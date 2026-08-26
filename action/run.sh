#!/usr/bin/env bash
set -u

workspace=${GITHUB_WORKSPACE:-$(pwd)}
run_dir=${INPUT_RUN_DIR:-.runledger/action}
run_path="$workspace/$run_dir"
report_path="$workspace/runledger-report.md"
bundle_path="$workspace/runledger-proof.zip"
sarif_path="$workspace/runledger-results.sarif"

mkdir -p "$run_path"

PYTHON_BIN=${RUNLEDGER_PYTHON:-python}
repo="$workspace"

"$PYTHON_BIN" -m runledger init --repo "$repo" --run-dir "$run_path" --run-id action-run >/dev/null 2>&1 || true

command_status=0
if [ -n "${INPUT_COMMAND:-}" ]; then
  if [ "${INPUT_ISOLATED:-true}" = "true" ]; then
    isolated_flag=--isolated
  else
    isolated_flag=
  fi
  if [ -n "${INPUT_TIMEOUT:-}" ]; then
    timeout_args=(--timeout "$INPUT_TIMEOUT")
  else
    timeout_args=()
  fi
  # Command input is intentionally executed through bash because GitHub Action
  # inputs are strings. Use this only in trusted workflows; leave it empty for
  # untrusted pull requests. RunLedger records the exact command boundary.
  set +e
  "$PYTHON_BIN" -m runledger exec --repo "$repo" --run-dir "$run_path" "${timeout_args[@]}" $isolated_flag --pty -- bash -lc "$INPUT_COMMAND"
  command_status=$?
  set -e
fi

verify_status=0
if [ -n "${INPUT_CONTRACT:-}" ]; then
  set +e
  "$PYTHON_BIN" -m runledger verify --run-dir "$run_path" --contract "$workspace/$INPUT_CONTRACT" >/dev/null
  verify_status=$?
  set -e
fi

"$PYTHON_BIN" -m runledger report --run-dir "$run_path" --format markdown --output "$report_path" >/dev/null
"$PYTHON_BIN" -m runledger report --run-dir "$run_path" --format sarif --output "$sarif_path" >/dev/null
"$PYTHON_BIN" -m runledger bundle create --run-dir "$run_path" --output "$bundle_path" >/dev/null

status=incomplete
if [ -n "${INPUT_COMMAND:-}" ] || [ -n "${INPUT_CONTRACT:-}" ]; then
  status=passed
fi
if [ "$command_status" -ne 0 ] || [ "$verify_status" -ne 0 ]; then
  status=failed
fi
if ! "$PYTHON_BIN" -m runledger bundle verify --output "$bundle_path" >/dev/null; then
  status=failed
fi

{
  printf 'status=%s\n' "$status"
  printf 'report=%s\n' "$report_path"
  printf 'bundle=%s\n' "$bundle_path"
  printf 'sarif=%s\n' "$sarif_path"
} >> "${GITHUB_OUTPUT:-/dev/stdout}"

if [ "$status" != passed ]; then
  exit 1
fi
