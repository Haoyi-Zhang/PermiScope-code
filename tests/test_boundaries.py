"""Owned finite regressions for emission limits and weighted evidence."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from pcpe import lowering, source_checker
from pcpe.evidence import _opaque_witness_sites
from pcpe.source_model import parse_source
from pcpe.weighted import minimum_cost
from pcpe.weighted_checker import validate_weighted


def source_with_allocations(count=0):
    body = [{"id": f"n{i}", "op": "new", "dst": "x", "class": "C"}
            for i in range(count)]
    body.append({"id": "load", "op": "load", "dst": "x", "base": "this", "field": "C.f"})
    return {"language": "bfil-1", "permissions": ["P"],
            "classes": [{"name": "C", "super": None, "fields": [{"name": "f", "type": "C"}],
                         "methods": [{"name": "api", "params": [], "returns": None,
                                      "locals": [{"name": "x", "type": "C"}], "body": body}]}],
            "services": [{"name": "svc", "declared_class": "C", "implementation_class": "C"}],
            "entries": [{"name": "api", "service": "svc", "selector": "api", "arg_classes": []}]}


def builders():
    source = parse_source(source_with_allocations())
    yield lowering.Builder(source, lowering.Variant())
    yield source_checker.ReferenceBuilder(source, lowering.Variant().document())


def emit(builder, head="h", body=()):
    builder.rule(head, body, source="load", origin="owned")


class BoundaryTests(unittest.TestCase):
    def test_lowering_rejects_during_emission(self):
        document = source_with_allocations(200)
        for module, run in ((lowering, lambda: lowering.lower(document)),
                            (source_checker, lambda: source_checker.reference_lower(document, lowering.Variant().document()))):
            with self.subTest(module=module.__name__), patch.object(module, "_finish", side_effect=AssertionError("late limit")):
                with self.assertRaisesRegex(ValueError, "ground.bound"):
                    run()

    def test_rule_limit_admits_boundary_not_next_record(self):
        for builder in builders():
            for _ in range(40_000):
                emit(builder)
            with self.assertRaisesRegex(ValueError, "ground.bound"):
                emit(builder)
            self.assertEqual(len(builder.rules), 40_000)

    def test_premise_limit_admits_boundary_not_next_record(self):
        for builder in builders():
            for _ in range(30_000):
                emit(builder, body=("a", "b", "c", "d"))
            with self.assertRaisesRegex(ValueError, "ground.bound"):
                emit(builder, body=("a",))
            self.assertEqual(len(builder.rules), 30_000)

    def test_atom_limit_counts_queries_and_facts(self):
        for builder in builders():
            for index in range(20_000):
                builder.query(f"q{index}")
            # Repeated atoms do not consume another slot.
            builder.fact("q0", source="entry:api", origin="owned")
            with self.assertRaisesRegex(ValueError, "ground.bound"):
                builder.fact("new", source="entry:api", origin="owned")
            self.assertEqual(len(builder.facts), 1)

    def test_atom_name_limit_is_early(self):
        for builder in builders():
            with self.assertRaises(ValueError):
                emit(builder, head="a" * 161)
            self.assertEqual(builder.rules, [])

    def test_large_finite_cost_is_not_a_decimal_ceiling(self):
        n = 82
        rules = [{"head": 0, "body": []}, {"head": 1, "body": [0]}]
        rules += [{"head": i, "body": [i - 2, i - 1]} for i in range(2, n)]
        program = {"atoms": [f"a{i}" for i in range(n)], "facts": [], "rules": rules, "queries": [n - 1]}
        weights = [1] + [0] * (n - 1)
        certificate, _ = minimum_cost(program, weights)
        self.assertEqual(certificate["distances"][-1], 61_305_790_721_611_591)
        self.assertTrue(validate_weighted(program, weights, certificate).accepted)
        certificate["distances"][-1] = 1 << (4 * n + 2)
        self.assertEqual(validate_weighted(program, weights, certificate).reason, "distance-value")

    def test_iterative_occurrence_walk_preserves_tree_duplicates(self):
        n = 1500
        program = {"atoms": ["P:e0:p0"] + [f"a{i}" for i in range(1, n)], "facts": [n - 1],
                   "rules": [{"head": i, "body": [i + 1]} for i in range(n - 1)], "queries": [0]}
        certificate, _ = minimum_cost(program, [1] * (n - 1))
        self.assertTrue(validate_weighted(program, [1] * (n - 1), certificate).accepted)
        upper = {"program": program, "certificate": {"nodes": certificate["nodes"]}, "minimum": certificate,
                 "ir": {"rules": [{"weight": 1, "source": "s", "certainty": "opaque-trigger"}] * (n - 1),
                        "queries": ["P:e0:p0"]}}
        lower = {"program": program, "certificate": {"nodes": [{"atom": n - 1, "rule": -1}]}}
        self.assertEqual(_opaque_witness_sites(upper, certificate, 0), ["s"] * (n - 1))
        row = source_checker.classify_from_certificates(lower, upper, certificate)[0]
        self.assertEqual(row["witness_opaque_sites"], ["s"] * (n - 1))
        self.assertEqual(row["minimum_opaque_uses"], n - 1)

    def test_zero_cost_shared_subtrees_do_not_expand(self):
        n = 40
        rules = [{"head": 0, "body": []}, {"head": 1, "body": [0]}]
        rules += [{"head": i, "body": [i - 2, i - 1]} for i in range(2, n)]
        rules.append({"head": n, "body": [n - 1]})
        program = {"atoms": [f"a{i}" for i in range(n + 1)], "facts": [], "rules": rules, "queries": [n]}
        certificate, _ = minimum_cost(program, [0] * n + [1])
        item = {"program": program, "ir": {"rules": [{"weight": 0, "source": "zero"}] * n + [{"weight": 1, "source": "s"}]}}
        self.assertEqual(_opaque_witness_sites(item, certificate, n), ["s"])

    def test_weighted_bad_atom_type_is_a_verdict(self):
        program = {"atoms": [[]], "facts": [], "rules": [], "queries": []}
        self.assertEqual(validate_weighted(program, [], {"distances": [None], "nodes": []}).reason, "atom-inventory")


if __name__ == "__main__":
    unittest.main()
