"""Render deterministic summaries from a recorded run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ledger import Ledger, canonical_json


def load_run(run_dir: Path) -> dict[str, Any]:
    run_json = run_dir / "run.json"
    if run_json.exists():
        return json.loads(run_json.read_text(encoding="utf-8"))
    return {"run_id": run_dir.name}


def build_summary(run_dir: Path) -> dict[str, Any]:
    ledger = Ledger(run_dir)
    events = list(ledger.events())
    completed = [event for event in events if event.get("type") == "command.completed"]
    commands: list[dict[str, Any]] = []
    for event in completed:
        commands.append(
            {
                "seq": event["seq"],
                "command": event.get("command_display", ""),
                "exit_code": event.get("exit_code"),
                "duration_ms": event.get("duration_ms", 0),
                "timed_out": event.get("timed_out", False),
                "redaction_count": event.get("redaction_count", 0),
                "stdout": event.get("stdout"),
                "stderr": event.get("stderr"),
            }
        )
    data = load_run(run_dir)
    snapshot_before = data.get("git_before")
    snapshot_after = data.get("git_after")
    checks = {}
    checks_path = run_dir / "artifacts" / "checks.json"
    if checks_path.exists():
        checks = json.loads(checks_path.read_text(encoding="utf-8"))
    command_status = "passed" if commands and all(item["exit_code"] == 0 for item in commands) else ("failed" if commands else "incomplete")
    check_status = checks.get("status") if checks else None
    overall_status = "failed" if command_status == "failed" or check_status == "failed" else ("passed" if command_status == "passed" else "incomplete")
    return {
        "schema": "runledger.report.v1",
        "run_id": data.get("run_id", run_dir.name),
        "status": overall_status,
        "commands": commands,
        "event_count": len(events),
        "artifact_root": "artifacts",
        "git_before": snapshot_before,
        "git_after": snapshot_after,
        "checks": checks,
    }


def render_json(run_dir: Path) -> str:
    return canonical_json(build_summary(run_dir)) + "\n"


def render_markdown(run_dir: Path) -> str:
    summary = build_summary(run_dir)
    lines = [
        f"# RunLedger report: `{summary['run_id']}`",
        "",
        f"**Status:** `{summary['status']}`  ",
        f"**Events:** {summary['event_count']}  ",
        f"**Commands:** {len(summary['commands'])}",
        "",
        "## Commands",
        "",
        "| Sequence | Command | Exit | Duration | Timeout | Redactions |",
        "|---:|---|---:|---:|:---:|---:|",
    ]
    for command in summary["commands"]:
        lines.append(
            f"| {command['seq']} | `{command['command']}` | {command['exit_code']} | {command['duration_ms']} ms | "
            f"{'yes' if command['timed_out'] else 'no'} | {command['redaction_count']} |"
        )
    if not summary["commands"]:
        lines.append("| — | No completed commands | — | — | — | — |")
    checks = summary.get("checks") or {}
    if checks:
        lines.extend(["", "## Contract checks", "", "| Check | Kind | Status | Message |", "|---|---|---|---|"])
        for check in checks.get("checks", []):
            lines.append(f"| `{check.get('id')}` | `{check.get('kind')}` | `{check.get('status')}` | {check.get('message', '')} |")
    lines.extend(["", "## Git evidence", ""])
    for label, snapshot in (("Before", summary.get("git_before")), ("After", summary.get("git_after"))):
        lines.append(f"### {label}")
        if not snapshot:
            lines.append("Git snapshot unavailable.")
            continue
        lines.append(f"- Available: `{snapshot.get('available')}`")
        lines.append(f"- HEAD: `{snapshot.get('head') or 'unknown'}`")
        lines.append(f"- Branch: `{snapshot.get('branch') or 'unknown'}`")
        lines.append(f"- Changed paths recorded: `{len(snapshot.get('status', []))}`")
        lines.append("")
    lines.extend([
        "## Evidence boundary",
        "",
        "This report summarizes observable process output and repository state. It does not prove code correctness, security, or the safety of the recorded command.",
        "",
    ])
    return "\n".join(lines)
