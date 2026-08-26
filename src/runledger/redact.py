"""Conservative redaction for common credential-shaped values."""

from __future__ import annotations

import re


_PATTERNS = (
    re.compile(r"(?i)(\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)\b\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"\b(?:ghp|gho|github_pat|sk|xox[baprs])_[A-Za-z0-9_\-]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
)


def redact(text: str) -> tuple[str, int]:
    """Return redacted text and the number of replacement operations."""
    count = 0

    def replace_assignment(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return match.group(1) + "[REDACTED]"

    text = _PATTERNS[0].sub(replace_assignment, text)
    for pattern in _PATTERNS[1:]:
        text, replacements = pattern.subn("[REDACTED]", text)
        count += replacements
    return text, count


def redact_argv(argv: list[str]) -> tuple[list[str], int]:
    redacted: list[str] = []
    total = 0
    for item in argv:
        clean, count = redact(item)
        redacted.append(clean)
        total += count
    return redacted, total
