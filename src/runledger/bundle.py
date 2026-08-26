"""Build and verify portable, manifest-backed RunLedger bundles."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .ledger import canonical_json


BUNDLE_SCHEMA = "runledger.bundle.v1"


def _safe_relative(path: str) -> PurePosixPath:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe bundle path: {path}")
    return relative


def _files(run_dir: Path) -> list[Path]:
    return sorted((path for path in run_dir.rglob("*") if path.is_file()), key=lambda path: path.relative_to(run_dir).as_posix())


def build_bundle(run_dir: Path, output: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    output = output.resolve()
    if not run_dir.is_dir():
        raise ValueError(f"run directory does not exist: {run_dir}")
    entries: list[dict[str, Any]] = []
    file_bytes: dict[str, bytes] = {}
    for path in _files(run_dir):
        relative = path.relative_to(run_dir).as_posix()
        if output == path.resolve():
            continue
        data = path.read_bytes()
        file_bytes[relative] = data
        entries.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    manifest = {"schema": BUNDLE_SCHEMA, "files": entries}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(file_bytes):
            info = zipfile.ZipInfo(relative, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, file_bytes[relative])
        info = zipfile.ZipInfo("MANIFEST.json", date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        archive.writestr(info, canonical_json(manifest) + "\n")
    return manifest


def verify_bundle(bundle: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            names = archive.namelist()
            if "MANIFEST.json" not in names:
                return False, ["MANIFEST.json is missing"]
            manifest = json.loads(archive.read("MANIFEST.json").decode("utf-8"))
            if manifest.get("schema") != BUNDLE_SCHEMA:
                errors.append("unsupported bundle schema")
            listed = {entry.get("path"): entry for entry in manifest.get("files", [])}
            for name in names:
                try:
                    _safe_relative(name)
                except ValueError as exc:
                    errors.append(str(exc))
            for relative, entry in listed.items():
                if relative not in names:
                    errors.append(f"missing member: {relative}")
                    continue
                data = archive.read(relative)
                actual = hashlib.sha256(data).hexdigest()
                if actual != entry.get("sha256"):
                    errors.append(f"hash mismatch: {relative}")
                if len(data) != entry.get("bytes"):
                    errors.append(f"size mismatch: {relative}")
            unexpected = set(names) - set(listed) - {"MANIFEST.json"}
            errors.extend(f"unmanifested member: {name}" for name in sorted(unexpected))
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, [f"invalid bundle: {exc}"]
    return not errors, errors
