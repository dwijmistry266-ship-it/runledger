# Changelog

## Unreleased

## 1.0.0a0 — 2026-09-24

Prerelease of the 1.0 line. All schema identifiers (`runledger.event.v1`, `runledger.run.v1`, `runledger.checks.v1`, `runledger.report.v1`, `runledger.bundle.v1`, `runledger.recovery.v1`) are frozen per `docs/VERSIONING.md`; migration notes there confirm no migration is required from any alpha. The stable `1.0.0` tag is reserved until the adoption gate is met: at least one real external trial producing reproducible feedback or a documented bug fix.

### Added

- Platform matrix CI: the test suite runs on Ubuntu, macOS, and Windows across Python 3.11–3.13; suite commands use the running interpreter instead of a hardcoded `python3`.
- Bundle compatibility evidence: verification explicitly rejects unknown bundle schemas (tested); bundles verify across package versions sharing the schema identifier.
- Security review (`docs/SECURITY.md`): full-scope review with no blocking findings; residual risks documented.
- Documentation now matches the software: README describes shipped capabilities, `docs/event-schema.md` lists all event types, `docs/VERSIONING.md` defines the versioning policy.

## 0.5.0a0 — 2026-09-24

Fifth alpha milestone. The schema and command interface may change before a stable release.

### Added

- Contract-driven Action self-test: the self-test workflow and the local harness (`tests/test_action.sh`) now exercise the `contract` input, asserting that a failed contract produces SARIF findings (`runledger/required-command`) and a `failed` status.
- `fixtures/action-contract/task.json`: fixture contract for the Action's SARIF path.

## 0.4.0a0 — 2026-09-24

Fourth alpha milestone. The schema and command interface may change before a stable release.

### Added

- Adapter conformance on the event contract: the suite records commands built by both shipped adapters and asserts identical event vocabulary (types, order, payload key sets).
- `docs/ADAPTERS.md`: the adapter interface, the two supported CLI shapes, validation rules, and conformance semantics.

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
