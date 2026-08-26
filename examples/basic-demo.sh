#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEMO_DIR=$(mktemp -d "${TMPDIR:-/tmp}/runledger-demo.XXXXXX")
trap 'rm -rf "$DEMO_DIR"' EXIT
export PYTHONPATH="$ROOT/src"

mkdir -p "$DEMO_DIR/repo"
git -C "$DEMO_DIR/repo" init -q
git -C "$DEMO_DIR/repo" config user.email runledger@example.com
git -C "$DEMO_DIR/repo" config user.name RunLedger
printf 'initial\n' > "$DEMO_DIR/repo/README.md"
git -C "$DEMO_DIR/repo" add README.md
git -C "$DEMO_DIR/repo" commit -qm initial

python3 -m runledger init --repo "$DEMO_DIR/repo" --run-dir "$DEMO_DIR/run" --run-id demo
mkdir -p "$DEMO_DIR/repo/src"
printf 'print("fixture")\n' > "$DEMO_DIR/repo/src/feature.py"
python3 -m runledger exec --repo "$DEMO_DIR/repo" --run-dir "$DEMO_DIR/run" -- python3 -c "print('fixture pass')"

cat > "$DEMO_DIR/task.json" <<'JSON'
{
  "name": "basic-demo",
  "allowed_paths": ["src/**"],
  "checks": [
    {"id": "fixture-command", "kind": "command-exit", "command": "python3 -c print('fixture pass')", "expect": 0},
    {"id": "diff-budget", "kind": "changed-lines", "maximum": 20}
  ]
}
JSON

python3 -m runledger verify --run-dir "$DEMO_DIR/run" --contract "$DEMO_DIR/task.json"
python3 -m runledger report --run-dir "$DEMO_DIR/run" --format html --output "$DEMO_DIR/run.html"
python3 -m runledger bundle create --run-dir "$DEMO_DIR/run" --output "$DEMO_DIR/proof.zip"
python3 -m runledger bundle verify --output "$DEMO_DIR/proof.zip"
printf '\nOpen the generated HTML report at: %s\n' "$DEMO_DIR/run.html"
