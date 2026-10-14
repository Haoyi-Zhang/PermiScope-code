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

    def test_local_check_cannot_shadow_primitive(self):
        with self.assertRaises(ValueError):
            translate_owned(PREFIX + '        check: Guard = Guard()\n        check("P_A")\n',
                            "owned-shadow-negative.py")

    def test_local_enabled_cannot_shadow_primitive(self):
        with self.assertRaises(ValueError):
            translate_owned(PREFIX + '        enabled: Guard = Guard()\n        if enabled("site"):\n            check("P_A")\n',
                            "owned-shadow-negative.py")

    def test_parameter_cannot_shadow_primitive(self):
        source = '''class Guard:
    def enforce(self) -> None:
        check("P_A")
class Service:
    def helper(self, check: Guard) -> None:
        check("P_A")
    def run(self) -> None:
        guard: Guard = Guard()
        self.helper(guard)
'''
        with self.assertRaises(ValueError):
            translate_owned(source, "owned-shadow-negative.py")

    def test_class_cannot_shadow_primitive(self):
        source = '''class check:
    def enforce(self) -> None:
        check("P_A")
class Service:
    def run(self) -> None:
        check("P_A")
'''
        with self.assertRaises(ValueError):
            translate_owned(source, "owned-shadow-negative.py")

    def test_unshadowed_primitives_are_accepted(self):
        document = translate_owned(PREFIX +
            '        check("P_A")\n        if enabled("site"):\n            check("P_A")\n',
            "owned-admission-positive.py")
        service = next(c for c in document["classes"] if c["name"] == "Service")
        self.assertEqual([s["op"] for s in service["methods"][-1]["body"]],
                         ["check", "opaque"])
        self.assertEqual(service["methods"][-1]["body"][-1]["candidates"][0]["op"], "check")

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
