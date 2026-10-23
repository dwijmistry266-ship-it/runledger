"""Build and verify portable, manifest-backed RunLedger bundles.

A bundle is a deterministic ``.zip`` archive of one run directory: every file
is hashed (SHA-256) and listed in an embedded ``MANIFEST.json`` alongside the
bundle schema identifier (``BUNDLE_SCHEMA``), so a bundle can be checked for
tampering or corruption with :func:`verify_bundle`. Determinism comes from a
fixed archive timestamp (2020-01-01 00:00:00 UTC) and fixed file permissions
(``0o600``) on every member, including the manifest — two bundles built from
identical run directories are byte-identical.

The manifest never contains secrets handling of its own; it only records
``path``, ``sha256``, and ``bytes`` per member. Extraction is deliberately not
offered here — every member path is checked by :func:`_safe_relative` during
verification, but reading bytes out of the archive is left to callers that know
their destination is safe."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .ledger import canonical_json


BUNDLE_SCHEMA = "runledger.bundle.v1"
"""Schema identifier stamped into every bundle manifest.

Frozen since the 1.0.0a0 prerelease (see ``docs/VERSIONING.md``):
:func:`verify_bundle` rejects any bundle whose manifest carries a different
value."""


def _safe_relative(path: str) -> PurePosixPath:
    """Validate a bundle member path, rejecting zip-slip escapes.

    Absolute paths and any path containing a ``..`` component raise
    ``ValueError``; anything else is returned as a ``PurePosixPath`` so
    archive members stay portable across platforms regardless of which OS
    built the bundle.
    """
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe bundle path: {path}")
    return relative


def _files(run_dir: Path) -> list[Path]:
    """List every file under *run_dir*, recursively, in deterministic order.

    Files are sorted by their POSIX relative path so the manifest entry order
    and archive member order are identical on every build.
    """
    return sorted((path for path in run_dir.rglob("*") if path.is_file()), key=lambda path: path.relative_to(run_dir).as_posix())


def build_bundle(run_dir: Path, output: Path) -> dict[str, Any]:
    """Build a bundle archive of *run_dir* at *output* and return its manifest.

    Both paths are resolved before use. Raises ``ValueError`` if *run_dir* is
    not a directory. Parent directories of *output* are created as needed.

    If *output* lives inside *run_dir* (the common case), that file is
    skipped so the bundle never contains itself. Every other file is stored
    deflated with the fixed timestamp and permissions described in the module
    docstring, followed by ``MANIFEST.json`` (canonical JSON plus a trailing
    newline) with the shape ``{"schema": BUNDLE_SCHEMA, "files": [...]}``,
    where each file entry is ``{"path": <posix relpath>, "sha256": <hex>,
    "bytes": <int>}``.

    Returns the manifest dict — the same object serialized into the archive —
    so callers can log or persist it without re-reading the zip.
    """
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
    """Verify a bundle archive, returning ``(ok, errors)``.

    ``ok`` is ``True`` only when the bundle is a readable zip that contains
    ``MANIFEST.json`` with the current ``BUNDLE_SCHEMA`` and every member
    passes all checks. ``errors`` accumulates one human-readable message per
    problem found, so callers get the full damage report in a single pass
    instead of stopping at the first failure:

    - ``"MANIFEST.json is missing"`` — returned immediately, alone, when the
      archive has no manifest.
    - ``"unsupported bundle schema"`` — manifest schema differs from
      ``BUNDLE_SCHEMA``.
    - zip-slip guard — every member name (manifest included) is run through
      :func:`_safe_relative`; unsafe names are reported as errors.
    - per manifest entry: ``"missing member: <path>"`` (listed but absent),
      ``"hash mismatch: <path>"`` (bytes differ from the recorded SHA-256),
      ``"size mismatch: <path>"`` (byte length differs from the recorded
      size).
    - ``"unmanifested member: <name>"`` — archive member not listed in the
      manifest (excluding ``MANIFEST.json`` itself).

    A corrupt zip, undecodable manifest bytes, or unparseable manifest JSON
    short-circuits to ``(False, ["invalid bundle: <reason>"])``. Verification
    never raises on malformed bundles — it only raises for programmer errors
    (e.g. passing a non-path-like argument).
    """
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
