"""Independent truth-table oracle: intersect *all classical models*.

This deliberately does not invoke any fixed-point, producer, or checker
code. Exponential enumeration is restricted to at most four atoms by the
published experiments (the hard function bound is ten).
"""
from __future__ import annotations
from typing import Any


def _admit_program(program: Any) -> int:
    """Own input gate: do not normalize malformed identifiers into bit masks."""
    if type(program) is not dict or set(program) != {'atoms','facts','rules','queries'}:
        raise ValueError('oracle program schema')
    atoms = program['atoms']
    if (type(atoms) is not list or not 1 <= len(atoms) <= 10 or
        any(type(a) is not str or not a or len(a) > 160 for a in atoms) or
        len(set(atoms)) != len(atoms)):
        raise ValueError('truth-table oracle is restricted to 1..10 distinct named atoms')
    n = len(atoms)
    def ids(xs: Any, limit: int) -> bool:
        return (type(xs) is list and len(xs) <= limit and
                all(type(x) is int and 0 <= x < n for x in xs) and
                len(set(xs)) == len(xs))
    if not ids(program['facts'], n) or not ids(program['queries'], n):
        raise ValueError('oracle fact/query inventory')
    rules = program['rules']
    if type(rules) is not list or len(rules) > 40_000:
        raise ValueError('oracle rule bound')
    premises = 0
    for rule in rules:
        if type(rule) is not dict or set(rule) != {'head','body'}:
            raise ValueError('oracle rule schema')
        if type(rule['head']) is not int or not 0 <= rule['head'] < n:
            raise ValueError('oracle head identifier')
        if not ids(rule['body'], 16) or rule['body'] != sorted(rule['body']):
            raise ValueError('oracle body inventory')
        premises += len(rule['body'])
        if premises > 120_000:
            raise ValueError('oracle premise bound')
    return n


def exact_model(program: dict[str,Any]) -> tuple[frozenset[int],int]:
    n=_admit_program(program)
    common=(1<<n)-1
    fact_mask=sum(1<<i for i in program['facts'])
    rules=[(1<<r['head'],sum(1<<i for i in r['body'])) for r in program['rules']]
    tested=0
    for assignment in range(1<<n):
        tested+=1
        if assignment & fact_mask != fact_mask:continue
        satisfies=True
        for head,body in rules:
            if assignment & body == body and assignment & head == 0:
                satisfies=False;break
        if satisfies:common &= assignment
    return frozenset(i for i in range(n) if common & (1<<i)),tested


def candidate_is_closed(program: dict[str,Any],candidate: frozenset[int]) -> bool:
    n=_admit_program(program)
    if (type(candidate) is not frozenset or
        any(type(x) is not int or not 0 <= x < n for x in candidate)):
        raise ValueError('oracle candidate inventory')
    if not set(program['facts'])<=candidate:return False
    return all(not set(r['body'])<=candidate or r['head'] in candidate for r in program['rules'])
