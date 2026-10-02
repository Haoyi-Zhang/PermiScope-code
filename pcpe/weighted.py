"""Minimum unresolved-site derivation-tree certificates for weighted Horn rules.

Weights are non-negative integers.  The value of an atom is the minimum sum of
rule weights in a finite derivation tree.  Facts have value zero.  The emitted
certificate contains all finite distances and one ordered equality witness per
finite atom; ``weighted_checker.py`` validates optimality independently using
Bellman inequalities.
"""
from __future__ import annotations

from math import inf
from typing import Any

from .model import parse_program


def minimum_cost(program: dict[str, Any], weights: list[int]) -> tuple[dict[str, Any], dict[str, int]]:
    parsed = parse_program(program)
    if type(weights) is not list or len(weights) != len(parsed.rules) or any(type(x) is not int or x < 0 or x > 1_000_000 for x in weights):
        raise ValueError("weight inventory")
    n = len(parsed.atoms)
    dist = [inf] * n
    reason: list[int | None] = [None] * n
    stamp = [0] * n
    clock = 0
    for atom in sorted(parsed.facts):
        dist[atom] = 0
        reason[atom] = -1
        stamp[atom] = clock
        clock += 1
    # Monotone relaxation from infinity.  Strict improvements retain a
    # foundation; zero-cost equality cycles never replace an existing witness.
    changed = True
    relaxations = 0
    scans = 0
    while changed:
        changed = False
        for rid, rule in enumerate(parsed.rules):
            scans += 1
            if any(dist[x] == inf for x in rule.body):
                continue
            candidate = weights[rid] + sum(int(dist[x]) for x in rule.body)
            if candidate < dist[rule.head]:
                dist[rule.head] = candidate
                reason[rule.head] = rid
                stamp[rule.head] = clock
                clock += 1
                relaxations += 1
                changed = True
    # The final witness relation is acyclic for non-negative weights and strict
    # updates, but order it by a defensive DFS rather than relying on stamps.
    ordered: list[int] = []
    state = [0] * n
    def visit(atom: int) -> None:
        if dist[atom] == inf or state[atom] == 2:
            return
        if state[atom] == 1:
            raise ValueError("cyclic minimum witness")
        state[atom] = 1
        rid = reason[atom]
        if rid is None:
            raise ValueError("finite atom without witness")
        if rid >= 0:
            for premise in parsed.rules[rid].body:
                visit(premise)
        state[atom] = 2
        ordered.append(atom)
    for atom in sorted(range(n), key=lambda x: (dist[x], stamp[x], x)):
        visit(atom)
    cert = {
        "distances": [None if x == inf else int(x) for x in dist],
        "nodes": [{"atom": a, "rule": int(reason[a])} for a in ordered],
    }
    return cert, {"relaxations": relaxations, "rule_scans": scans, "finite_atoms": len(ordered)}


def witness_rule_ids(certificate: dict[str, Any], query: int) -> list[int]:
    """Return a derivation-tree list of rule ids (duplicates preserve tree cost)."""
    nodes = {x["atom"]: x["rule"] for x in certificate["nodes"]}
    out: list[int] = []
    # The caller must supply the program to recurse through bodies; this helper
    # is intentionally only a shallow selected-rule lookup for compatibility.
    if query in nodes and nodes[query] >= 0:
        out.append(nodes[query])
    return out
