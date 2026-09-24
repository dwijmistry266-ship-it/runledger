# Supported environments

RunLedger is a local command-line tool. The core recorder uses Python’s standard library and is intended to run on Python 3.11 or newer.

| Area | Supported behavior | Boundary |
|---|---|---|
| Linux | Standard capture, Git snapshots, isolated worktrees, PTY capture, reports, bundles, and the Action environment. | PTY behavior depends on a usable POSIX pseudo-terminal. |
| macOS | Standard capture, Git snapshots, isolated worktrees, reports, and bundles. | PTY capture is expected to work on normal terminal hosts but is covered less extensively than Linux. || Windows | Standard capture, Git snapshots, reports, bundles, contracts, and comparisons when Git is installed. | `--pty` is unavailable; use the regular recorder. Disposable worktree support requires a working Git installation. |
| Git | Git repositories with a readable `HEAD` are supported for snapshots and diffs. | Non-Git directories can still record commands, but Git evidence is marked unavailable. |
| Commands | Argument-array execution is the default CLI path. | `action.yml` accepts a command string and uses Bash because GitHub Action inputs are strings; use it only in trusted workflows. |
| Interactive input | PTY capture accepts optional stdin bytes for interactive fixtures (REPLs, prompts). | Typed input is recorded only as a byte count, never stored; do not type secrets into an interactive fixture. |
| Output | UTF-8 text is decoded with replacement for invalid bytes and stored as hashed artifacts. | Redaction is conservative and does not identify every private datum. |
| Network | The recorder does not control, restrict, or monitor network access; every run manifest declares `"network": "unrestricted"`. | No network sandbox is provided or implied. Use OS-level controls for untrusted work. |
| Containers | Docker-based execution is not provided. | Run the command in your own container and record it with the CLI; the ledger captures what happened inside. |

## Stability expectations

The event identifiers ending in `.v1` are the compatibility surface for the alpha-to-stable transition. The CLI syntax may change before 1.0.0. Consumers should use the documented report and bundle schemas rather than parsing human-readable terminal messages.

RunLedger has no hosted control plane, telemetry requirement, or model API dependency. It does not inspect hidden model reasoning and does not guarantee that a recorded command was safe.
