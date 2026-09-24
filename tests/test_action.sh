#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

make_workspace() {
  local dir
  dir=$(mktemp -d "${TMPDIR:-/tmp}/runledger-action.XXXXXX")
  mkdir -p "$dir/workspace"
  git -C "$dir/workspace" init -q
  git -C "$dir/workspace" config user.email action@example.com
  git -C "$dir/workspace" config user.name RunLedger
  printf 'initial\n' > "$dir/workspace/README.md"
  git -C "$dir/workspace" add README.md
  git -C "$dir/workspace" commit -qm initial
  printf '%s' "$dir"
}

run_action() {
  export PYTHONPATH="$ROOT/src"
  export RUNLEDGER_PYTHON=python3
  export GITHUB_WORKSPACE="$1/workspace"
  export GITHUB_OUTPUT="$1/outputs"
  export INPUT_COMMAND="printf 'action-ok\\n'"
  if [ -n "$2" ]; then
    mkdir -p "$1/workspace/fixtures/action-contract"
    cp "$ROOT/fixtures/action-contract/task.json" "$1/workspace/fixtures/action-contract/task.json"
    export INPUT_CONTRACT="fixtures/action-contract/task.json"
  else
    export INPUT_CONTRACT=
  fi
  export INPUT_RUN_DIR=.runledger/action
  export INPUT_ISOLATED=true
  export INPUT_TIMEOUT=
  bash "$ROOT/action/run.sh" >/dev/null
}

# Phase 1: passing run without a contract.
TMP=$(make_workspace)
trap 'rm -rf "$TMP" "${TMP2:-}"' EXIT
run_action "$TMP" ""
grep -q '^status=passed$' "$TMP/outputs"
test -s "$TMP/workspace/runledger-report.md"
test -s "$TMP/workspace/runledger-proof.zip"
test -s "$TMP/workspace/runledger-results.sarif"
test -s "$TMP/workspace/.runledger/action/events.jsonl"

# Phase 2: a failing contract must surface as SARIF findings.
TMP2=$(make_workspace)
set +e
run_action "$TMP2" "contract"
action_code=$?
set -e
test "$action_code" -ne 0
grep -q '^status=failed$' "$TMP2/outputs"
test -s "$TMP2/workspace/runledger-results.sarif"
grep -q 'runledger/required-command' "$TMP2/workspace/runledger-results.sarif"

echo "RunLedger Action harness: OK"
