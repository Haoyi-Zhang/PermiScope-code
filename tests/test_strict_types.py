"""Harmless malformed-JSON regressions at each numeric admission boundary."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from pcpe.check import load
from pcpe.checker import validate
from pcpe.core import activation_core
from pcpe.evidence import build_evidence
from pcpe.lowering import Variant, lower
from pcpe.model import parse_program
from pcpe.oracle import exact_model, candidate_is_closed
from pcpe.producer import extract
from pcpe.public_slice import validate_public_slice
from pcpe.revision import transport
from pcpe.source_checker import reference_lower, validate_source_evidence
from pcpe.source_identity import SemanticCatalog
from pcpe.source_model import parse_source
from pcpe.source_oracle import permission_oracle
from pcpe.source_revision import transport_complete
from pcpe.weighted import minimum_cost
from pcpe.weighted_checker import validate_weighted

ROOT = Path(__file__).resolve().parents[1]


def tiny_source():
    return dict(language="bfil-1", permissions=["P_A", "P_B", "P_C"],
        classes=[dict(name="Svc", super=None, fields=[], methods=[dict(
            name="run", params=[], returns=None, locals=[], body=[
                dict(id="certain", op="check", permission="P_A"),
                dict(id="optional", op="opaque", candidates=[dict(op="check", permission="P_B")]),
                dict(id="end", op="return", src=None)])])],
        services=[dict(name="service", declared_class="Svc", implementation_class="Svc")],
        entries=[dict(name="API", service="service", selector="run", arg_classes=[])])


def numeric_leaves(value, path=()):
    if type(value) in (int, bool):
        yield path, value
    elif type(value) is dict:
        for key, child in value.items():
            yield from numeric_leaves(child, path + (key,))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from numeric_leaves(child, path + (index,))


def substitutes(value):
    if type(value) is bool:
        return [int(value), float(value), str(value).lower()]
    values = [float(value), str(value)]
    if value in (0, 1):
        values.append(bool(value))
    return values


def replaced(document, path, value):
    changed = copy.deepcopy(document)
    parent = changed
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    return changed


class StrictTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = tiny_source()
        cls.evidence, _ = build_evidence(cls.source)
        cls.program = dict(atoms=["a", "b", "q"], facts=[0],
            rules=[dict(head=1, body=[0]), dict(head=2, body=[1])], queries=[2])
        cls.certificate, _ = extract(parse_program(cls.program))
        cls.weights = [0, 1]
        cls.weighted, _ = minimum_cost(cls.program, cls.weights)

    def test_ground_numeric_fields_all_consumers(self):
        for path, original in numeric_leaves(self.program):
            for value in substitutes(original):
                with self.subTest(path=path, value=value, type=type(value).__name__):
                    malformed = replaced(self.program, path, value)
                    self.assertFalse(validate(malformed, self.certificate).accepted)
                    self.assertFalse(validate_weighted(malformed, self.weights, self.weighted).accepted)
                    for consumer in (parse_program, exact_model,
                                     lambda p: candidate_is_closed(p, frozenset({0, 1, 2})),
                                     lambda p: minimum_cost(p, self.weights),
                                     lambda p: activation_core(p, [], 2, [])):
                        with self.assertRaises(ValueError):
                            consumer(malformed)
                    self.assertFalse(transport(self.program, malformed, self.certificate)[1].accepted)
                    self.assertFalse(transport(malformed, self.program, self.certificate)[1].accepted)

    def test_ordinary_certificate_numeric_fields(self):
        for path, original in numeric_leaves(self.certificate):
            for value in substitutes(original):
                with self.subTest(path=path, value=value):
                    malformed = replaced(self.certificate, path, value)
                    self.assertFalse(validate(self.program, malformed).accepted)
                    self.assertFalse(transport(self.program, self.program, malformed)[1].accepted)

    def test_weighted_certificate_numeric_fields(self):
        for path, original in numeric_leaves(self.weighted):
            for value in substitutes(original):
                with self.subTest(path=path, value=value):
                    malformed = replaced(self.weighted, path, value)
                    self.assertFalse(validate_weighted(self.program, self.weights, malformed).accepted)

    def test_rule_weights_are_integers_not_booleans_or_reals(self):
        for index, weight in enumerate(self.weights):
            for value in substitutes(weight):
                weights = list(self.weights)
                weights[index] = value
                with self.subTest(index=index, value=value):
                    with self.assertRaises(ValueError):
                        minimum_cost(self.program, weights)
                    self.assertFalse(validate_weighted(self.program, weights, self.weighted).accepted)

    def test_complete_source_evidence_numeric_leaves(self):
        # Includes both IR weights and Boolean variant tags, every ground ID,
        # coverage row/total, both certificates, and must/unresolved costs.
        paths = list(numeric_leaves(self.evidence))
        self.assertTrue(any(p[0] == "classification" for p, _ in paths))
        self.assertTrue(validate_source_evidence(self.source, self.evidence).accepted)
        for path, original in paths:
            for value in substitutes(original):
                with self.subTest(path=path, value=value, type=type(value).__name__):
                    # Round-trip through JSON so these are actual decoded JSON
                    # booleans/reals/strings, not exotic Python subclasses.
                    malformed = json.loads(json.dumps(replaced(self.evidence, path, value)))
                    self.assertFalse(validate_source_evidence(self.source, malformed).accepted)

    def test_none_is_not_zero_for_impossible_cost(self):
        index = next(i for i, row in enumerate(self.evidence["classification"])
                     if row["status"] == "impossible")
        for value in (False, 0, 0.0, "0"):
            malformed = replaced(self.evidence, ("classification", index, "minimum_opaque_uses"), value)
            self.assertEqual(validate_source_evidence(self.source, malformed).reason, "classification-mismatch")

    def test_boolean_variant_tags_in_both_lowerings(self):
        for value in (0, 1, 0.0, 1.0, "false", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    lower(self.source, Variant(include_opaque=value))
                with self.assertRaises(ValueError):
                    reference_lower(self.source, Variant(include_opaque=value).document())

    def test_source_span_integer_admission(self):
        document = copy.deepcopy(self.source)
        stmt = document["classes"][0]["methods"][0]["body"][0]
        stmt["span"] = dict(unit="owned", start_line=1, end_line=1)
        for key in ("start_line", "end_line"):
            for value in (True, 1.0, "1"):
                malformed = replaced(document, ("classes", 0, "methods", 0, "body", 0, "span", key), value)
                with self.subTest(key=key, value=value):
                    for consumer in (parse_source, lower, permission_oracle):
                        with self.assertRaises(ValueError):
                            consumer(malformed)
                    self.assertFalse(validate_source_evidence(malformed, self.evidence).accepted)

    def test_public_source_line_integer_admission(self):
        record = json.loads(next((ROOT / "inputs/public-slices").glob("*.json")).read_text())
        for key in ("start_line", "end_line"):
            for value in (True, float(record["provenance"][key]), str(record["provenance"][key])):
                malformed = replaced(record, ("provenance", key), value)
                self.assertEqual(validate_public_slice(malformed).reason, "line-range")

    def test_kernel_optional_query_order_candidate_admission(self):
        program = dict(atoms=["u", "q"], facts=[],
                       rules=[dict(head=1, body=[0])], queries=[1])
        for value in (False, 0.0, "0"):
            for optional, order in (([value], [0]), ([0], [value])):
                with self.assertRaises(ValueError):
                    activation_core(program, optional, 1, order)
            with self.assertRaises(ValueError):
                candidate_is_closed(program, frozenset({value}))
        for value in (True, 1.0, "1"):
            with self.assertRaises(ValueError):
                activation_core(program, [0], value, [0])

    def test_source_transport_ground_admission_before_indexing(self):
        compiled = {k: self.evidence["lower"][k] for k in ("ir", "program", "coverage")}
        for path, original in numeric_leaves(compiled["program"]):
            for value in substitutes(original):
                malformed = replaced(compiled, ("program",) + path, value)
                with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                    transport_complete(self.evidence["lower"], malformed)

    def test_transport_identity_weight_and_variant_admission(self):
        compiled = {k: self.evidence["lower"][k] for k in ("ir", "program", "coverage")}
        paths = [("ir", "variant", "include_opaque"), ("ir", "rules", 0, "weight")]
        for path in paths:
            original = False if path[1] == "variant" else 0
            for value in substitutes(original):
                malformed = replaced(compiled, path, value)
                with self.assertRaises(ValueError):
                    SemanticCatalog(malformed["ir"])
                with self.assertRaises(ValueError):
                    transport_complete(self.evidence["lower"], malformed)
                old = replaced(self.evidence["lower"], path, value)
                with self.assertRaises(ValueError):
                    transport_complete(old, compiled)

    def test_json_reader_preserves_types_for_admission(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / "owned-malformed.json"
            for value in (False, 0.0, "0"):
                malformed = replaced(self.program, ("facts", 0), value)
                path.write_text(json.dumps(malformed), encoding="utf-8")
                decoded = load(path)
                self.assertIs(type(decoded["facts"][0]), type(value))
                self.assertFalse(validate(decoded, self.certificate).accepted)


if __name__ == "__main__":
    unittest.main()
