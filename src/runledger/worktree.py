"""Disposable Git worktrees for isolated command execution."""

from __future__ import annotations

import subprocess
from pathlib import Path


class WorktreeError(RuntimeError):
    """Raised when an isolated worktree cannot be created or removed."""


class Worktree:
    def __init__(self, repository: Path, path: Path):
        self.repository = repository.resolve()
        self.path = path.resolve()
        self.created = False

    def create(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "-c", "color.ui=false", "-C", str(self.repository), "worktree", "add", "--detach", str(self.path), "HEAD"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise WorktreeError(result.stderr.strip() or "git worktree add failed")
        self.created = True
        return self.path

    def remove(self) -> None:
        if not self.created:
            return
        result = subprocess.run(
            ["git", "-c", "color.ui=false", "-C", str(self.repository), "worktree", "remove", "--force", str(self.path)],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise WorktreeError(result.stderr.strip() or "git worktree remove failed")
        self.created = False
