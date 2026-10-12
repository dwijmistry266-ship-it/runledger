# FAQ — newcomers start here

## 1. What is RunLedger, and what isn't it?

RunLedger is a local-first flight recorder for coding-agent runs: it records
what a development command did to a repository — the command, timing, exit
status, terminal output, Git state before and after, changed files, and any
artifacts it produced — and turns an opaque session into an inspectable,
replayable evidence ledger.

It is **not** a coding agent, a correctness oracle, or a claim that a process
was safe. It records observable behavior and evaluates explicit checks within
a declared capture boundary. A run with green test output can still show
out-of-scope file changes, skipped checks, or retried commands when you read
the ledger — that is the point.

## 2. Does anything I record leave my machine?

No. RunLedger is local-first and dependency-light (standard library only).
Everything is written as plain files beneath the run directory you chose:
`events.jsonl`, `run.json`, `artifacts/`, and `checks.json`. There is no
account, no server, no telemetry, and the offline HTML timeline opens straight
from a file. The one exception is your own doing: if you choose to share a
run directory or a proof bundle (ZIP), that is an explicit export.

## 3. What exactly does `runledger exec` do to my command?

It runs your command with **your** user's permissions — RunLedger is an
evidence recorder, not a sandbox, and it does not make arbitrary code safe
merely by recording it. Commands are passed as argument arrays; they are
never interpolated into a shell (`shell=True` is never used, and shell-string
input is rejected). RunLedger captures the argument vector, working
directory, exit status, duration, and stdout/stderr, and snapshots Git state
before and after. It writes only beneath the selected run directory.

Use a dedicated test environment for untrusted code, the same as you would
without RunLedger.

## 4. Will RunLedger keep my secrets out of the recorded output?

Common credential-shaped values are replaced with placeholders before terminal
artifacts are written — but treat redaction as a **safety net, not a
guarantee**. Full output capture can still contain sensitive business data
that is not shaped like a token, and new secret formats may slip through.
Always review a run directory before sharing it, and don't intentionally
print credentials into a recorded command. See [SECURITY.md](SECURITY.md) for the
security model and its limits.

## 5. What is a "task contract", and how does `verify` differ from `recover`?

They answer two different questions about a run:

- `runledger recover --run-dir <dir>` answers **"what actually happened?"**
  It classifies command events that ended without `command.completed` —
  a kill, a crash, a lost machine — as `incomplete` instead of leaving them
  silently unmarked. It changes no evidence, only the classification.
- `runledger verify --run-dir <dir> --contract <task.json>` answers
  **"did the run do what was asked?"** It evaluates an explicit JSON task
  contract and reports each check as `pass`, `fail`, `not-run`, `unknown`,
  or `incomplete`. Contracts are data (JSON); check kinds are dispatched,
  never evaluated.

Missing evidence is reported as `not-run` or `unknown`, never silently
promoted to a pass.

## 6. How do I tell "it passed" from "something crashed mid-run"?

Read the event stream. If the append-only ledger ends after `command.started`
with no `command.completed` event, the command was terminated, crashed, or
the machine lost power — consumers must treat missing completion as
incomplete, not successful. `recover` makes that classification explicit and
records it under `recovery.v1`. The proof-bundle verifier also reports
incomplete runs explicitly, and any altered bundle member fails SHA-256/size
verification.

## 7. What does `--isolated` do, and when should I use it?

`runledger exec --isolated -- <command>` runs the command in a disposable
detached Git worktree: the caller's checkout is not mutated. Use it whenever
an agent's changes shouldn't touch your working tree — exploratory agent
tasks, parallel runs on the same repository, or any command you wouldn't
comfortably run against your own checkout. Capture is otherwise identical:
events, terminal artifacts, Git before/after evidence, and redaction all
behave the same inside the worktree.

## 8. Can RunLedger run in CI / GitHub Actions?

Yes. The repo ships a published GitHub Action (`action.yml`) that records a
run and can upload a SARIF report on failed contracts. See `docs/ADAPTERS.md`
for building commands for local agent CLIs through conformance-checked
adapters, and `docs/SUPPORTED.md` before relying on output from any
environment. The test suite itself runs on Ubuntu, macOS, and Windows across
Python 3.11–3.13.

---

Still stuck? Check [SECURITY.md](SECURITY.md) (security model and limits),
[event-schema.md](event-schema.md) (every event type), and
[SUPPORTED.md](SUPPORTED.md) (supported environments). For contributing, read
[CONTRIBUTING.md](../CONTRIBUTING.md).
