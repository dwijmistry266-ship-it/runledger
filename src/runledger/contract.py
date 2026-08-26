"""Deterministic verification of a recorded run against a JSON task contract."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .ledger import Ledger, canonical_json


@dataclass(frozen=True)
class CheckResult:
    id: str
    kind: str
    status: str
    message: str
    evidence: dict[str, Any]


def load_contract(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"contract must be valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("contract root must be a JSON object")
    if not data.get("name"):
        raise ValueError("contract requires a name")
    if not isinstance(data.get("checks", []), list):
        raise ValueError("contract checks must be a list")
    return data


def _changed_paths(run: dict[str, Any]) -> list[str]:
    snapshot = run.get("git_after") or {}
    paths: list[str] = []
    for raw in snapshot.get("status", []):
        entry = raw[3:] if len(raw) >= 3 else raw
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        if entry:
            paths.append(entry)
    return sorted(set(paths))


def _diff_lines(run_dir: Path) -> tuple[int, int]:
    patch = run_dir / "artifacts" / "git-diff.patch"
    if not patch.exists():
        return 0, 0
    additions = deletions = 0
    for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions


def _completed_commands(run_dir: Path) -> list[dict[str, Any]]:
    return [event for event in Ledger(run_dir).events() if event.get("type") == "command.completed"]


def _path_policy(contract: dict[str, Any], changed: list[str]) -> CheckResult:
    forbidden = contract.get("forbidden_paths", [])
    allowed = contract.get("allowed_paths", [])
    forbidden_hits = [path for path in changed if any(fnmatch.fnmatch(path, pattern) for pattern in forbidden)]
    outside_allowed = [path for path in changed if allowed and not any(fnmatch.fnmatch(path, pattern) for pattern in allowed)]
    if forbidden_hits:
        return CheckResult("path-policy", "path-policy", "fail", "forbidden paths changed", {"forbidden": forbidden_hits})
    if outside_allowed:
        return CheckResult("path-policy", "path-policy", "fail", "paths fall outside the allowed set", {"outside_allowed": outside_allowed})
    return CheckResult("path-policy", "path-policy", "pass", "changed paths satisfy the declared policy", {"changed_paths": changed})


def _command_check(check: dict[str, Any], commands: list[dict[str, Any]]) -> CheckResult:
    expected = check.get("command")
    if not isinstance(expected, str) or not expected:
        return CheckResult(check.get("id", "command"), "command-exit", "unknown", "command-exit check requires a command", {})
    matches = [event for event in commands if event.get("command_display") == expected]
    if not matches:
        return CheckResult(check.get("id", expected), "command-exit", "not-run", "required command was not recorded", {"command": expected})
    event = matches[-1]
    expected_exit = check.get("expect", 0)
    actual = event.get("exit_code")
    status = "pass" if actual == expected_exit else "fail"
    message = "command exited with the expected status" if status == "pass" else "command exited with an unexpected status"
    return CheckResult(check.get("id", expected), "command-exit", status, message, {"command": expected, "expected": expected_exit, "actual": actual, "seq": event.get("seq")})


def _diff_budget(check: dict[str, Any], run_dir: Path) -> CheckResult:
    additions, deletions = _diff_lines(run_dir)
    total = additions + deletions
    maximum = check.get("maximum")
    if not isinstance(maximum, int) or maximum < 0:
        return CheckResult(check.get("id", "diff-budget"), "changed-lines", "unknown", "changed-lines check requires a non-negative integer maximum", {})
    status = "pass" if total <= maximum else "fail"
    message = "changed-line budget respected" if status == "pass" else "changed-line budget exceeded"
    return CheckResult(check.get("id", "diff-budget"), "changed-lines", status, message, {"additions": additions, "deletions": deletions, "total": total, "maximum": maximum})


def verify(run_dir: Path, contract_path: Path) -> tuple[dict[str, Any], int]:
    contract = load_contract(contract_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8")) if (run_dir / "run.json").exists() else {}
    changed = _changed_paths(run)
    commands = _completed_commands(run_dir)
    results: list[CheckResult] = []
    if contract.get("allowed_paths") or contract.get("forbidden_paths"):
        results.append(_path_policy(contract, changed))
    for check in contract.get("checks", []):
        if not isinstance(check, dict):
            results.append(CheckResult("invalid-check", "unknown", "unknown", "check must be an object", {}))
            continue
        kind = check.get("kind")
        if kind == "command-exit":
            results.append(_command_check(check, commands))
        elif kind == "path-policy":
            results.append(_path_policy(contract, changed))
        elif kind == "changed-lines":
            results.append(_diff_budget(check, run_dir))
        else:
            results.append(CheckResult(check.get("id", "unknown"), str(kind), "unknown", "unsupported check kind", {}))
    if not results:
        results.append(CheckResult("contract", "contract", "unknown", "contract contains no executable checks", {}))
    status = "passed" if all(result.status == "pass" for result in results) else "failed"
    output = {
        "schema": "runledger.checks.v1",
        "contract": contract.get("name"),
        "status": status,
        "checks": [asdict(result) for result in results],
    }
    ledger = Ledger(run_dir, run_id=run.get("run_id", run_dir.name))
    ledger.artifacts.write_text("checks.json", canonical_json(output) + "\n")
    ledger.append("verification.completed", {"contract": contract.get("name"), "status": status, "check_count": len(results)})
    return output, 0 if status == "passed" else 1
