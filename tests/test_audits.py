from __future__ import annotations

import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from audit_manuscript import audit_public_sources, audit_references
from pcpe.public_slice import validate_public_slice

ROOT = Path(__file__).resolve().parents[1]


class AuditTests(unittest.TestCase):
    def test_reference_audit_inventory(self):
        self.assertEqual(audit_references(ROOT), {"references": 68})

    def test_public_source_audit_inventory(self):
        self.assertEqual(audit_public_sources(ROOT), {"public_sources": 12})

    def test_public_slice_digest_tamper_rejected(self):
        path = next((ROOT / "inputs" / "public-slices").glob("*.json"))
        record = json.loads(path.read_text())
        record["excerpt"] = record["excerpt"].replace("permission", "permissioN", 1)
        self.assertEqual(validate_public_slice(record).reason, "excerpt-digest")

    def test_public_blob_identities_are_frozen(self):
        with (ROOT / "public_source_audit.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        by_path = {}
        for row in rows:
            by_path.setdefault(row["path"], set()).add(row["file_blob_sha1"])
        self.assertEqual(set(map(len, by_path.values())), {1})
        self.assertEqual(
            {next(iter(values)) for values in by_path.values()},
            {
                "cb7e54dda5279d5e80a34a279fa0bb1a61ece934",
                "cd3d603d831a0478aaea4d09e8db8d589c14a9dc",
            },
        )


if __name__ == "__main__":
    unittest.main()
