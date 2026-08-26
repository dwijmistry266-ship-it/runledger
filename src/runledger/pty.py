"""PTY-backed command capture for interactive and line-oriented tools."""

from __future__ import annotations

import errno
import hashlib
import os
import pty
import select
import signal
import subprocess
import time
from pathlib import Path
from typing import Sequence

from .ledger import Ledger
from .redact import redact, redact_argv


class PtyUnavailable(RuntimeError):
    """Raised when the host cannot provide a POSIX pseudo-terminal."""


def run_pty(ledger: Ledger, argv: Sequence[str], *, cwd: Path | None = None, timeout: float | None = None) -> int:
    """Run argv under a PTY and record one ordered terminal transcript.

    PTY support is intentionally POSIX-only. Callers should use the regular
    recorder on Windows or another host where ``pty`` is unavailable.
    """
    if os.name != "posix":
        raise PtyUnavailable("PTY capture is only available on POSIX hosts")
    if not argv:
        raise ValueError("a command is required")
    raw_argv = list(argv)
    display_argv, command_redactions = redact_argv(raw_argv)
    command_hash = hashlib.sha256("\0".join(raw_argv).encode("utf-8")).hexdigest()
    started = time.monotonic()
    master, slave = pty.openpty()
    process: subprocess.Popen[bytes] | None = None
    chunks: list[bytes] = []
    timed_out = False
    try:
        process = subprocess.Popen(
            raw_argv,
            cwd=cwd or Path.cwd(),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave)
        slave = -1
        started_event = ledger.append(
            "command.started",
            {
                "capture": "pty",
                "cwd": str((cwd or Path.cwd()).resolve()),
                "argv": display_argv,
                "command_display": " ".join(display_argv),
                "command_sha256": command_hash,
                "redaction_count": command_redactions,
            },
        )
        deadline = started + timeout if timeout is not None else None
        while True:
            if deadline is not None and time.monotonic() >= deadline and process.poll() is None:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            readable, _, _ = select.select([master], [], [], 0.05)
            if readable:
                try:
                    chunks.append(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
            if process.poll() is not None:
                try:
                    while True:
                        chunks.append(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                break
        raw_output = b"".join(chunks).decode("utf-8", errors="replace")
        output, output_redactions = redact(raw_output)
        artifact = ledger.artifacts.write_text(f"pty-{started_event['seq']}.log", output)
        exit_code = 124 if timed_out else (process.returncode if process.returncode is not None else 1)
        ledger.append(
            "command.completed",
            {
                "capture": "pty",
                "cwd": str((cwd or Path.cwd()).resolve()),
                "command_display": " ".join(display_argv),
                "command_sha256": command_hash,
                "exit_code": exit_code,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": timed_out,
                "transcript": artifact,
                "redaction_count": command_redactions + output_redactions,
            },
        )
        return exit_code
    except BaseException:
        # Deliberately leave command.started without command.completed: the
        # recovery path must classify this run as incomplete.
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        raise
    finally:
        if slave != -1:
            os.close(slave)
        os.close(master)
