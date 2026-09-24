# RunLedger

> **A local-first flight recorder for coding-agent runs.**

RunLedger records what a development command did to a repository: the command, timing, exit status, terminal output, Git state, changed files, and produced artifacts. It turns an opaque agent session into an inspectable, replayable evidence ledger.

RunLedger is not a coding agent, a correctness oracle, or a claim that a process was safe. It records observable behavior and evaluates explicit checks within a declared capture boundary.

## Why it exists

A coding agent can finish with a green test command while still changing out-of-scope files, skipping a required check, retrying a failing command, or leaving behind an unexplained repository state. RunLedger makes those details reviewable after the process exits.

## What it does

RunLedger is local-first and dependency-light (standard library only):

- record a command run as append-only JSONL events;
- capture Git before/after evidence and changed files;
- hash stored artifacts and redact common credential-shaped values;
- capture interactive output through a POSIX pseudo-terminal (`--pty`), including genuinely interactive fixtures;
- recover interrupted runs as `incomplete` rather than passed (`runledger recover`);
- run in a disposable detached Git worktree (`--isolated`); the caller’s checkout is not mutated;
- evaluate explicit JSON task contracts with pass, fail, not-run, unknown, and incomplete states;
- compare two recorded runs without interpreting hidden model reasoning;
- build commands for local agent CLIs through conformance-checked adapters (`docs/ADAPTERS.md`);
- render Markdown, JSON, SARIF, and an offline HTML replay timeline with event-type filters;
- export manifest-backed proof bundles with tamper detection;
- run in CI through the published GitHub Action (`action.yml`), including SARIF upload for failed contracts.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

# Capture the repository state before a task.
runledger init --repo . --run-dir .runledger/demo --run-id demo

# Record a command without shell interpolation.
runledger exec --repo . --run-dir .runledger/demo -- python3 -c "print('hello')"

# Capture interactive output through a POSIX pseudo-terminal.
runledger exec --repo . --run-dir .runledger/interactive --pty -- python3 -i

# Run in a disposable detached worktree; the caller’s checkout is not mutated.
runledger exec --repo . --run-dir .runledger/isolated --isolated -- python3 -c "open('agent-output.txt', 'w').write('captured')"

# Classify a run that ended without command.completed.
runledger recover --run-dir .runledger/demo

# Check the recorded run against an explicit contract.
runledger verify --run-dir .runledger/demo --contract fixtures/basic-task/task.json

# Produce Markdown, JSON, or a self-contained offline HTML timeline.
runledger report --run-dir .runledger/demo --format markdown --output report.md
runledger report --run-dir .runledger/demo --format html --output run.html

# Compare two recorded runs.
runledger compare .runledger/demo-a .runledger/demo-b --format markdown --output comparison.md

# Export and verify a portable proof bundle.
runledger bundle create --run-dir .runledger/demo --output demo-proof.zip
runledger bundle verify --output demo-proof.zip
```

RunLedger writes `events.jsonl`, `run.json`, `artifacts/`, and `checks.json` beneath the run directory. The HTML output can be opened directly from a file without a server or hosted account. The proof bundle contains a manifest of SHA-256 digests and fails verification if a member is altered. The project ships runnable fixtures rather than relying on screenshots or simulated output.

## What a run contains

| Evidence | Example |
|---|---|
| Process events | `run.initialized`, `command.started`, `command.completed`, `verification.completed` |
| Terminal artifacts | Redacted stdout and stderr with unique per-command paths and hashes. |
| Git evidence | Repository availability, HEAD, branch, porcelain status, and binary-aware diff. |
| Contract checks | `pass`, `fail`, `not-run`, `unknown`, and `incomplete` outcomes from explicit JSON checks. |
| Portable output | Markdown, JSON, offline HTML timeline, and manifest-backed ZIP bundle. |

## Design principles

RunLedger uses plain files, explicit boundaries, deterministic checks, and human-readable evidence. Missing evidence is reported as `not-run` or `unknown`, never silently promoted to a pass. RunLedger captures command output into redacted artifacts, but recorded data should still be reviewed before sharing because redaction is not a guarantee against private business data.

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash examples/basic-demo.sh
bash tests/test_action.sh
```

Read [supported environments](docs/SUPPORTED.md), the [security model](docs/SECURITY.md), the [event schema](docs/event-schema.md), and the [stable-release gates](docs/STABLE_RELEASE_GATES.md) before depending on RunLedger output.

## Non-goals

RunLedger does not certify correctness or security, inspect private model reasoning, or upload repository contents to a hosted service. Standard execution records the command in the current checkout; use `--isolated` for disposable Git worktree execution. PTY capture is POSIX-only, and no network sandbox is implied by the recorder.

## Status

Prerelease: `1.0.0a0`. The event schema identifiers (`runledger.event.v1`, `runledger.report.v1`, `runledger.checks.v1`, `runledger.bundle.v1`, `runledger.recovery.v1`) are frozen per `docs/VERSIONING.md`. The stable `1.0.0` tag is reserved until the adoption gate is met: at least one real external trial producing reproducible feedback or a documented bug fix. PTY capture is POSIX-only; the regular recorder is the documented fallback on other platforms.

## License

MIT. See [LICENSE](LICENSE).
