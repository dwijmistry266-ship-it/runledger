"""Unit tests for runledger.compare: run-diff edge cases.

Covers the inputs the happy-path tests never exercise: missing run.json,
missing run_id/git_after fields, empty ledgers, malformed git status entries
(too short, empty, non-string), renames, and commands with missing fields.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runledger.compare import build_comparison, render_json, render_markdown
from runledger.ledger import Ledger


def make_run(root: Path, name: str, *, manifest: dict | None = None,
             completed: list[dict] | None = None) -> Path:
    """Build a synthetic run dir.

    ``manifest`` is written as run.json verbatim (pass None to skip it
    entirely); each dict in ``completed`` is appended as a
    ``command.completed`` event.
    """
    run_dir = root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        (run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    if completed:
        ledger = Ledger(run_dir, run_id=name)
        for payload in completed:
            ledger.append("command.completed", dict(payload))
    return run_dir


class TestEmptyAndMissingInputs(unittest.TestCase):
    def test_two_empty_run_dirs_compare_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "run-a"
            run_b = root / "run-b"
            run_a.mkdir()
            run_b.mkdir()
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["schema"], "runledger.compare.v1")
            self.assertEqual(comparison["run_a"]["id"], "run-a")
            self.assertEqual(comparison["run_b"]["id"], "run-b")
            for side in ("run_a", "run_b"):
                self.assertEqual(comparison[side]["status"], "incomplete")
                self.assertEqual(comparison[side]["commands"], 0)
                self.assertEqual(comparison[side]["duration_ms"], 0)
                self.assertEqual(comparison[side]["failed_commands"], 0)
            self.assertEqual(comparison["paths"]["only_a"], [])
            self.assertEqual(comparison["paths"]["only_b"], [])
            self.assertEqual(comparison["paths"]["common"], [])

    def test_run_id_falls_back_to_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={"git_after": {"status": []}})
            run_b = make_run(root, "run-b", manifest={})
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["run_a"]["id"], "run-a")
            self.assertEqual(comparison["run_b"]["id"], "run-b")

    def test_missing_git_after_and_status_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={"run_id": "run-a"})  # no git_after at all
            run_b = make_run(root, "run-b",
                             manifest={"run_id": "run-b", "git_after": None})  # explicit null
            run_c = make_run(root, "run-c",
                             manifest={"run_id": "run-c", "git_after": {"head": "abc123"}})  # no status
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["paths"]["only_a"], [])
            comparison = build_comparison(run_a, run_c)
            self.assertEqual(comparison["paths"]["common"], [])

    def test_malformed_status_entries_are_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={
                "run_id": "run-a",
                "git_after": {
                    "status": [
                        " M src/a.py",
                        "XY",       # shorter than a git XY prefix: kept as-is
                        "M ",       # 2 chars, no path part: kept as-is
                        " M ",      # 3 chars stripping to an empty path: dropped
                        " M ",
                        "",         # empty string: dropped
                        42,         # non-string entry: skipped, no crash
                        None,       # non-string entry: skipped, no crash
                        {"path": "src/x.py"},  # non-string entry: skipped, no crash
                    ]
                },
            })
            run_b = make_run(root, "run-b", manifest={"run_id": "run-b"})
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["paths"]["only_a"], ["M ", "XY", "src/a.py"])
            self.assertEqual(comparison["paths"]["only_b"], [])
            self.assertEqual(comparison["paths"]["common"], [])


class TestPathDiffs(unittest.TestCase):
    def test_rename_resolves_to_destination_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={
                "run_id": "run-a",
                "git_after": {"status": ["R  old.py -> new.py", "C  c1.py -> c2.py"]},
            })
            run_b = make_run(root, "run-b", manifest={"run_id": "run-b"})
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["paths"]["only_a"], ["c2.py", "new.py"])
            self.assertNotIn("old.py", comparison["paths"]["only_a"])

    def test_duplicate_statuses_are_deduplicated_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={
                "run_id": "run-a",
                "git_after": {"status": [" M z.py", " M z.py", "A  a.py"]},
            })
            run_b = make_run(root, "run-b", manifest={"run_id": "run-b"})
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["paths"]["only_a"], ["a.py", "z.py"])

    def test_identical_runs_share_all_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "run_id": "same",
                "git_after": {"status": [" M src/a.py", "?? src/b.py"]},
            }
            run_a = make_run(root, "run-a", manifest=dict(manifest))
            run_b = make_run(root, "run-b", manifest=dict(manifest))
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["paths"]["common"], ["src/a.py", "src/b.py"])
            self.assertEqual(comparison["paths"]["only_a"], [])
            self.assertEqual(comparison["paths"]["only_b"], [])


class TestCommandDiffs(unittest.TestCase):
    def test_failed_commands_count_includes_missing_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={"run_id": "run-a"}, completed=[
                {"command_display": "ok", "exit_code": 0, "duration_ms": 100},
                {"command_display": "broken", "exit_code": 1, "duration_ms": 50},
                {"command_display": "unknown"},  # no exit_code: counted as failed, like the status logic
                {"command_display": "instant", "exit_code": 0},  # no duration_ms: 0
            ])
            run_b = make_run(root, "run-b", manifest={"run_id": "run-b"})
            comparison = build_comparison(run_a, run_b)
            self.assertEqual(comparison["run_a"]["commands"], 4)
            self.assertEqual(comparison["run_a"]["duration_ms"], 150)
            self.assertEqual(comparison["run_a"]["failed_commands"], 2)
            self.assertEqual(comparison["run_a"]["status"], "failed")
            self.assertEqual(comparison["run_b"]["failed_commands"], 0)


class TestRenderers(unittest.TestCase):
    def test_render_json_is_valid_json_with_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={"run_id": "run-a"})
            run_b = make_run(root, "run-b", manifest={"run_id": "run-b"})
            parsed = json.loads(render_json(run_a, run_b))
            self.assertEqual(parsed["schema"], "runledger.compare.v1")
            self.assertEqual(parsed["run_a"]["id"], "run-a")

    def test_render_markdown_reports_none_for_empty_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={"run_id": "run-a"})
            run_b = make_run(root, "run-b", manifest={"run_id": "run-b"})
            markdown = render_markdown(run_a, run_b)
            self.assertIn("`run-a` vs `run-b`", markdown)
            self.assertIn("Only in `run-a`: none", markdown)
            self.assertIn("Common paths: none", markdown)

    def test_render_markdown_lists_path_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = make_run(root, "run-a", manifest={
                "run_id": "run-a", "git_after": {"status": [" M src/a.py"]},
            })
            run_b = make_run(root, "run-b", manifest={
                "run_id": "run-b", "git_after": {"status": [" M src/b.py"]},
            })
            markdown = render_markdown(run_a, run_b)
            self.assertIn("Only in `run-a`: src/a.py", markdown)
            self.assertIn("Only in `run-b`: src/b.py", markdown)


if __name__ == "__main__":
    unittest.main()
