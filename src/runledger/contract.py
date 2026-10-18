"""Deterministic verification of a recorded run against a JSON task contract.

A contract names a task and declares the checks a recorded run must satisfy:

``command-exit`` — a recorded command whose ``command_display`` matches and whose
exit code equals ``expect`` (default ``0``); ``path-policy`` — the top-level
``allowed_paths``/``forbidden_paths`` glob policies every changed path must
satisfy; ``changed-lines`` — an ``artifacts/git-diff.patch`` budget of at most
``maximum`` added + deleted lines.

Every check yields a :class:`CheckResult` with status ``pass``, ``fail``,
``unknown`` (check is malformed or unevaluable) or ``not-run`` (a required
command was never recorded). A run only ``passes`` when every check passes;
anything else is ``failed``. :func:`verify` writes the machine-readable
``checks.json`` artifact and logs a ``verification.completed`` ledger event, so
a verification is itself recorded for later audit.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .ledger import Ledger, canonical_json


@dataclass(frozen=True)
class CheckResult:
    """One executed contract check.

    ``id`` is the contract's own check id (or a fallback); ``kind`` names the
    check kind; ``status`` is one of ``pass``, ``fail``, ``unknown`` or
    ``not-run``; ``message`` is the human-readable verdict; ``evidence`` holds
    the JSON-serializable facts the verdict was based on.
    """

    id: str
    kind: str
    status: str
    message: str
    evidence: dict[str, Any]


def load_contract(path: Path) -> dict[str, Any]:
    """Read and structurally validate the JSON contract at ``path``.

    Returns the contract dict unchanged. Raises :class:`ValueError` when the
    file is not valid JSON, the root is not an object, the ``name`` is missing
    or empty, or ``checks`` is present but not a list.
    """
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
    """Return the deduplicated, sorted paths changed by the recorded run.

    Derived from the ``git_after`` snapshot's ``status`` entries: the leading
    3-character status prefix is stripped, and rename entries (``old -> new``)
    resolve to the destination path. Entries shorter than 3 characters are
    kept verbatim rather than mangled. An absent ``git_after`` snapshot means
    no changed paths.
    """
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
    """Count added and deleted lines in the run's ``artifacts/git-diff.patch``.

    The ``+++``/``---`` file-header lines are not counted. A missing patch is
    not an error — the run simply recorded no diff, so ``(0, 0)`` is returned.
    """
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
    """Return every ``command.completed`` ledger event for the run, in order."""
    return [event for event in Ledger(run_dir).events() if event.get("type") == "command.completed"]


def _path_policy(contract: dict[str, Any], changed: list[str]) -> CheckResult:
    """Check the run's changed paths against the contract's path policy.

    Patterns are matched with ``fnmatch`` against the full relative path.
    A hit on any ``forbidden_paths`` pattern fails the check; when
    ``allowed_paths`` is non-empty, any path matching none of them fails it
    too. An empty ``allowed_paths`` list constrains nothing. Forbidden wins
    when a path matches both lists. Evidence names the offending paths (or
    the full changed set on success).
    """
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
    """Check that the contract's ``command`` was recorded and exited as expected.

    The expected exit code comes from ``expect`` (default ``0``). The required
    command must appear among the recorded ``command.completed`` events with
    an exact ``command_display`` match — a mismatch is status ``not-run``, not
    ``fail``. When the command ran more than once, the most recent invocation
    decides. A malformed check (missing or non-string ``command``) yields
    ``unknown``. Evidence carries the expected/actual exit codes and the
    ledger ``seq`` of the matched event.
    """
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
    """Check the run's changed-line total against the check's ``maximum``.

    ``maximum`` must be a non-negative integer; anything else yields
    ``unknown`` rather than an assumed budget. The total counts added plus
    deleted patch lines (see :func:`_diff_lines`), so a refactor touching many
    lines fails even if the net change is small. Evidence records additions,
    deletions, the total, and the budget.
    """
    additions, deletions = _diff_lines(run_dir)
    total = additions + deletions
    maximum = check.get("maximum")
    if not isinstance(maximum, int) or maximum < 0:
        return CheckResult(check.get("id", "diff-budget"), "changed-lines", "unknown", "changed-lines check requires a non-negative integer maximum", {})
    status = "pass" if total <= maximum else "fail"
    message = "changed-line budget respected" if status == "pass" else "changed-line budget exceeded"
    return CheckResult(check.get("id", "diff-budget"), "changed-lines", status, message, {"additions": additions, "deletions": deletions, "total": total, "maximum": maximum})


def verify(run_dir: Path, contract_path: Path) -> tuple[dict[str, Any], int]:
    """Verify a recorded run against a contract and persist the verdict.

    Runs every executable check in the contract (top-level
    ``allowed_paths``/``forbidden_paths`` first, then each entry in
    ``checks``; non-object checks and unsupported kinds become ``unknown``
    results rather than raising). A contract with no executable checks yields
    a single ``unknown`` result, so it can never silently pass.

    The verdict is written to ``artifacts/checks.json`` (schema
    ``runledger.checks.v1``) and a ``verification.completed`` event is
    appended to the run's ledger, making the verification itself part of the
    recorded run. Returns ``(output, exit_code)`` where the exit code is ``0``
    when every check passed and ``1`` otherwise.
    """
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
