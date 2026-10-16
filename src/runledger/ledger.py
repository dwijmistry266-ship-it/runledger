"""Append-only run events and content-addressed artifacts.

Every event is fsync'd on write, so the ledger survives a crash between
events; artifacts are stored by relative path with a SHA-256 digest recorded
at write time for later integrity checks.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "runledger.event.v1"


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string with millisecond precision.

    The trailing ``+00:00`` is normalized to ``Z`` so every event timestamp in
    the ledger shares one canonical format.
    """
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    """Serialize ``value`` to JSON with deterministic key order and no whitespace.

    ``sort_keys=True`` plus compact separators keep the ledger stable for
    diffing and hashing across runs and Python versions.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ArtifactStore:
    """Write run artifacts beneath one directory and return stable metadata."""

    def __init__(self, root: Path):
        """Create the artifact root directory (and parents) if it does not exist."""
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, relative_name: str, data: bytes) -> dict[str, Any]:
        """Write ``data`` under ``relative_name`` and return its metadata record.

        The metadata carries the POSIX-style relative path, the SHA-256 hex
        digest of the written bytes, and the byte count. Raises
        :class:`ValueError` when ``relative_name`` is absolute or escapes the
        artifact root via ``..``.
        """
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artifact path must stay inside the run directory")
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        return {"path": relative.as_posix(), "sha256": digest, "bytes": len(data)}

    def write_text(self, relative_name: str, text: str) -> dict[str, Any]:
        """Write ``text`` as UTF-8 (replacing undecodable characters) and return metadata.

        Delegates to :meth:`write_bytes`; returns the same path/digest/size
        metadata record.
        """
        return self.write_bytes(relative_name, text.encode("utf-8", errors="replace"))


class Ledger:
    """An append-only JSONL ledger with monotonic sequence numbers."""

    def __init__(self, run_dir: Path, run_id: str | None = None):
        """Set up a run directory with an append-only event log and artifact store.

        When ``run_id`` is omitted it defaults to the run directory's name.
        The directory (plus ``artifacts/``) is created if it does not exist.
        """
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.run_id = run_id or self.run_dir.name
        self.artifacts = ArtifactStore(self.run_dir / "artifacts")

    def _next_sequence(self) -> int:
        """Return the next free event sequence number (1-based).

        Scans ``events.jsonl`` for the highest recorded ``seq`` and returns one
        higher; returns 1 when the log does not exist yet.
        """
        if not self.events_path.exists():
            return 1
        last = 0
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = int(json.loads(line)["seq"])
        return last + 1

    def append(self, event_type: str, payload: dict[str, Any], *, timestamp: str | None = None) -> dict[str, Any]:
        """Append an event to the ledger and return the written event record.

        The record carries the schema tag, run id, a monotonic ``seq``, the
        timestamp (UTC now unless ``timestamp`` is given), the event ``type``,
        and everything in ``payload``. The line is fsync'd before returning so
        an event is durable once :meth:`append` returns.
        """
        event = {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "seq": self._next_sequence(),
            "timestamp": timestamp or utc_now(),
            "type": event_type,
            **payload,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def events(self) -> Iterable[dict[str, Any]]:
        """Yield the ledger's events in append order as dicts.

        Returns an empty iterable when ``events.jsonl`` does not exist yet;
        blank lines in the file are skipped.
        """
        if not self.events_path.exists():
            return iter(())

        def read() -> Iterable[dict[str, Any]]:
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)

        return read()

    def write_manifest(self, data: dict[str, Any]) -> None:
        """Write ``data`` as canonical JSON to ``run.json`` in the run directory.

        The manifest holds the run's identity and summary metadata; it is a
        single document and is fully overwritten on each call.
        """
        (self.run_dir / "run.json").write_text(canonical_json(data) + "\n", encoding="utf-8")
