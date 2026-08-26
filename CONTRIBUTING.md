# Contributing to RunLedger

RunLedger is intentionally evidence-first. A contribution should make a recorded behavior more observable, a verification result more deterministic, a platform boundary clearer, or the local installation easier to reproduce.

Before opening a pull request, run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash examples/basic-demo.sh
```

New behavior should include a fixture or regression test. Prefer standard-library implementations for the core. Do not add a hosted service, model API, telemetry, or automatic repository mutation without documenting the boundary and adding a safe failure test.

A useful pull request explains the problem, the observable evidence that demonstrates the change, the tests run, and any known limitations. Do not include captured secrets, private repository content, or real production logs in fixtures. Synthetic fixtures are sufficient for testing redaction and failure behavior.

## Contribution areas

| Area | Examples |
|---|---|
| Capture adapters | PTY support, agent CLI adapters, platform-specific process events. |
| Verification | New deterministic check kinds, task-pack fixtures, test-runner parsers. |
| Viewer | Timeline filters, artifact navigation, accessible offline rendering. |
| Integrity | Bundle verification, redaction rules, crash recovery, schema tooling. |
| Documentation | Reproducible examples, threat-model improvements, platform notes. |

The project currently uses direct commits during early development. Please keep changes small enough to review from the generated evidence artifacts.
