"""RunLedger v0.3 milestone tests: concurrent isolation and explicit safety limits."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from runledger.cli import main
from runledger.ledger import Ledger
from runledger.pty import run_pty
from runledger.recorder import CommandRecorder


PYTHON = sys.executable  # interpreter running the suite; portable across platforms


class RunLedgerV03Tests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "RunLedger Test"], check=True)
        (repo / "README.txt").write_text("initial\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "README.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
        return repo

    def test_two_concurrent_isolated_runs_remain_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            run_dirs = [root / "run-a", root / "run-b"]
            markers = ["marker-a.txt", "marker-b.txt"]
            for run_dir, run_id in zip(run_dirs, ("run-a", "run-b")):
                self.assertEqual(
                    main(["init", "--repo", str(repo), "--run-dir", str(run_dir), "--run-id", run_id]), 0
                )

            errors: list[BaseException] = []
            codes: dict[str, int] = {}

            def isolated_exec(tag: str, run_dir: Path, marker: str) -> None:
                try:
                    codes[tag] = main(
                        [
                            "exec",
                            "--repo",
                            str(repo),
                            "--run-dir",
                            str(run_dir),
                            "--isolated",
                            "--",
                            PYTHON,
                            "-c",
                            f"open({marker!r}, 'w').write({tag!r})",
                        ]
                    )
                except BaseException as exc:  # noqa: BLE001 - surfaced below
                    errors.append(exc)

            threads = [
                threading.Thread(target=isolated_exec, args=("a", run_dirs[0], markers[0])),
                threading.Thread(target=isolated_exec, args=("b", run_dirs[1], markers[1])),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=120)
            self.assertFalse(errors, [str(exc) for exc in errors])
            self.assertEqual(codes, {"a": 0, "b": 0})

            # Neither run touched the caller's checkout, and both worktrees are gone.
            self.assertFalse((repo / markers[0]).exists())
            self.assertFalse((repo / markers[1]).exists())
            for run_dir in run_dirs:
                self.assertFalse((run_dir / "worktree").exists())

            # Each run saw only its own file.
            diff_a = (run_dirs[0] / "artifacts" / "git-diff.patch").read_text(encoding="utf-8")
            diff_b = (run_dirs[1] / "artifacts" / "git-diff.patch").read_text(encoding="utf-8")
            self.assertIn(markers[0], diff_a)
            self.assertNotIn(markers[1], diff_a)
            self.assertIn(markers[1], diff_b)
            self.assertNotIn(markers[0], diff_b)

    def test_run_manifest_declares_network_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            run_dir = root / "run"
            self.assertEqual(main(["init", "--repo", str(repo), "--run-dir", str(run_dir), "--run-id", "net"]), 0)
            manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["network"], "unrestricted")

    def test_recorder_rejects_shell_string_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / "run", run_id="shell-string")
            with self.assertRaises(ValueError):
                CommandRecorder(ledger, cwd=Path(tmp)).run("python3 -c print('x')")  # type: ignore[arg-type]

    def test_pty_rejects_shell_string_command(self) -> None:
        import os

        if os.name != "posix":
            self.skipTest("PTY capture is POSIX-only")
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / "run", run_id="shell-string-pty")
            with self.assertRaises(ValueError):
                run_pty(ledger, "python3 -c print('x')", cwd=Path(tmp))  # type: ignore[arg-type]

    def test_exec_requires_a_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            run_dir = root / "run"
            self.assertEqual(main(["init", "--repo", str(repo), "--run-dir", str(run_dir), "--run-id", "nocmd"]), 0)
            with self.assertRaises(SystemExit):
                main(["exec", "--repo", str(repo), "--run-dir", str(run_dir), "--"])


if __name__ == "__main__":
    unittest.main()
