"""Recover the terminal state of an interrupted RunLedger run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .ledger import Ledger


def recover(run_dir: Path) -> dict[str, Any]:
    ledger = Ledger(run_dir)
    pending: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    for event in ledger.events():
        if event.get("type") == "command.started":
            pending.append(event)
        elif event.get("type") == "command.completed":
            completed.append(event)
    unmatched: list[int] = []
    used: set[int] = set()
    for started in pending:
        match = next(
            (
                event for event in completed
                if event.get("seq") not in used
                and event.get("command_sha256") == started.get("command_sha256")
                and event.get("seq", 0) > started.get("seq", 0)
            ),
            None,
        )
        if match is None:
            unmatched.append(started["seq"])
        else:
            used.add(match["seq"])
    status = "incomplete" if unmatched else "complete"
    result = {
        "schema": "runledger.recovery.v1",
        "status": status,
        "pending_sequences": unmatched,
        "completed_commands": len(used),
    }
    ledger.append("run.recovered", result)
    ledger.artifacts.write_text("recovery.json", __import__("json").dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return result
