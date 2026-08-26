# Event schema v1

Each RunLedger run is a directory containing an append-only `events.jsonl` file, a `run.json` manifest, and an `artifacts/` directory. Every event is one JSON object per line.

## Required envelope

```json
{
  "schema": "runledger.event.v1",
  "run_id": "demo",
  "seq": 2,
  "timestamp": "2026-08-26T12:00:00.000Z",
  "type": "command.completed"
}
```

`seq` is a 1-based monotonic integer within one run. Consumers must preserve input order and treat a gap or malformed line as a corrupt or incomplete ledger. Timestamps are informational and are not used as the ordering key.

## v0.1 event types

| Type | Required payload | Meaning |
|---|---|---|
| `run.initialized` | `repo`, `git` | The initial repository state was captured. |
| `command.started` | `argv`, `command_display`, `command_sha256`, `cwd` | A command was accepted for execution. |
| `command.completed` | `exit_code`, `duration_ms`, `stdout`, `stderr`, `timed_out` | The command completed, timed out, or failed to start. |
| `verification.completed` | `contract`, `status`, `check_count` | A deterministic task contract was evaluated. |

## Artifact references

Artifact-bearing event fields contain a relative `path`, a lowercase SHA-256 `sha256`, and a byte count. Paths are always relative to the run directory and must not contain `..` components. A consumer should verify the digest before rendering or sharing an artifact.

## Compatibility rule

New event fields may be added without changing the schema identifier. A breaking change to field meaning, sequencing, or artifact path semantics requires a new schema identifier and migration note. Unknown event types must be rendered as unknown rather than discarded.
