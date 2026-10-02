"""Untrusted worklist extractor. It is not imported by the checker."""
from __future__ import annotations
from collections import deque
from typing import Any
from .model import Program


def extract(p: Program) -> tuple[dict[str, Any],dict[str,int]]:
    waiting=[[] for _ in p.atoms]
    left=[]
    operations=0
    for rid,r in enumerate(p.rules):
        left.append(len(r.body))
        for a in r.body:
            waiting[a].append(rid); operations+=1
    queue=deque()
    seen=set()
    nodes=[]
    def add(a: int, why: int) -> None:
        if a not in seen:
            seen.add(a);nodes.append({'atom':a,'rule':why});queue.append(a)
    for a in sorted(p.facts): add(a,-1)
    for rid,r in enumerate(p.rules):
        operations+=1
        if not r.body: add(r.head,rid)
    while queue:
        a=queue.popleft();operations+=1
        for rid in waiting[a]:
            operations+=1
            left[rid]-=1
            if left[rid]==0: add(p.rules[rid].head,rid)
    cert={'nodes':nodes,'reported':sorted(seen.intersection(p.queries))}
    return cert,{'graph_operations':operations,'derived_atoms':len(seen)}
