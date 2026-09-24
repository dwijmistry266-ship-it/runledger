# Security model

RunLedger is an evidence recorder, not a sandbox. The command passed to `runledger exec` runs with the permissions of the invoking user. RunLedger does not make arbitrary code safe merely by recording it.

## Capture boundary

The recorder captures the command arguments, working directory, exit status, duration, and stdout/stderr. It hashes the raw argument vector for correlation but stores a redacted display form. Common credential-shaped values are replaced before terminal artifacts are written.

Redaction is a safety net, not a guarantee. Review a run directory before sharing it, use a dedicated test environment for untrusted code, and do not intentionally print credentials into a command. Full output capture can still contain sensitive business data that is not shaped like a token.

## Git and filesystem behavior

RunLedger uses argument-array subprocess calls for Git and recorded commands; it does not interpolate commands into a shell. It reads Git metadata and writes only beneath the selected run directory. The v0.1 contract verifier reports path evidence from the captured Git snapshot but does not revert changes.

## Integrity and limitations

Artifact SHA-256 values make accidental changes detectable within a run bundle. They do not prove that the original process was honest, that the operating system was uncompromised, or that an agent’s hidden reasoning was captured. Later bundle verification will report hash mismatches and incomplete runs explicitly.

If a command is terminated, loses power, or is killed, the append-only ledger may end after a `command.started` event. Consumers must treat missing completion events as incomplete, not successful.

## Reporting vulnerabilities

Do not open a public issue containing credentials, private repository contents, or an exploit payload. Use the repository’s private security-reporting channel when configured, or contact the maintainer before public disclosure.

## Security review — 2026-09-24

Scope: all of `src/runledger/`, `action/run.sh`, and the CI workflows, reviewed against the threat model above before the 1.0.0a0 prerelease.

- **Command execution**: the recorder and PTY capture take argument arrays only; `shell=True` is never used, and shell-string input is rejected with `ValueError`. No finding.
- **Artifact paths**: `ArtifactStore` and bundle verification reject absolute paths and `..` components. Bundle verification never extracts to disk (no ZipSlip surface). No finding.
- **Bundles**: deterministic member ordering, fixed timestamps, and `0o600` member permissions; tampering is detected via SHA-256/size checks against `MANIFEST.json`. No finding.
- **Contracts**: contracts are data (JSON); check kinds are dispatched, never evaluated. Path matching uses `fnmatch` on captured Git status, with no shell involvement. No finding.
- **Redaction**: credential-shaped values are replaced before artifacts are written, and typed PTY input is never stored. By design, redaction is conservative and documented as a safety net, not a guarantee.
- **Action**: `action.yml` executes the `command` string through `bash -lc` because Action inputs are strings; this is documented as trusted-workflows-only, and the input defaults to empty (inspect-only mode). Accepted residual risk, documented.
- **Correlation hashes**: `command_sha256` hashes the raw argv for event correlation while storing only the redacted display. A short, low-entropy command could theoretically be brute-forced from its hash; treat hashes as opaque correlation ids, not as secret storage. Accepted residual risk, documented here.

No blocking findings. Residual risks are documented above rather than silently accepted.
