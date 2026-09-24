# Changelog

## Unreleased

## 0.3.0a0 — 2026-09-24

Third alpha milestone. The schema and command interface may change before a stable release.

### Added

- Explicit safety limits: `CommandRecorder.run` and `run_pty` reject shell-string commands with `ValueError`; run manifests declare the machine-readable network boundary `"network": "unrestricted"`.
- Concurrent isolation evidence: two simultaneous `--isolated` runs keep separate worktrees and leave the caller's checkout untouched.
- Documented Docker/network position in `docs/SUPPORTED.md`: no network sandbox is provided or implied, and Docker-based execution is not provided.

## 0.2.0a0 — 2026-09-24

Second alpha milestone. The schema and command interface may change before a stable release.

### Added

- Interactive PTY fixtures: `run_pty` accepts optional stdin bytes so REPL-style sessions are genuinely interactive; typed input is recorded only as a byte count, never stored.
- Machine-readable artifact index: report summaries now include an `artifacts` array with path, SHA-256, and byte count for every file beneath `artifacts/` (additive field; `runledger.report.v1` unchanged).
- `docs/VERSIONING.md`: package, tag, and schema-identifier versioning policy with migration notes.

## 0.1.0a0 — 2026-08-26

Initial alpha milestone. The schema and command interface may change before a stable 0.1.0 release.

### Added

- Append-only JSONL event ledger for local command runs.
- Git before/after snapshots and binary-aware working-tree diff capture.
- Redacted stdout/stderr artifacts with per-command paths and SHA-256 metadata.
- JSON task contracts with path-policy, command-exit, and changed-line checks.
- Markdown, JSON, and self-contained offline HTML timeline reports.
- Manifest-backed deterministic ZIP proof bundles with tamper detection.
