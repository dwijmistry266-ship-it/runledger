"""Deterministic SARIF output for RunLedger contract findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ledger import canonical_json


def _level(status: str) -> str:
    return "error" if status == "fail" else "warning"


def build_sarif(run_dir: Path) -> dict[str, Any]:
    checks_path = run_dir / "artifacts" / "checks.json"
    checks = json.loads(checks_path.read_text(encoding="utf-8")) if checks_path.exists() else {"checks": []}
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for check in checks.get("checks", []):
        status = check.get("status")
        if status == "pass":
            continue
        check_id = str(check.get("id", "unknown"))
        rule_id = f"runledger/{check_id}"
        rules.setdefault(rule_id, {"id": rule_id, "name": check_id, "shortDescription": {"text": check.get("message", "RunLedger check did not pass")}})
        result = {
            "ruleId": rule_id,
            "level": _level(status),
            "message": {"text": check.get("message", "RunLedger check requires attention")},
            "properties": {"runledgerStatus": status, "evidence": check.get("evidence", {})},
        }
        evidence = check.get("evidence", {})
        paths = evidence.get("forbidden", []) or evidence.get("outside_allowed", [])
        if paths:
            result["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": path}}} for path in sorted(paths)]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "RunLedger", "informationUri": "https://github.com/dwijmistry266-ship-it/runledger", "rules": [rules[key] for key in sorted(rules)]}},
            "results": results,
        }],
    }


def render_sarif(run_dir: Path) -> str:
    return canonical_json(build_sarif(run_dir)) + "\n"
