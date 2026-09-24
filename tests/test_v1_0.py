"""RunLedger v1.0 milestone tests: schema stability and bundle compatibility."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from runledger.bundle import BUNDLE_SCHEMA, build_bundle, verify_bundle
from runledger.ledger import SCHEMA as EVENT_SCHEMA, Ledger
from runledger.recorder import CommandRecorder


PYTHON = sys.executable  # portable no-op command target across platforms
NOOP = [PYTHON, "-c", "pass"]


class RunLedgerV10Tests(unittest.TestCase):
    def test_stable_schema_identifiers_are_unchanged(self) -> None:
        # The v1 compatibility surface froze at 0.1.0a0; changing any of these
        # identifiers requires a migration note per docs/VERSIONING.md.
        self.assertEqual(EVENT_SCHEMA, "runledger.event.v1")
        self.assertEqual(BUNDLE_SCHEMA, "runledger.bundle.v1")

    def test_bundle_rejects_unknown_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            ledger = Ledger(run_dir, run_id="schema")
            ledger.write_manifest({"run_id": "schema"})
            CommandRecorder(ledger, cwd=root).run(NOOP)
            bundle = root / "proof.zip"
            build_bundle(run_dir, bundle)
            tampered = root / "future.zip"
            with zipfile.ZipFile(bundle) as source:
                manifest = json.loads(source.read("MANIFEST.json").decode("utf-8"))
            manifest["schema"] = "runledger.bundle.v99"
            with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(tampered, "w") as target:
                for item in source.infolist():
                    if item.filename == "MANIFEST.json":
                        target.writestr(item, json.dumps(manifest).encode("utf-8"))
                    else:
                        target.writestr(item, source.read(item.filename))
            valid, errors = verify_bundle(tampered)
            self.assertFalse(valid)
            self.assertTrue(any("unsupported bundle schema" in error for error in errors))

    def test_bundle_round_trips_across_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            ledger = Ledger(run_dir, run_id="portable")
            ledger.write_manifest({"run_id": "portable"})
            CommandRecorder(ledger, cwd=root).run(NOOP)
            bundle = root / "proof.zip"
            manifest = build_bundle(run_dir, bundle)
            self.assertEqual(manifest["schema"], BUNDLE_SCHEMA)
            valid, errors = verify_bundle(bundle)
            self.assertTrue(valid, errors)


if __name__ == "__main__":
    unittest.main()
