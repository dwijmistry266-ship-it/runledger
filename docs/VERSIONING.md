# Versioning

RunLedger versions the package, the Git tags, and the schema identifiers on separate but coordinated tracks.

## Package versions

- Versions are `MAJOR.MINOR.PATCH` with an optional alpha prerelease suffix, e.g. `0.2.0a0`.
- Alpha milestones are published as prereleases (`0.1.0a0`, `0.2.0a0`, …). The schema and CLI may change between alphas.
- The first stable release is `1.0.0`. After that, breaking changes to the CLI or to any documented schema require a major version bump.
- `pyproject.toml` and `src/runledger/__init__.py` must carry the same version before a tag is created.

## Tags and releases

- Tags are `v` + version, e.g. `v0.2.0a0`. One tag per milestone, on `main`.
- Every tag gets a GitHub release. Alpha releases are marked prerelease and describe the milestone's exit evidence honestly, including gates that remain open.
- Release notes state the capture boundary: a passing contract is not proof of safety or correctness.

## Schema identifiers

- Schema identifiers such as `runledger.event.v1`, `runledger.report.v1`, `runledger.checks.v1`, and `runledger.bundle.v1` are the compatibility surface.
- Adding fields without changing meaning does not change the identifier. A breaking change to field meaning, sequencing, or artifact path semantics requires a new identifier and a migration note in the changelog.
- Proof bundles verify across package versions as long as the bundle schema identifier matches; `bundle verify` rejects unknown schema identifiers explicitly rather than guessing.

## Migration notes

- `0.1.0a0` → `1.0.0a0`: no migration required. All schema identifiers introduced in the alpha (`runledger.event.v1`, `runledger.run.v1`, `runledger.checks.v1`, `runledger.report.v1`, `runledger.bundle.v1`, `runledger.recovery.v1`) are unchanged, and the CLI subcommands are backward compatible. The report summary gained an additive `artifacts` index array; consumers should ignore unknown fields.
