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
