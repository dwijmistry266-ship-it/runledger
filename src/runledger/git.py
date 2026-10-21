"""Safe Git inspection helpers for local run evidence.

Everything here is read-only: the module never runs a Git command that
writes, stages, or mutates the repository. All invocations are funneled
through :func:`_run_git`, which disables color output, never raises, and
times out instead of hanging a run when Git is wedged.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitSnapshot:
    """Point-in-time Git state captured around a run.

    A frozen record: taking another snapshot never mutates this one.

    ``available`` is ``True`` when ``repo`` is a Git repository Git can
    read; when ``False``, ``error`` explains why (e.g. ``"not a Git
    repository"``) and the remaining fields are empty/``None``.
    ``head`` is the full commit SHA of ``HEAD``, or ``None`` in an empty
    repository with no commits yet. ``branch`` is the current branch name,
    or ``None`` when ``HEAD`` is detached (or the repository is empty).
    ``status`` holds one ``git status --porcelain=v1`` line per changed or
    untracked path (``-uall``: untracked files listed individually), empty
    when the worktree is clean. ``diff_stat`` is the ``git diff --stat``
    summary of tracked changes, or ``None`` when there are none.
    """

    available: bool
    head: str | None
    branch: str | None
    status: list[str]
    diff_stat: str | None
    error: str | None = None


def _run_git(repo: Path, args: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    """Run one Git command against ``repo`` and return ``(code, stdout, stderr)``.

    Never raises: a missing ``git`` binary or an expired timeout yields
    ``(1, "", <message>)`` so callers can degrade into a
    ``GitSnapshot(available=False, ...)`` instead of crashing the run.

    ``color.ui=false`` is forced on every invocation so color escape codes
    never leak into captured output or stored snapshots. The timeout
    defaults to 10 seconds; callers pass a longer one for commands that
    legitimately scan more history (e.g. full diffs).
    """
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
    """Capture the Git state of ``repo`` (resolved to an absolute path first).

    ``repo`` need not be a repository: when ``git rev-parse HEAD`` fails,
    the result is ``GitSnapshot(available=False, ..., error=<reason>)`` so
    callers can record "git was unavailable" as run metadata rather than
    aborting. A blank ``HEAD`` or branch becomes ``None`` (empty repo /
    detached ``HEAD``); a blank ``diff --stat`` likewise becomes ``None``.
    Branch, status (with untracked files, ``-uall``), and diff-stat reads
    are best-effort after a successful ``rev-parse`` — their individual
    failures simply leave the corresponding field empty.
    """
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
    """Return the full binary diff of ``repo``'s working-tree changes.

    Covers both tracked changes (``git diff --binary``, i.e. unstaged
    working-tree changes) and untracked files, each untracked file
    rendered via ``git diff --no-index --binary -- /dev/null <file>`` and
    appended. Returns an empty string when the worktree is clean.

    Raises:
        RuntimeError: when the initial ``git diff`` fails, or when
            diffing an untracked file fails. Note the exit-code asymmetry
            handled here: a plain ``git diff`` exits 0 even when
            differences exist (only ``--exit-code``/``--quiet`` turn
            differences into exit 1), so only a nonzero code means
            failure — while ``git diff --no-index`` exits 1 on real
            differences, so codes 0 *and* 1 are accepted for untracked
            files and only anything else raises.

    ``repo`` is resolved to an absolute path first, matching
    :func:`snapshot`. The 20-second timeout on the tracked diff and
    10-second timeout per untracked file keep large worktrees from
    stalling a run.
    """
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
