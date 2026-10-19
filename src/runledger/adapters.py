"""Conformance-friendly adapters for local coding-agent command lines.

An adapter turns a plain-text task plus a repository path into a concrete
executable argv (`AdapterCommand`) that the CLI can record, redact, and
replay like any other command. Two adapters ship: `PromptArgumentAdapter`
for agents that take the task as one argument, and `PromptFileAdapter` for
agents that read the task from a prepared file. `conformance_check` is the
acceptance test any custom adapter must pass (deterministic builds, shell-
safe argv, metadata echo) before it can drive a recorded run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


_SHELL_META = re.compile(r"[;&|<>`$()]")


@dataclass(frozen=True)
class AdapterCommand:
    """A ready-to-exec command line produced by an adapter.

    `adapter` names the adapter that built it, `argv` is the full command
    line (executed directly, never through a shell), `task` is the original
    task text the run records, and `repo` is the resolved absolute path of
    the repository boundary the command must stay inside. Frozen so a
    recorded command cannot be mutated after the fact.
    """

    adapter: str
    argv: tuple[str, ...]
    task: str
    repo: str


class CommandAdapter(Protocol):
    """Protocol every adapter must implement.

    `name` identifies the adapter in logs and bundles. `build` must be a
    pure function of its inputs: same `(task, repo)` always yields the same
    `AdapterCommand` (`conformance_check` enforces this determinism).
    """

    name: str

    def build(self, task: str, repo: Path) -> AdapterCommand:
        """Build the command line for `task` rooted at `repo`.

        Must raise `ValueError` for inputs it cannot represent (e.g. an
        empty task) rather than returning a broken command.
        """

        ...


@dataclass(frozen=True)
class PromptArgumentAdapter:
    """Adapter for agents that accept the task as one argument."""

    executable: str
    fixed_args: tuple[str, ...] = ()
    name: str = "prompt-argument"

    def build(self, task: str, repo: Path) -> AdapterCommand:
        """Build `argv` as `executable + fixed_args + [task]`.

        Raises `ValueError` when `task` is blank. The task travels as one
        trailing argument, so agents that take a free-text prompt work
        unchanged; `repo` is stored as the resolved absolute boundary path.
        """
        if not task.strip():
            raise ValueError("task must not be empty")
        argv = (self.executable, *self.fixed_args, task)
        return AdapterCommand(self.name, argv, task, str(repo.resolve()))


@dataclass(frozen=True)
class PromptFileAdapter:
    """Adapter for agents that accept a path to a prepared task file."""

    executable: str
    prompt_flag: str = "--prompt-file"
    fixed_args: tuple[str, ...] = ()
    name: str = "prompt-file"

    def build(self, task: str, repo: Path) -> AdapterCommand:
        """Build `argv` as `executable + fixed_args + [prompt_flag, path]`.

        Here `task` is interpreted as the prompt's path *inside the run
        boundary*, not literal text: absolute paths and `..` segments are
        rejected with `ValueError` (as is a blank task), so a prompt file
        can never point outside the recorded repo. `repo` is stored as the
        resolved absolute boundary path.
        """
        if not task.strip():
            raise ValueError("task must not be empty")
        prompt_path = Path(task)
        if prompt_path.is_absolute() or ".." in prompt_path.parts:
            raise ValueError("prompt file must be a relative path inside the run boundary")
        argv = (self.executable, *self.fixed_args, self.prompt_flag, prompt_path.as_posix())
        return AdapterCommand(self.name, argv, task, str(repo.resolve()))


def validate_adapter_command(command: AdapterCommand) -> list[str]:
    """Statically validate an adapter-built command; return the error list.

    An empty list means the command is valid. Checks: a non-empty adapter
    name, an argv whose first element is an executable, no shell
    metacharacters (`;`, `&`, `|`, `<`, `>`, backtick, `$`, parens) in the
    executable or fixed args — the *last* argv element is exempt because it
    carries the free-text task or prompt path — and a non-empty repo
    boundary. This runs before anything executes, not after a failure.
    """
    errors: list[str] = []
    if not command.adapter:
        errors.append("adapter name is empty")
    if not command.argv or not command.argv[0]:
        errors.append("argv must contain an executable")
    if any(_SHELL_META.search(item) for item in command.argv[:-1]):
        errors.append("shell metacharacters are not allowed in executable or fixed arguments")
    if not command.repo:
        errors.append("repo is empty")
    return errors


def conformance_check(adapter: CommandAdapter, task: str, repo: Path) -> tuple[bool, list[str]]:
    """Acceptance test every adapter must pass: return `(ok, errors)`.

    Builds the command twice and requires: both builds succeed (a `build`
    that raises `OSError`/`ValueError` fails the check), the result passes
    `validate_adapter_command`, the two builds are identical (determinism —
    adapters must be pure functions of `(task, repo)`), and the command's
    `task`/`repo` metadata echoes the request exactly. Custom adapters must
    pass this before driving a recorded run.
    """
    try:
        first = adapter.build(task, repo)
        second = adapter.build(task, repo)
    except (OSError, ValueError) as exc:
        return False, [str(exc)]
    errors = validate_adapter_command(first)
    if first != second:
        errors.append("adapter output is not deterministic")
    if first.task != task or first.repo != str(repo.resolve()):
        errors.append("adapter metadata does not match the request")
    return not errors, errors
