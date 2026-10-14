"""Benign syntax-only regressions; negative Python sources are never executed."""
from pathlib import Path
import unittest

from pcpe.owned_subset import translate_owned


PREFIX = '''class Guard:
    def enforce(self) -> None:
        check("P_A")

class Service:
    def relay(self, value: Guard) -> Guard:
        return value

    def run(self) -> None:
'''


class OwnedSubsetAdmissionTests(unittest.TestCase):
    def reject(self, body):
        with self.assertRaisesRegex(ValueError, "initialized variable"):
            translate_owned(PREFIX + body, "owned-admission-negative.py")

    def test_initializer_cannot_read_its_own_local(self):
        self.reject("        value: Guard = value\n        value.enforce()\n")

    def test_initializer_cannot_read_a_later_local(self):
        self.reject("        value: Guard = later\n        later: Guard = Guard()\n        value.enforce()\n")

    def test_initializer_call_cannot_use_its_destination(self):
        self.reject("        value: Guard = self.relay(value)\n        value.enforce()\n")

    def test_call_before_local_initialization_is_rejected(self):
        self.reject("        value.enforce()\n        value: Guard = Guard()\n")

    def test_opaque_candidate_cannot_read_a_later_local(self):
        self.reject('        if enabled("site"):\n            value.enforce()\n        value: Guard = Guard()\n')

    def test_initialized_alias_and_parameter_are_accepted(self):
        document = translate_owned(PREFIX + "        value: Guard = Guard()\n        alias: Guard = self.relay(value)\n        alias.enforce()\n", "owned-admission-positive.py")
        service = next(c for c in document["classes"] if c["name"] == "Service")
        self.assertEqual([s["op"] for s in service["methods"][-1]["body"]], ["new", "invoke", "invoke"])

    def test_all_four_retained_sources_still_translate(self):
        inputs = Path(__file__).resolve().parents[1] / "inputs"
        for directory in ("source-semantics", "receiver-semantics"):
            for version in ("old", "new"):
                path = inputs / directory / (version + ".py")
                with self.subTest(path=str(path)):
                    document = translate_owned(path.read_text(encoding="utf-8"), path.name)
                    self.assertEqual(document["language"], "bfil-1")


if __name__ == "__main__":
    unittest.main()
