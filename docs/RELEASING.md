# Releasing RunLedger

RunLedger releases should be reproducible from a clean checkout. The alpha gate is a passing standard-library test suite, a successful CLI fixture run, a valid offline HTML report, a valid proof bundle, and a clean package build.

## Local verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src
```

Create a temporary Git fixture and run the quick start from the README. Inspect `events.jsonl`, `run.json`, redacted artifacts, `checks.json`, Markdown, HTML, and the proof bundle before publishing any captured output.

## Package verification

```bash
python3 -m pip install --upgrade build
python3 -m build
python3 -m venv /tmp/runledger-release-venv
. /tmp/runledger-release-venv/bin/activate
python -m pip install dist/*.whl
runledger --help
deactivate
```

The package must not require a model API key, hosted service, or third-party runtime dependency for the core CLI.

## Release checklist

Before creating a tag, confirm that the version in `pyproject.toml` and `src/runledger/__init__.py` matches, the changelog has an entry, the README commands work from a fresh environment, the full test suite passes, and no local `.runledger/` state or captured secrets is included in the release archive.

A release should include a short demonstration with real fixture output and should state the capture boundary. Never describe a passing contract as proof that an agent was safe or that the resulting code is correct.
