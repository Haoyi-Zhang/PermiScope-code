"""Independent truth-table oracle: intersect *all classical models*.

This deliberately does not invoke any fixed-point, producer, or checker
code. Exponential enumeration is restricted to at most four atoms by the
published experiments (the hard function bound is ten).
"""
from __future__ import annotations
from typing import Any


def exact_model(program: dict[str,Any]) -> tuple[frozenset[int],int]:
    n=len(program['atoms'])
    if not 1<=n<=10:raise ValueError('truth-table oracle is restricted to 1..10 atoms')
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
    if not set(program['facts'])<=candidate:return False
    return all(not set(r['body'])<=candidate or r['head'] in candidate for r in program['rules'])
