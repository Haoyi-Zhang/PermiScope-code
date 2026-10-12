"""Execute only the two newly authored, reviewed, harmless source fixtures."""
from __future__ import annotations

import unittest

from pcpe.owned_subset import translate_owned
from run_owned_source_comparison import compare, concrete_owned, FIXTURES


class OwnedSourceComparisonTests(unittest.TestCase):
    def test_native_translation_completion_and_revision_comparison(self):
        report, _ = compare()
        self.assertEqual(report["concrete_completions"], 8)
        self.assertEqual(report["mismatches"], 0)
        rows = report["lower_endpoint_ablations"]
        for variant in ("field-insensitive", "context-insensitive"):
            row = next(x for x in rows if x["version"] == "old" and x["variant"] == variant)
            self.assertEqual(row["false_positives"], [("API", "P_B")])
            self.assertEqual(row["false_negatives"], [])
        self.assertGreater(report["changing_revision_transport"]["completed_nodes"], 0)

    def test_unknown_execution_path_and_choice_are_rejected(self):
        with self.assertRaises(ValueError):
            concrete_owned("unreviewed", set())
        with self.assertRaises(RuntimeError):
            concrete_owned("old", {"unknown"})

    def test_unsupported_source_constructs_are_rejected(self):
        text = (FIXTURES / "old.py").read_text(encoding="utf-8")
        for bad in ("import os\n" + text,
                    text.replace('if enabled("opaque.outer"):', "if True:"),
                    text.replace("target: Guard = first", "target: Guard = first\n        target = second"),
                    text.replace("return alias", "return alias\n        check(\"P_A\")"),
                    text.replace("loaded.enforce()", "while True:\n            loaded.enforce()")):
            with self.subTest(source=bad[:30]), self.assertRaises(ValueError):
                translate_owned(bad, "owned-negative.py")


if __name__ == "__main__":
    unittest.main()
