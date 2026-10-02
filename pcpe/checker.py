"""Stand-alone checking logic. No imports from producer, core, or oracle.

The checker independently validates the complete input schema, positive
witness order, initial facts, every rule's closure, and query projection.
Its independence is architectural, not independent human authorship or
formal machine verification.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str
    steps: int


def validate(program: Any, certificate: Any, *, closure: bool=True) -> Verdict:
    steps=0
    def bad(reason: str) -> Verdict: return Verdict(False,reason,steps)
    # Deliberate duplicate parsing avoids accepting producer-normalized input.
    if type(program) is not dict or set(program)!={'atoms','facts','rules','queries'}:
        return bad('program-schema')
    names=program['atoms']
    if type(names) is not list or not 1<=len(names)<=20_000:
        return bad('atom-bound')
    if any(type(a) is not str or not a or len(a)>160 for a in names) or len(set(names))!=len(names):
        return bad('atom-inventory')
    n=len(names)
    def valid_ids(xs: Any, limit: int) -> bool:
        return (type(xs) is list and len(xs)<=limit and
                all(type(x) is int and 0<=x<n for x in xs) and
                len(set(xs))==len(xs))
    facts=program['facts'];queries=program['queries'];rules=program['rules']
    if not valid_ids(facts,n) or not valid_ids(queries,n):return bad('fact-query-inventory')
    if type(rules) is not list or len(rules)>40_000:return bad('rule-bound')
    total=0
    for r in rules:
        steps+=1
        if type(r) is not dict or set(r)!={'head','body'}:return bad('rule-schema')
        if type(r['head']) is not int or not 0<=r['head']<n:return bad('head-identifier')
        b=r['body']
        if not valid_ids(b,16) or b!=sorted(b):return bad('body-inventory')
        total+=len(b)
        if total>120_000:return bad('premise-bound')
    if type(certificate) is not dict or set(certificate)!={'nodes','reported'}:
        return bad('certificate-schema')
    nodes=certificate['nodes'];reported=certificate['reported']
    if type(nodes) is not list or len(nodes)>20_000:return bad('certificate-bound')
    if not valid_ids(reported,n) or reported!=sorted(reported):return bad('report-inventory')
    proved=[False]*n
    base=set(facts)
    for node in nodes:
        steps+=1
        if type(node) is not dict or set(node)!={'atom','rule'}:return bad('node-schema')
        a=node['atom'];rid=node['rule']
        if type(a) is not int or not 0<=a<n or proved[a]:return bad('node-identifier')
        if type(rid) is not int or not -1<=rid<len(rules):return bad('reason-identifier')
        if rid==-1:
            if a not in base:return bad('unjustified-leaf')
        else:
            r=rules[rid]
            if r['head']!=a:return bad('wrong-head')
            for x in r['body']:
                steps+=1
                if not proved[x]:return bad('unsupported-premise')
        proved[a]=True
    if closure:
        for f in facts:
            steps+=1
            if not proved[f]:return bad('missing-initial-fact')
        for r in rules:
            steps+=1
            active=True
            for x in r['body']:
                steps+=1
                if not proved[x]:active=False;break
            if active and not proved[r['head']]:return bad('closure-violation')
    wanted=sorted(q for q in queries if proved[q])
    if reported!=wanted:return bad('projection-mismatch')
    return Verdict(True,'accepted',steps)
