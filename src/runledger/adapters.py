"""Conformance-friendly adapters for local coding-agent command lines."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


_SHELL_META = re.compile(r"[;&|<>`$()]")


@dataclass(frozen=True)
class AdapterCommand:
    adapter: str
    argv: tuple[str, ...]
    task: str
    repo: str


class CommandAdapter(Protocol):
    name: str

    def build(self, task: str, repo: Path) -> AdapterCommand:
        ...


@dataclass(frozen=True)
class PromptArgumentAdapter:
    """Adapter for agents that accept the task as one argument."""

    executable: str
    fixed_args: tuple[str, ...] = ()
    name: str = "prompt-argument"

    def build(self, task: str, repo: Path) -> AdapterCommand:
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
        if not task.strip():
            raise ValueError("task must not be empty")
        prompt_path = Path(task)
        if prompt_path.is_absolute() or ".." in prompt_path.parts:
            raise ValueError("prompt file must be a relative path inside the run boundary")
        argv = (self.executable, *self.fixed_args, self.prompt_flag, prompt_path.as_posix())
        return AdapterCommand(self.name, argv, task, str(repo.resolve()))


def validate_adapter_command(command: AdapterCommand) -> list[str]:
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
