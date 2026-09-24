"""RunLedger v0.4 milestone tests: adapters produce the same event contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runledger.adapters import (
    AdapterCommand,
    PromptArgumentAdapter,
    PromptFileAdapter,
    conformance_check,
    validate_adapter_command,
)
from runledger.ledger import Ledger
from runledger.recorder import CommandRecorder


def event_vocabulary(run_dir: Path) -> list[tuple[str, tuple[str, ...]]]:
    """The ordered event contract of a run: types plus payload key sets."""
    events = list(Ledger(run_dir).events())
    return [(event["type"], tuple(sorted(event.keys()))) for event in events]


class RunLedgerV04Tests(unittest.TestCase):
    def test_both_adapters_produce_the_same_event_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = {"prompt-argument": "fix the bug", "prompt-file": "task.md"}
            vocabularies = []
            for adapter in (PromptArgumentAdapter("true"), PromptFileAdapter("true")):
                task = tasks[adapter.name]
                valid, errors = conformance_check(adapter, task, root)
                self.assertTrue(valid, errors)
                command = adapter.build(task, root)
                run_dir = root / f"run-{adapter.name}"
                ledger = Ledger(run_dir, run_id=f"adapter-{adapter.name}")
                exit_code = CommandRecorder(ledger, cwd=root).run(list(command.argv))
                self.assertEqual(exit_code, 0)
                vocabularies.append(event_vocabulary(run_dir))
            self.assertEqual(vocabularies[0], vocabularies[1])
            self.assertEqual(
                [event_type for event_type, _ in vocabularies[0]],
                ["command.started", "command.completed"],
            )

    def test_conformance_rejects_empty_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            valid, errors = conformance_check(PromptArgumentAdapter("true"), "   ", Path(tmp))
            self.assertFalse(valid)
            self.assertTrue(errors)

    def test_validation_rejects_shell_metacharacters_in_fixed_args(self) -> None:
        command = AdapterCommand("prompt-argument", ("agent", "--flag;rm", "task"), "task", "/tmp/repo")
        errors = validate_adapter_command(command)
        self.assertTrue(any("shell metacharacters" in error for error in errors))

    def test_validation_rejects_empty_argv(self) -> None:
        command = AdapterCommand("prompt-argument", (), "task", "/tmp/repo")
        errors = validate_adapter_command(command)
        self.assertTrue(any("argv" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
