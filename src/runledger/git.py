"""Safe Git inspection helpers for local run evidence."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitSnapshot:
    available: bool
    head: str | None
    branch: str | None
    status: list[str]
    diff_stat: str | None
    error: str | None = None


def _run_git(repo: Path, args: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", "-c", "color.ui=false", "-C", str(repo), *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)
    return result.returncode, result.stdout, result.stderr


def snapshot(repo: Path) -> GitSnapshot:
    repo = repo.resolve()
    code, head, error = _run_git(repo, ["rev-parse", "HEAD"])
    if code != 0:
        return GitSnapshot(False, None, None, [], None, error.strip() or "not a Git repository")
    _, branch, _ = _run_git(repo, ["branch", "--show-current"])
    _, status, _ = _run_git(repo, ["status", "--porcelain=v1", "-uall"])
    _, diff_stat, _ = _run_git(repo, ["diff", "--stat"])
    return GitSnapshot(
        True,
        head.strip() or None,
        branch.strip() or None,
        status.splitlines(),
        diff_stat.strip() or None,
    )


def diff(repo: Path) -> str:
    repo = repo.resolve()
    code, output, error = _run_git(repo, ["diff", "--binary"], timeout=20.0)
    if code != 0:
        raise RuntimeError(error.strip() or "git diff failed")
    _, untracked, _ = _run_git(repo, ["ls-files", "--others", "--exclude-standard", "-z"], timeout=10.0)
    for relative in (item for item in untracked.split("\x00") if item):
        untracked_code, untracked_diff, untracked_error = _run_git(
            repo, ["diff", "--no-index", "--binary", "--", "/dev/null", relative], timeout=20.0
        )
        if untracked_code not in (0, 1):
            raise RuntimeError(untracked_error.strip() or f"unable to diff untracked file: {relative}")
        output += untracked_diff
    return output
