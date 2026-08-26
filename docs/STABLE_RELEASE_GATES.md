# Stable release gates

RunLedger will not be called stable because it has a polished README or a passing happy-path demo. The stable release must satisfy the following gates.

| Gate | Required behavior | Evidence required |
|---|---|---|
| Interactive capture | Record line-oriented and interactive subprocess output without losing ordering or terminal completion state. | PTY fixture tests on Linux, with a documented fallback on platforms without PTY support. |
| Crash recovery | A killed or interrupted process leaves a ledger that is classified as incomplete rather than passed. | Forced interruption fixture, recovery command, and report test. |
| Repository isolation | A run can execute in a disposable Git worktree without mutating the caller’s checkout. | Before/after hash tests, concurrent-run test, and explicit cleanup behavior. |
| Safety controls | No shell interpolation by default; command, network, filesystem, and output boundaries are explicit. | Threat model, negative tests, and clear CLI warnings. |
| Contract verification | Required checks distinguish pass, fail, not-run, unknown, and incomplete states. | Contract fixtures for each state and non-zero CI exit behavior. |
| Adapter interface | At least two local command adapters produce the same versioned event vocabulary. | Adapter conformance suite and sample recorded runs. |
| Portable evidence | Reports and proof bundles can be consumed offline and verify their artifact hashes. | Clean-install demo, tamper test, and schema documentation. |
| CI integration | A repository can run RunLedger on a declared contract without leaking secrets or executing untrusted commands by default. | Reusable Action fixture and workflow self-test. |
| Compatibility | Supported Python and operating-system versions are tested, and schema changes are versioned. | Matrix CI, package smoke tests, migration notes, and supported-platform document. |
| Adoption evidence | At least one external trial produces reproducible feedback or a documented bug fix. | Linked issue, reproduction, or review—not merely stars or impressions. |

## Explicit non-gates

RunLedger does not need a hosted dashboard, a proprietary model API, automatic claims about agent intelligence, or a large star count to be technically complete. Those may be future distribution choices, not substitutes for capture fidelity, safety, and reproducibility.
