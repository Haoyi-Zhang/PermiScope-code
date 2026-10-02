"""Ordered inclusion-minimal activation sets of optional input facts.

This is not a least set, a minimum-cardinality set, or a repair recommendation.
The only completion semantics implemented here is independent addition of
optional *positive facts*. Deletions, negation, and mutually exclusive choices
are not silently modeled this way.
"""
from __future__ import annotations
from typing import Any
from .model import parse_program
from .producer import extract


def activation_core(program: dict[str,Any], optional: list[int], query: int,
                    order: list[int], *, counters: dict[str,int]|None=None) -> tuple[list[int]|None,int]:
    parsed=parse_program(program)
    n=len(parsed.atoms)
    if (type(optional) is not list or any(type(x) is not int or not 0<=x<n for x in optional) or
        len(set(optional))!=len(optional) or set(optional)&set(program['facts'])):
        raise ValueError('optional facts must be distinct, in range, and noninitial')
    if type(order) is not list or any(type(x) is not int for x in order) or sorted(order)!=sorted(optional) or len(order)!=len(optional):raise ValueError('order must permute optional facts')
    if type(query) is not int or not 0<=query<n:raise ValueError('query out of range')
    kept=set(optional);calls=0
    def holds(s:set[int]) -> bool:
        nonlocal calls
        d=dict(program);d['facts']=sorted(set(program['facts'])|s)
        cert,stats=extract(parse_program(d));calls+=1
        if counters is not None:
            counters['graph_operations']=counters.get('graph_operations',0)+stats['graph_operations']
        return any(x['atom']==query for x in cert['nodes'])
    if not holds(kept):return None,calls
    for item in order:
        if holds(kept-{item}):kept.remove(item)
    return sorted(kept),calls
