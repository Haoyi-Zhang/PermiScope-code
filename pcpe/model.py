"""Strict data model for finite propositional definite-Horn programs.

The trusted input is the *complete* ground program, not a Java framework.
No symbolic grounding, environment reconstruction, or source-coverage proof
is provided by this module. Limits bound encoded size, not Android behavior.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

MAX_ATOMS = 20_000
MAX_RULES = 40_000
MAX_BODY = 16
MAX_PREMISES = 120_000

@dataclass(frozen=True)
class Rule:
    head: int
    body: tuple[int, ...]

@dataclass(frozen=True)
class Program:
    atoms: tuple[str, ...]
    facts: frozenset[int]
    rules: tuple[Rule, ...]
    queries: tuple[int, ...]

    def document(self) -> dict[str, Any]:
        return {'atoms':list(self.atoms),'facts':sorted(self.facts),
                'rules':[{'head':r.head,'body':list(r.body)} for r in self.rules],
                'queries':list(self.queries)}


def parse_program(doc: Any) -> Program:
    if type(doc) is not dict or set(doc) != {'atoms','facts','rules','queries'}:
        raise ValueError('program must have exactly atoms, facts, rules, queries')
    atoms=doc['atoms']
    if type(atoms) is not list or not 1 <= len(atoms) <= MAX_ATOMS:
        raise ValueError('atom inventory bound')
    if any(type(x) is not str or not x or len(x)>160 for x in atoms) or len(set(atoms))!=len(atoms):
        raise ValueError('invalid or duplicate atom name')
    n=len(atoms)
    def ids(xs: Any, label: str, maximum: int=n) -> tuple[int,...]:
        if type(xs) is not list or len(xs)>maximum:
            raise ValueError(label+' bound or type')
        if any(type(x) is not int or not 0<=x<n for x in xs) or len(set(xs))!=len(xs):
            raise ValueError(label+' invalid or duplicate identifier')
        return tuple(xs)
    facts=ids(doc['facts'],'facts')
    queries=ids(doc['queries'],'queries')
    rules_doc=doc['rules']
    if type(rules_doc) is not list or len(rules_doc)>MAX_RULES:
        raise ValueError('rule inventory bound')
    rules=[]
    premises=0
    for d in rules_doc:
        if type(d) is not dict or set(d)!={'head','body'}:
            raise ValueError('rule schema')
        h=d['head']
        if type(h) is not int or not 0<=h<n: raise ValueError('head identifier')
        b=ids(d['body'],'body',MAX_BODY)
        if tuple(sorted(b))!=b: raise ValueError('body must be sorted')
        premises+=len(b)
        if premises>MAX_PREMISES: raise ValueError('premise bound')
        rules.append(Rule(h,b))
    return Program(tuple(atoms),frozenset(facts),tuple(rules),queries)
