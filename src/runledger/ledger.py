"""Append-only run events and content-addressed artifacts."""

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
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ArtifactStore:
    """Write run artifacts beneath one directory and return stable metadata."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, relative_name: str, data: bytes) -> dict[str, Any]:
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artifact path must stay inside the run directory")
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        return {"path": relative.as_posix(), "sha256": digest, "bytes": len(data)}

    def write_text(self, relative_name: str, text: str) -> dict[str, Any]:
        return self.write_bytes(relative_name, text.encode("utf-8", errors="replace"))


class Ledger:
    """An append-only JSONL ledger with monotonic sequence numbers."""

    def __init__(self, run_dir: Path, run_id: str | None = None):
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.run_id = run_id or self.run_dir.name
        self.artifacts = ArtifactStore(self.run_dir / "artifacts")

    def _next_sequence(self) -> int:
        if not self.events_path.exists():
            return 1
        last = 0
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = int(json.loads(line)["seq"])
        return last + 1

    def append(self, event_type: str, payload: dict[str, Any], *, timestamp: str | None = None) -> dict[str, Any]:
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
        if not self.events_path.exists():
            return iter(())

        def read() -> Iterable[dict[str, Any]]:
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)

        return read()

    def write_manifest(self, data: dict[str, Any]) -> None:
        (self.run_dir / "run.json").write_text(canonical_json(data) + "\n", encoding="utf-8")
