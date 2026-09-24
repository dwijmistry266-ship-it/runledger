# Changelog

## Unreleased

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
