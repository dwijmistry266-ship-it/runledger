"""Capture a command as observable ledger events."""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Sequence

from .ledger import Ledger
from .redact import redact, redact_argv


class CommandRecorder:
    def __init__(self, ledger: Ledger, *, cwd: Path | None = None):
        self.ledger = ledger
        self.cwd = cwd or Path.cwd()

    def run(self, argv: Sequence[str], *, timeout: float | None = None) -> int:
        if not argv:
            raise ValueError("a command is required")
        raw_argv = list(argv)
        display_argv, command_redactions = redact_argv(raw_argv)
        command_display = " ".join(display_argv)
        command_hash = hashlib.sha256("\0".join(raw_argv).encode("utf-8")).hexdigest()
        started = time.monotonic()
        started_event = self.ledger.append(
            "command.started",
            {
                "actor": "runledger",
                "cwd": str(self.cwd.resolve()),
                "argv": display_argv,
                "command_display": command_display,
                "command_sha256": command_hash,
                "redaction_count": command_redactions,
            },
        )
        try:
            process = subprocess.run(
                raw_argv,
                cwd=self.cwd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            exit_code = process.returncode
            stdout = process.stdout.decode("utf-8", errors="replace") if isinstance(process.stdout, bytes) else process.stdout
            stderr = process.stderr.decode("utf-8", errors="replace") if isinstance(process.stderr, bytes) else process.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            stderr += "\n[runledger] command timed out\n"
            timed_out = True
        except OSError as exc:
            exit_code = 127
            stdout = ""
            stderr = f"[runledger] unable to start command: {exc}\n"
            timed_out = False
        clean_stdout, stdout_redactions = redact(stdout)
        clean_stderr, stderr_redactions = redact(stderr)
        stdout_meta = self.ledger.artifacts.write_text(f"stdout-{started_event['seq']}.txt", clean_stdout)
        stderr_meta = self.ledger.artifacts.write_text(f"stderr-{started_event['seq']}.txt", clean_stderr)
        duration_ms = int((time.monotonic() - started) * 1000)
        self.ledger.append(
            "command.completed",
            {
                "actor": "runledger",
                "cwd": str(self.cwd.resolve()),
                "command_display": command_display,
                "command_sha256": command_hash,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "stdout": stdout_meta,
                "stderr": stderr_meta,
                "redaction_count": command_redactions + stdout_redactions + stderr_redactions,
            },
        )
        return exit_code
