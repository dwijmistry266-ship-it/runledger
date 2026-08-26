"""Compare two recorded runs without interpreting model reasoning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .ledger import canonical_json
from .report import build_summary


def _paths(summary: dict[str, Any]) -> set[str]:
    snapshot = summary.get("git_after") or {}
    values: set[str] = set()
    for raw in snapshot.get("status", []):
        value = raw[3:] if len(raw) >= 3 else raw
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        if value:
            values.add(value)
    return values


def build_comparison(run_a: Path, run_b: Path) -> dict[str, Any]:
    first = build_summary(run_a)
    second = build_summary(run_b)
    paths_a = _paths(first)
    paths_b = _paths(second)
    return {
        "schema": "runledger.compare.v1",
        "run_a": {
            "id": first["run_id"],
            "status": first["status"],
            "commands": len(first["commands"]),
            "duration_ms": sum(command.get("duration_ms", 0) for command in first["commands"]),
            "failed_commands": sum(command.get("exit_code") != 0 for command in first["commands"]),
        },
        "run_b": {
            "id": second["run_id"],
            "status": second["status"],
            "commands": len(second["commands"]),
            "duration_ms": sum(command.get("duration_ms", 0) for command in second["commands"]),
            "failed_commands": sum(command.get("exit_code") != 0 for command in second["commands"]),
        },
        "paths": {
            "only_a": sorted(paths_a - paths_b),
            "only_b": sorted(paths_b - paths_a),
            "common": sorted(paths_a & paths_b),
        },
    }


def render_json(run_a: Path, run_b: Path) -> str:
    return canonical_json(build_comparison(run_a, run_b)) + "\n"


def render_markdown(run_a: Path, run_b: Path) -> str:
    comparison = build_comparison(run_a, run_b)
    left = comparison["run_a"]
    right = comparison["run_b"]
    lines = [
        f"# RunLedger comparison: `{left['id']}` vs `{right['id']}`",
        "",
        "| Metric | Run A | Run B |",
        "|---|---:|---:|",
        f"| Status | `{left['status']}` | `{right['status']}` |",
        f"| Commands | {left['commands']} | {right['commands']} |",
        f"| Duration | {left['duration_ms']} ms | {right['duration_ms']} ms |",
        f"| Failed commands | {left['failed_commands']} | {right['failed_commands']} |",
        "",
        "## Changed-path differences",
        "",
        f"- Only in `{left['id']}`: {', '.join(comparison['paths']['only_a']) or 'none'}",
        f"- Only in `{right['id']}`: {', '.join(comparison['paths']['only_b']) or 'none'}",
        f"- Common paths: {', '.join(comparison['paths']['common']) or 'none'}",
        "",
        "This comparison reports observable differences; it does not infer model quality or prove that either run is safe.",
        "",
    ]
    return "\n".join(lines)
