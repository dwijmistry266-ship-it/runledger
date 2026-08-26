from __future__ import annotations

import json
import subprocess
import tempfile
import zipfile
import unittest
from pathlib import Path

from runledger.bundle import build_bundle, verify_bundle
from runledger.compare import build_comparison
from runledger.cli import main
from runledger.contract import verify as verify_contract
from runledger.git import snapshot
from runledger.ledger import Ledger
from runledger.recorder import CommandRecorder
from runledger.report import build_summary, render_markdown
from runledger.viewer import render_html


class RunLedgerV01Tests(unittest.TestCase):
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

    def test_ledger_appends_monotonic_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / "run", run_id="test-run")
            ledger.append("one", {"value": 1}, timestamp="2026-01-01T00:00:00.000Z")
            ledger.append("two", {"value": 2}, timestamp="2026-01-01T00:00:01.000Z")
            events = list(ledger.events())
            self.assertEqual([event["seq"] for event in events], [1, 2])
            self.assertEqual(events[1]["run_id"], "test-run")
            self.assertEqual(ledger.events_path.read_text(encoding="utf-8").count("\n"), 2)

    def test_recorder_captures_and_redacts_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = Ledger(root / "run", run_id="capture")
            recorder = CommandRecorder(ledger, cwd=root)
            exit_code = recorder.run(["python3", "-c", "print('api_key=sk_test_123456789012345')"])
            self.assertEqual(exit_code, 0)
            output_files = sorted((root / "run" / "artifacts").glob("stdout-*.txt"))
            self.assertEqual(len(output_files), 1)
            output = output_files[0].read_text(encoding="utf-8")
            self.assertIn("[REDACTED]", output)
            self.assertNotIn("sk_test_123456789012345", output)
            self.assertEqual([event["type"] for event in ledger.events()], ["command.started", "command.completed"])

    def test_recorder_returns_nonzero_for_failed_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = Ledger(root / "run", run_id="failure")
            code = CommandRecorder(ledger, cwd=root).run(["python3", "-c", "raise SystemExit(3)"])
            self.assertEqual(code, 3)
            completed = list(ledger.events())[-1]
            self.assertEqual(completed["exit_code"], 3)

    def test_git_snapshot_records_clean_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            clean = snapshot(repo)
            self.assertTrue(clean.available)
            self.assertIsNotNone(clean.head)
            self.assertEqual(clean.status, [])
            (repo / "README.txt").write_text("changed\n", encoding="utf-8")
            dirty = snapshot(repo)
            self.assertEqual(len(dirty.status), 1)

    def test_contract_passes_for_recorded_command_and_allowed_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            run_dir = root / "run"
            self.assertEqual(main(["init", "--repo", str(repo), "--run-dir", str(run_dir), "--run-id", "contract-pass"]), 0)
            (repo / "src").mkdir()
            (repo / "src" / "feature.py").write_text("pass\n", encoding="utf-8")
            recorder = CommandRecorder(Ledger(run_dir, run_id="contract-pass"), cwd=repo)
            recorder.run(["python3", "-c", "print('fixture pass')"])
            after = snapshot(repo)
            metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            metadata["git_after"] = {**metadata.get("git_before", {}), **{**__import__("dataclasses").asdict(after)}}
            (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
            contract = root / "task.json"
            contract.write_text(json.dumps({"name": "pass", "allowed_paths": ["src/**"], "checks": [{"id": "tests-pass", "kind": "command-exit", "command": "python3 -c print('fixture pass')", "expect": 0}]}), encoding="utf-8")
            output, code = verify_contract(run_dir, contract)
            self.assertEqual(code, 0)
            self.assertEqual(output["status"], "passed")

    def test_contract_reports_missing_command_as_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            ledger = Ledger(run_dir, run_id="missing")
            CommandRecorder(ledger, cwd=root).run(["python3", "-c", "print('other')"])
            contract = root / "task.json"
            contract.write_text(json.dumps({"name": "missing", "checks": [{"id": "required", "kind": "command-exit", "command": "python3 -c print('required')", "expect": 0}]}), encoding="utf-8")
            output, code = verify_contract(run_dir, contract)
            self.assertEqual(code, 1)
            self.assertEqual(output["checks"][0]["status"], "not-run")

    def test_contract_rejects_forbidden_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            run_dir = root / "run"
            before = snapshot(repo)
            Ledger(run_dir, run_id="forbidden").write_manifest({"run_id": "forbidden", "git_before": __import__("dataclasses").asdict(before)})
            (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
            after = snapshot(repo)
            metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            metadata["git_after"] = __import__("dataclasses").asdict(after)
            (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
            contract = root / "task.json"
            contract.write_text(json.dumps({"name": "forbidden", "forbidden_paths": [".env"]}), encoding="utf-8")
            output, code = verify_contract(run_dir, contract)
            self.assertEqual(code, 1)
            self.assertEqual(output["checks"][0]["status"], "fail")

    def test_comparison_reports_path_and_command_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            Ledger(first, run_id="first").write_manifest({"run_id": "first", "git_after": {"status": [" M src/a.py"]}})
            Ledger(second, run_id="second").write_manifest({"run_id": "second", "git_after": {"status": [" M src/b.py"]}})
            CommandRecorder(Ledger(first, run_id="first"), cwd=root).run(["python3", "-c", "print('a')"])
            result = build_comparison(first, second)
            self.assertEqual(result["run_a"]["id"], "first")
            self.assertIn("src/a.py", result["paths"]["only_a"])
            self.assertIn("src/b.py", result["paths"]["only_b"])
            self.assertEqual(result["run_b"]["commands"], 0)

    def test_bundle_verification_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            ledger = Ledger(run_dir, run_id="bundle")
            ledger.write_manifest({"run_id": "bundle"})
            ledger.artifacts.write_text("sample.txt", "original")
            bundle = root / "proof.zip"
            build_bundle(run_dir, bundle)
            valid, errors = verify_bundle(bundle)
            self.assertTrue(valid, errors)
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(tampered, "w") as target:
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename == "artifacts/sample.txt":
                        data = b"modified"
                    target.writestr(item, data)
            valid, errors = verify_bundle(tampered)
            self.assertFalse(valid)
            self.assertTrue(any("hash mismatch" in error for error in errors))

    def test_html_viewer_contains_events_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "viewer"
            ledger = Ledger(run_dir, run_id="viewer")
            CommandRecorder(ledger, cwd=root).run(["python3", "-c", "print('hello')"])
            page = render_html(run_dir)
            self.assertIn("RunLedger replay", page)
            self.assertIn("command.completed", page)
            self.assertIn("stdout-", page)
            self.assertIn("id=\"filter\"", page)

    def test_report_marks_pass_and_contains_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "report"
            ledger = Ledger(run_dir, run_id="report")
            CommandRecorder(ledger, cwd=root).run(["python3", "-c", "print('ok')"])
            summary = build_summary(run_dir)
            self.assertEqual(summary["status"], "passed")
            markdown = render_markdown(run_dir)
            self.assertIn("# RunLedger report: `report`", markdown)
            self.assertIn("does not prove code correctness", markdown)


if __name__ == "__main__":
    unittest.main()
