"""RunLedger v0.2 milestone tests: interactive PTY fixture and artifact index."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from runledger.ledger import Ledger
from runledger.pty import run_pty
from runledger.recorder import CommandRecorder
from runledger.recovery import recover
from runledger.report import artifact_index, build_summary


PYTHON = sys.executable  # interpreter running the suite; portable across platforms


class RunLedgerV02Tests(unittest.TestCase):
    def test_interactive_pty_session_records_typed_input_and_output(self) -> None:
        if os.name != "posix":
            self.skipTest("PTY capture is POSIX-only")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = Ledger(root / "run", run_id="interactive")
            code = run_pty(
                ledger,
                [PYTHON, "-i"],
                cwd=root,
                stdin_data=b"print('interactive-ok')\nexit()\n",
                timeout=20,
            )
            self.assertEqual(code, 0)
            events = list(ledger.events())
            self.assertEqual([event["type"] for event in events], ["command.started", "command.completed"])
            self.assertEqual(events[0]["stdin_bytes"], len(b"print('interactive-ok')\nexit()\n"))
            transcript = (root / "run" / "artifacts" / "pty-1.log").read_text(encoding="utf-8")
            self.assertIn("interactive-ok", transcript)

    def test_interrupted_interactive_session_is_recoverable_as_incomplete(self) -> None:
        if os.name != "posix":
            self.skipTest("PTY capture is POSIX-only")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = Ledger(root / "run", run_id="interrupted-pty")
            ledger.append(
                "command.started",
                {
                    "capture": "pty",
                    "command_display": "python3 -i",
                    "command_sha256": "unfinished-interactive",
                    "stdin_bytes": 0,
                },
            )
            result = recover(root / "run")
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["pending_sequences"], [1])

    def test_report_summary_contains_artifact_index_with_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            ledger = Ledger(run_dir, run_id="indexed")
            CommandRecorder(ledger, cwd=root).run([PYTHON, "-c", "print('indexed')"])
            summary = build_summary(run_dir)
            index = summary["artifacts"]
            by_name = {entry["path"].split("/")[-1]: entry for entry in index}
            self.assertIn("stdout-1.txt", by_name)
            self.assertIn("stderr-1.txt", by_name)
            for entry in index:
                self.assertEqual(len(entry["sha256"]), 64)
                self.assertGreaterEqual(entry["bytes"], 0)
            expected = hashlib.sha256(b"indexed\n").hexdigest()
            self.assertEqual(by_name["stdout-1.txt"]["sha256"], expected)
            self.assertEqual(
                [entry["path"] for entry in index],
                sorted(entry["path"] for entry in index),
            )

    def test_artifact_index_is_empty_for_run_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            Ledger(run_dir, run_id="empty")
            self.assertEqual(artifact_index(run_dir), [])


if __name__ == "__main__":
    unittest.main()
