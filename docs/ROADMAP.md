# Roadmap

RunLedger is being built in narrow, testable milestones. A feature is not considered complete because a screenshot looks convincing; it must have a fixture, a documented boundary, and a reproducible command.

| Milestone | Scope | Exit evidence | Status |
|---|---|---|---|
| **v0.1 alpha** | JSONL ledger, command recorder, Git snapshots, redaction, contracts, reports, comparison, proof bundles, demo | Green regression suite, passing demo, offline HTML, verified bundle. | ✅ Released `v0.1.0a0` |
| v0.2 | PTY capture, crash/incomplete-run recovery, richer artifact index, viewer timeline filters | Interactive CLI fixture and crash-recovery tests. | ✅ Released `v0.2.0a0` |
| v0.3 | Worktree isolation and explicit safety boundaries | Two concurrent runs remain isolated; safety limits are explicit. | ✅ Released `v0.3.0a0` |
| v0.4 | Agent adapters for selected local CLIs and adapter conformance tests | At least two adapters produce the same event contract. | ✅ Released `v0.4.0a0` |
| v0.5 | GitHub Action and SARIF findings for failed contracts | Clean public workflow and fixture self-test. | ✅ Released `v0.5.0a0` |
| v1.0 | Stable event schema, portable bundle compatibility, platform matrix, security review | Reproducible package, migration notes, platform matrix, recorded security review. | 🟡 Prerelease `v1.0.0a0`; stable `1.0.0` waits on a real external trial (see `docs/STABLE_RELEASE_GATES.md`) |

The project will not claim to evaluate hidden model reasoning, certify code correctness, or make arbitrary command execution safe. Those limitations remain part of the product design, not temporary omissions.
