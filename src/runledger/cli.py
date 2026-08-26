"""Command-line interface for RunLedger v0.1."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

from .bundle import build_bundle, verify_bundle
from .compare import render_json as render_compare_json, render_markdown as render_compare_markdown
from .contract import verify as verify_contract
from .git import diff as git_diff
from .git import snapshot as git_snapshot
from .ledger import Ledger
from .pty import run_pty
from .recorder import CommandRecorder
from .recovery import recover
from .sarif import render_sarif
from .report import render_json, render_markdown
from .viewer import render_html
from .worktree import Worktree


def _snapshot_payload(value):
    return asdict(value)


def _write_run_metadata(run_dir: Path, run_id: str, repo: Path, before=None, after=None) -> None:
    ledger = Ledger(run_dir, run_id=run_id)
    current = {}
    if (run_dir / "run.json").exists():
        current = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    current.update({"schema": "runledger.run.v1", "run_id": run_id, "repo": str(repo.resolve())})
    if before is not None:
        current["git_before"] = _snapshot_payload(before)
    if after is not None:
        current["git_after"] = _snapshot_payload(after)
    ledger.write_manifest(current)


def _init(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    run_id = args.run_id or f"run-{uuid.uuid4().hex[:12]}"
    run_dir = Path(args.run_dir).resolve() if args.run_dir else Path(".runledger") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    before = git_snapshot(repo)
    _write_run_metadata(run_dir, run_id, repo, before=before)
    Ledger(run_dir, run_id=run_id).append(
        "run.initialized",
        {"actor": "runledger", "repo": str(repo), "git": _snapshot_payload(before)},
    )
    print(run_dir)
    return 0


def _exec(args: argparse.Namespace) -> int:
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("runledger exec requires a command after --")
    run_dir = Path(args.run_dir).resolve()
    run_json = run_dir / "run.json"
    if not run_json.exists():
        raise SystemExit(f"run does not exist: {run_dir}; run `runledger init` first")
    metadata = json.loads(run_json.read_text(encoding="utf-8"))
    repo = Path(args.repo or metadata.get("repo", ".")).resolve()
    ledger = Ledger(run_dir, run_id=metadata.get("run_id", run_dir.name))
    worktree = None
    execution_repo = repo
    if args.isolated:
        worktree = Worktree(repo, run_dir / "worktree")
        execution_repo = worktree.create()
        ledger.append("worktree.created", {"repository": str(repo), "path": str(execution_repo), "isolated": True})
    diff_output = ""
    try:
        if args.pty:
            exit_code = run_pty(ledger, command, cwd=execution_repo, timeout=args.timeout)
        else:
            recorder = CommandRecorder(ledger, cwd=execution_repo)
            exit_code = recorder.run(command, timeout=args.timeout)
        after = git_snapshot(execution_repo)
        if after.available:
            try:
                diff_output = git_diff(execution_repo)
            except RuntimeError as exc:
                diff_output = f"[runledger] unable to capture diff: {exc}\n"
    finally:
        if worktree is not None:
            worktree.remove()
    ledger.artifacts.write_text("git-diff.patch", diff_output)
    _write_run_metadata(run_dir, metadata.get("run_id", run_dir.name), repo, after=after)
    print(f"run={run_dir} exit_code={exit_code}")
    return exit_code


def _compare(args: argparse.Namespace) -> int:
    if args.format == "json":
        output = render_compare_json(Path(args.run_a).resolve(), Path(args.run_b).resolve())
    else:
        output = render_compare_markdown(Path(args.run_a).resolve(), Path(args.run_b).resolve())
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(args.output)
    else:
        sys.stdout.write(output)
    return 0


def _recover(args: argparse.Namespace) -> int:
    result = recover(Path(args.run_dir).resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "complete" else 1


def _bundle(args: argparse.Namespace) -> int:
    bundle_path = Path(args.output).resolve()
    if args.bundle_action == "create":
        manifest = build_bundle(Path(args.run_dir), bundle_path)
        print(json.dumps({"bundle": str(bundle_path), "files": len(manifest["files"])}, sort_keys=True))
        return 0
    valid, errors = verify_bundle(bundle_path)
    if valid:
        print(f"valid bundle: {bundle_path}")
        return 0
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1


def _verify(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    output, exit_code = verify_contract(run_dir, Path(args.contract).resolve())
    print(json.dumps(output, indent=2, sort_keys=True))
    return exit_code


def _report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    if args.format == "json":
        output = render_json(run_dir)
    elif args.format == "html":
        output = render_html(run_dir)
    elif args.format == "sarif":
        output = render_sarif(run_dir)
    else:
        output = render_markdown(run_dir)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(args.output)
    else:
        sys.stdout.write(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="runledger", description="Record and verify observable coding-agent runs.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init = subparsers.add_parser("init", help="create a run directory and capture the initial Git state")
    init.add_argument("--repo", default=".")
    init.add_argument("--run-dir")
    init.add_argument("--run-id")
    init.set_defaults(handler=_init)

    execute = subparsers.add_parser("exec", help="record one command in an initialized run")
    execute.add_argument("--repo")
    execute.add_argument("--run-dir", required=True)
    execute.add_argument("--timeout", type=float)
    execute.add_argument("--pty", action="store_true", help="capture an interactive POSIX command through a pseudo-terminal")
    execute.add_argument("--isolated", action="store_true", help="run the command in a disposable detached Git worktree")
    execute.add_argument("command", nargs=argparse.REMAINDER)
    execute.set_defaults(handler=_exec)

    recover_parser = subparsers.add_parser("recover", help="classify unfinished command events in a run")
    recover_parser.add_argument("--run-dir", required=True)
    recover_parser.set_defaults(handler=_recover)

    compare = subparsers.add_parser("compare", help="compare two recorded runs")
    compare.add_argument("run_a")
    compare.add_argument("run_b")
    compare.add_argument("--format", choices=("markdown", "json"), default="markdown")
    compare.add_argument("--output")
    compare.set_defaults(handler=_compare)

    bundle = subparsers.add_parser("bundle", help="create or verify a portable proof bundle")
    bundle_subparsers = bundle.add_subparsers(dest="bundle_action", required=True)
    bundle_create = bundle_subparsers.add_parser("create")
    bundle_create.add_argument("--run-dir", required=True)
    bundle_create.add_argument("--output", required=True)
    bundle_create.set_defaults(handler=_bundle)
    bundle_verify = bundle_subparsers.add_parser("verify")
    bundle_verify.add_argument("--output", required=True)
    bundle_verify.set_defaults(handler=_bundle)

    verify = subparsers.add_parser("verify", help="evaluate a recorded run against a JSON task contract")
    verify.add_argument("--run-dir", required=True)
    verify.add_argument("--contract", required=True)
    verify.set_defaults(handler=_verify)

    report = subparsers.add_parser("report", help="render a recorded run")
    report.add_argument("--run-dir", required=True)
    report.add_argument("--format", choices=("markdown", "json", "html", "sarif"), default="markdown")
    report.add_argument("--output")
    report.set_defaults(handler=_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
