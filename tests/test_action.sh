#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/runledger-action.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/workspace"
git -C "$TMP/workspace" init -q
git -C "$TMP/workspace" config user.email action@example.com
git -C "$TMP/workspace" config user.name RunLedger
printf 'initial\n' > "$TMP/workspace/README.md"
git -C "$TMP/workspace" add README.md
git -C "$TMP/workspace" commit -qm initial

export PYTHONPATH="$ROOT/src"
export RUNLEDGER_PYTHON=python3
export GITHUB_WORKSPACE="$TMP/workspace"
export GITHUB_OUTPUT="$TMP/outputs"
export INPUT_COMMAND="printf 'action-ok\\n'"
export INPUT_CONTRACT=
export INPUT_RUN_DIR=.runledger/action
export INPUT_ISOLATED=true
export INPUT_TIMEOUT=

bash "$ROOT/action/run.sh" >/dev/null

grep -q '^status=passed$' "$TMP/outputs"
test -s "$TMP/workspace/runledger-report.md"
test -s "$TMP/workspace/runledger-proof.zip"
test -s "$TMP/workspace/runledger-results.sarif"
test -s "$TMP/workspace/.runledger/action/events.jsonl"

echo "RunLedger Action harness: OK"
