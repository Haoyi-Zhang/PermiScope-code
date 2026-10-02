"""Independent validator for minimum weighted Horn derivation certificates.

This module imports neither the weighted producer nor the shared model parser.
Acceptance establishes the exact minimum derivation-tree cost for every atom
relative to the supplied complete ground program and rule weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WeightedVerdict:
    accepted: bool
    reason: str
    steps: int


def validate_weighted(program: Any, weights: Any, certificate: Any) -> WeightedVerdict:
    steps = 0
    def bad(reason: str) -> WeightedVerdict:
        return WeightedVerdict(False, reason, steps)
    if type(program) is not dict or set(program) != {"atoms", "facts", "rules", "queries"}:
        return bad("program-schema")
    atoms = program["atoms"]
    if type(atoms) is not list or not 1 <= len(atoms) <= 20_000 or len(set(atoms)) != len(atoms):
        return bad("atom-inventory")
    if any(type(x) is not str or not x or len(x) > 160 for x in atoms):
        return bad("atom-inventory")
    n = len(atoms)
    def ids(xs: Any, limit: int) -> bool:
        return type(xs) is list and len(xs) <= limit and all(type(x) is int and 0 <= x < n for x in xs) and len(set(xs)) == len(xs)
    if not ids(program["facts"], n) or not ids(program["queries"], n):
        return bad("fact-query-inventory")
    rules = program["rules"]
    if type(rules) is not list or len(rules) > 40_000:
        return bad("rule-bound")
    premises = 0
    for rule in rules:
        steps += 1
        if type(rule) is not dict or set(rule) != {"head", "body"}:
            return bad("rule-schema")
        if type(rule["head"]) is not int or not 0 <= rule["head"] < n:
            return bad("head-identifier")
        if not ids(rule["body"], 16) or rule["body"] != sorted(rule["body"]):
            return bad("body-inventory")
        premises += len(rule["body"])
        if premises > 120_000:
            return bad("premise-bound")
    if type(weights) is not list or len(weights) != len(rules) or any(type(x) is not int or not 0 <= x <= 1_000_000 for x in weights):
        return bad("weight-inventory")
    if type(certificate) is not dict or set(certificate) != {"distances", "nodes"}:
        return bad("certificate-schema")
    distances = certificate["distances"]
    nodes = certificate["nodes"]
    if type(distances) is not list or len(distances) != n:
        return bad("distance-inventory")
    if any(x is not None and (type(x) is not int or x < 0 or x > 10**15) for x in distances):
        return bad("distance-value")
    if type(nodes) is not list or len(nodes) > n:
        return bad("node-bound")
    proved = [False] * n
    selected = [-2] * n
    base = set(program["facts"])
    for node in nodes:
        steps += 1
        if type(node) is not dict or set(node) != {"atom", "rule"}:
            return bad("node-schema")
        atom = node["atom"]; rid = node["rule"]
        if type(atom) is not int or not 0 <= atom < n or proved[atom]:
            return bad("node-identifier")
        if type(rid) is not int or not -1 <= rid < len(rules):
            return bad("reason-identifier")
        if distances[atom] is None:
            return bad("infinite-node")
        if rid == -1:
            if atom not in base or distances[atom] != 0:
                return bad("fact-distance")
        else:
            rule = rules[rid]
            if rule["head"] != atom:
                return bad("wrong-head")
            total = weights[rid]
            for premise in rule["body"]:
                steps += 1
                if not proved[premise] or distances[premise] is None:
                    return bad("unsupported-premise")
                total += distances[premise]
            if total != distances[atom]:
                return bad("witness-cost")
        proved[atom] = True
        selected[atom] = rid
    # Every and only finite atom has a founded witness.
    for atom, value in enumerate(distances):
        steps += 1
        if (value is not None) != proved[atom]:
            return bad("finite-witness-mismatch")
        if atom in base and value != 0:
            return bad("initial-distance")
    # Bellman lower-bound inequalities: the proposed distance is no larger
    # than the cost of every possible rule derivation.  Coupled with one
    # equality witness, this proves exact minimality.
    for rid, rule in enumerate(rules):
        steps += 1
        if any(distances[x] is None for x in rule["body"]):
            continue
        candidate = weights[rid] + sum(distances[x] for x in rule["body"])
        head = distances[rule["head"]]
        if head is None:
            return bad("finite-rule-to-infinite-head")
        if head > candidate:
            return bad("bellman-violation")
    return WeightedVerdict(True, "accepted", steps)
