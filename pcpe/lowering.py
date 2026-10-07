"""Untrusted BFIL-to-ground-Horn lowering and certificate inventory producer.

The independent consumer in :mod:`pcpe.source_checker` does not import this
module.  It shares only the declared parser/type-model base in
:mod:`pcpe.source_model`.  The lowering is deterministic and emits named
facts/rules before converting them to the finite ground format checked by the
existing Horn checker.

Method/field catalog keys are canonical owner/member pairs supplied by the
strict source model. Compact e0/p0/... tokens are local to this catalog, not
cross-revision identities; transport decodes them before comparison.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .source_model import (
    SourceProgram, Method, Entry, parse_source, resolve_method,
    possible_dispatch, is_subtype,
)

IR_LANGUAGE = "bfil-ir-1"
COVERAGE_LANGUAGE = "bfil-coverage-1"


@dataclass(frozen=True)
class Variant:
    context: str = "1call"          # 1call | insensitive
    fields: str = "sensitive"       # sensitive | insensitive
    dispatch: str = "points-to"     # points-to | cha
    include_opaque: bool = False

    def document(self) -> dict[str, Any]:
        return {"context": self.context, "fields": self.fields,
                "dispatch": self.dispatch, "include_opaque": self.include_opaque}

    def validate(self) -> None:
        if self.context not in {"1call", "insensitive"}:
            raise ValueError("context variant")
        if self.fields not in {"sensitive", "insensitive"}:
            raise ValueError("field variant")
        if self.dispatch not in {"points-to", "cha"}:
            raise ValueError("dispatch variant")
        if type(self.include_opaque) is not bool:
            raise ValueError("opaque variant")


@dataclass(frozen=True)
class Catalog:
    entries: tuple[str, ...]
    permissions: tuple[str, ...]
    methods: tuple[str, ...]
    fields: tuple[str, ...]
    contexts: tuple[str, ...]
    allocations: tuple[str, ...]
    allocation_classes: dict[str, str]
    variables: dict[str, tuple[str, ...]]
    statements: tuple[str, ...]

    def document(self) -> dict[str, Any]:
        return {
            "entries": list(self.entries), "permissions": list(self.permissions),
            "methods": list(self.methods), "fields": list(self.fields),
            "contexts": list(self.contexts), "allocations": list(self.allocations),
            "allocation_classes": dict(sorted(self.allocation_classes.items())),
            "variables": {k: list(v) for k, v in sorted(self.variables.items())},
            "statements": list(self.statements),
        }


class Builder:
    def __init__(self, source: SourceProgram, variant: Variant):
        self.source = source
        self.variant = variant
        self.variant.validate()
        self.catalog = make_catalog(source, variant)
        self.eid = {x: f"e{i}" for i, x in enumerate(self.catalog.entries)}
        self.pid = {x: f"p{i}" for i, x in enumerate(self.catalog.permissions)}
        self.mid = {x: f"m{i}" for i, x in enumerate(self.catalog.methods)}
        self.fid = {x: f"f{i}" for i, x in enumerate(self.catalog.fields)}
        self.cid = {x: f"c{i}" for i, x in enumerate(self.catalog.contexts)}
        self.oid = {x: f"o{i}" for i, x in enumerate(self.catalog.allocations)}
        self.sid = {x: f"s{i}" for i, x in enumerate(self.catalog.statements)}
        self.vid = {(m, v): f"v{i}" for m in self.catalog.methods
                    for i, v in enumerate(self.catalog.variables[m])}
        self.facts: list[dict[str, Any]] = []
        self.rules: list[dict[str, Any]] = []
        self.queries: set[str] = set()
        self._atoms: set[str] = set()
        self._premises = 0

    def reach(self, entry: str, context: str, method: str) -> str:
        return f"R:{self.eid[entry]}:{self.cid[context]}:{self.mid[method]}"

    def point(self, entry: str, context: str, method: str, variable: str, alloc: str) -> str:
        return f"V:{self.eid[entry]}:{self.cid[context]}:{self.mid[method]}:{self.vid[(method, variable)]}:{self.oid[alloc]}"

    def heap(self, entry: str, base: str, field: str, value: str) -> str:
        fk = field if self.variant.fields == "sensitive" else "*"
        if fk == "*":
            ftoken = "fx"
        else:
            ftoken = self.fid[fk]
        return f"H:{self.eid[entry]}:{self.oid[base]}:{ftoken}:{self.oid[value]}"

    def ret(self, entry: str, context: str, method: str, alloc: str) -> str:
        return f"T:{self.eid[entry]}:{self.cid[context]}:{self.mid[method]}:{self.oid[alloc]}"

    def perm(self, entry: str, permission: str) -> str:
        return f"P:{self.eid[entry]}:{self.pid[permission]}"

    def active(self, entry: str, context: str, method: str, statement: str) -> str:
        return f"U:{self.eid[entry]}:{self.cid[context]}:{self.mid[method]}:{self.sid[statement]}"

    def fact(self, atom: str, *, source: str, origin: str) -> None:
        self._track_atoms((atom,))
        self.facts.append({"atom": atom, "source": source, "origin": origin})

    def _track_atoms(self, atoms: Iterable[str]) -> None:
        added = set(atoms) - self._atoms
        if any(len(atom) > 160 for atom in added):
            raise ValueError("atom name bound")
        if len(self._atoms) + len(added) > 20_000:
            raise ValueError("ground bound")
        self._atoms.update(added)

    def query(self, atom: str) -> None:
        self._track_atoms((atom,))
        self.queries.add(atom)

    def rule(self, head: str, body: Iterable[str], *, source: str, origin: str,
             weight: int = 0, certainty: str = "definite") -> None:
        b = sorted(set(body))
        if len(self.rules) >= 40_000 or self._premises + len(b) > 120_000:
            raise ValueError("ground bound")
        self._track_atoms((head, *b))
        self._premises += len(b)
        self.rules.append({"head": head, "body": b, "source": source,
                           "origin": origin, "weight": weight, "certainty": certainty})


def make_catalog(source: SourceProgram, variant: Variant) -> Catalog:
    entries = tuple(sorted(x.name for x in source.entries))
    permissions = tuple(sorted(source.permissions))
    methods = tuple(sorted(source.method_map))
    fields = tuple(sorted(source.field_map))
    statements = tuple(sorted(s["id"] for m in source.method_map.values() for s in m.body))
    variables = {m.key: tuple(sorted(m.variables)) for m in source.method_map.values()}

    context_names: set[str] = {f"root:{x}" for x in entries}
    if variant.context == "insensitive":
        contexts = ("*",)
    else:
        for m in source.method_map.values():
            for stmt in m.body:
                if stmt["op"] in {"invoke", "direct"}:
                    context_names.add(f"site:{stmt['id']}")
                if stmt["op"] == "opaque":
                    for i, candidate in enumerate(stmt["candidates"]):
                        if candidate["op"] in {"invoke", "direct"}:
                            context_names.add(f"site:{stmt['id']}#{i}")
        contexts = tuple(sorted(context_names))

    allocation_classes: dict[str, str] = {}
    services = source.service_map
    for entry in source.entries:
        service = services[entry.service]
        allocation_classes[f"entry:{entry.name}:receiver"] = service.implementation_class
        for i, cls in enumerate(entry.arg_classes):
            allocation_classes[f"entry:{entry.name}:arg:{i}"] = cls
    for method in source.method_map.values():
        for stmt in method.body:
            if stmt["op"] == "new":
                allocation_classes[f"new:{method.key}:{stmt['id']}"] = stmt["class"]
    allocations = tuple(sorted(allocation_classes))
    return Catalog(entries, permissions, methods, fields, contexts, allocations,
                   allocation_classes, variables, statements)


def lower(source_document: Any, variant: Variant | None = None) -> dict[str, Any]:
    source = parse_source(source_document)
    variant = variant or Variant()
    builder = Builder(source, variant)
    _compile_entries(builder)
    _compile_methods(builder)
    return _finish(builder)


def _ctx(builder: Builder, name: str) -> str:
    return "*" if builder.variant.context == "insensitive" else name


def _compile_entries(b: Builder) -> None:
    source = b.source
    services = source.service_map
    for entry in sorted(source.entries, key=lambda x: x.name):
        api = entry.name
        root = _ctx(b, f"root:{api}")
        service = services[entry.service]
        receiver = f"entry:{api}:receiver"
        if b.variant.dispatch == "points-to":
            targets = (resolve_method(source, service.implementation_class, entry.selector),)
        else:
            targets = possible_dispatch(source, service.declared_class, entry.selector)
        for target in targets:
            if target is None:
                continue
            prefix = f"entry:{api}:target:{target.key}"
            b.fact(b.reach(api, root, target.key), source=f"entry:{api}", origin=prefix + ":reach")
            b.fact(b.point(api, root, target.key, "this", receiver), source=f"entry:{api}", origin=prefix + ":this")
            for i, param in enumerate(target.params):
                alloc = f"entry:{api}:arg:{i}"
                b.fact(b.point(api, root, target.key, param.name, alloc), source=f"entry:{api}",
                       origin=prefix + f":arg:{i}")
        for permission in source.permissions:
            b.query(b.perm(api, permission))


def _compile_methods(b: Builder) -> None:
    for method in sorted(b.source.method_map.values(), key=lambda x: x.key):
        for entry in b.catalog.entries:
            for context in b.catalog.contexts:
                for stmt in method.body:
                    if stmt["op"] == "opaque":
                        if b.variant.include_opaque:
                            _compile_opaque(b, entry, context, method, stmt)
                    else:
                        _compile_operation(b, entry, context, method, stmt,
                                           source_id=stmt["id"], origin_prefix=f"stmt:{stmt['id']}",
                                           extra=(), certainty="definite")


def _compile_opaque(b: Builder, entry: str, context: str, method: Method,
                    stmt: dict[str, Any]) -> None:
    active = b.active(entry, context, method.key, stmt["id"])
    reach = b.reach(entry, context, method.key)
    b.rule(active, [reach], source=stmt["id"],
           origin=f"stmt:{stmt['id']}:activate:{b.eid[entry]}:{b.cid[context]}",
           weight=1, certainty="opaque-trigger")
    for i, candidate in enumerate(stmt["candidates"]):
        _compile_operation(b, entry, context, method, candidate,
                           source_id=stmt["id"], origin_prefix=f"stmt:{stmt['id']}:candidate:{i}",
                           extra=(active,), certainty="opaque-effect", candidate_index=i)


def _compile_operation(b: Builder, entry: str, context: str, method: Method,
                       op: dict[str, Any], *, source_id: str, origin_prefix: str,
                       extra: tuple[str, ...], certainty: str,
                       candidate_index: int | None = None) -> None:
    kind = op["op"]
    reach = b.reach(entry, context, method.key)
    base_guard = extra if extra else (reach,)
    suffix = f":{b.eid[entry]}:{b.cid[context]}"
    allocs = b.catalog.allocations
    if kind == "new":
        alloc = f"new:{method.key}:{op['id']}"
        b.rule(b.point(entry, context, method.key, op["dst"], alloc), base_guard,
               source=source_id, origin=origin_prefix + suffix + ":new", certainty=certainty)
    elif kind == "move":
        for alloc in allocs:
            b.rule(b.point(entry, context, method.key, op["dst"], alloc),
                   base_guard + (b.point(entry, context, method.key, op["src"], alloc),),
                   source=source_id, origin=origin_prefix + suffix + f":move:{b.oid[alloc]}", certainty=certainty)
    elif kind == "store":
        for base in allocs:
            for value in allocs:
                b.rule(b.heap(entry, base, op["field"], value),
                       base_guard + (b.point(entry, context, method.key, op["base"], base),
                                     b.point(entry, context, method.key, op["src"], value)),
                       source=source_id,
                       origin=origin_prefix + suffix + f":store:{b.oid[base]}:{b.oid[value]}",
                       certainty=certainty)
    elif kind == "load":
        for base in allocs:
            for value in allocs:
                b.rule(b.point(entry, context, method.key, op["dst"], value),
                       base_guard + (b.point(entry, context, method.key, op["base"], base),
                                     b.heap(entry, base, op["field"], value)),
                       source=source_id,
                       origin=origin_prefix + suffix + f":load:{b.oid[base]}:{b.oid[value]}",
                       certainty=certainty)
    elif kind == "check":
        b.rule(b.perm(entry, op["permission"]), base_guard, source=source_id,
               origin=origin_prefix + suffix + ":check", certainty=certainty)
    elif kind == "return":
        if op["src"] is not None:
            for alloc in allocs:
                b.rule(b.ret(entry, context, method.key, alloc),
                       base_guard + (b.point(entry, context, method.key, op["src"], alloc),),
                       source=source_id, origin=origin_prefix + suffix + f":return:{b.oid[alloc]}",
                       certainty=certainty)
    elif kind == "direct":
        target = b.source.method_map[op["target"]]
        site = f"site:{source_id}" if candidate_index is None else f"site:{source_id}#{candidate_index}"
        callee_ctx = _ctx(b, site)
        _compile_call(b, entry, context, method, target, op, base_guard, source_id,
                      origin_prefix + suffix + ":direct", callee_ctx, certainty,
                      receiver_var="this", dynamic_alloc=None)
    elif kind == "invoke":
        static_type = method.variables[op["recv"]]
        site = f"site:{source_id}" if candidate_index is None else f"site:{source_id}#{candidate_index}"
        callee_ctx = _ctx(b, site)
        if b.variant.dispatch == "points-to":
            for recv_alloc in allocs:
                cls = b.catalog.allocation_classes[recv_alloc]
                if not is_subtype(b.source, cls, static_type):
                    continue
                target = resolve_method(b.source, cls, op["selector"])
                if target is None:
                    continue
                guard = base_guard + (b.point(entry, context, method.key, op["recv"], recv_alloc),)
                _compile_call(b, entry, context, method, target, op, guard, source_id,
                              origin_prefix + suffix + f":invoke:{b.oid[recv_alloc]}:{b.mid[target.key]}",
                              callee_ctx, certainty, receiver_var=op["recv"], dynamic_alloc=recv_alloc)
        else:
            targets = possible_dispatch(b.source, static_type, op["selector"])
            for target in targets:
                _compile_call(b, entry, context, method, target, op, base_guard, source_id,
                              origin_prefix + suffix + f":cha:{b.mid[target.key]}", callee_ctx,
                              certainty, receiver_var=op["recv"], dynamic_alloc="CHA")
    else:
        raise AssertionError(kind)


def _compile_call(b: Builder, entry: str, caller_ctx: str, caller: Method,
                  target: Method, op: dict[str, Any], guard: tuple[str, ...],
                  source_id: str, origin: str, callee_ctx: str, certainty: str,
                  *, receiver_var: str, dynamic_alloc: str | None) -> None:
    b.rule(b.reach(entry, callee_ctx, target.key), guard, source=source_id,
           origin=origin + ":reach", certainty=certainty)
    allocs = b.catalog.allocations
    # ``None`` is a direct same-receiver call; ``CHA`` uses every compatible
    # receiver allocation for every hierarchy target; otherwise the allocation
    # was already selected by the points-to guard.
    if dynamic_alloc not in (None, "CHA"):
        receiver_allocs = (dynamic_alloc,)
    else:
        receiver_allocs = allocs
    for alloc in receiver_allocs:
        if dynamic_alloc == "CHA":
            static_type = caller.variables[receiver_var]
            if not is_subtype(b.source, b.catalog.allocation_classes[alloc], static_type):
                continue
        this_body = guard + (b.point(entry, caller_ctx, caller.key, receiver_var, alloc),)
        b.rule(b.point(entry, callee_ctx, target.key, "this", alloc), this_body,
               source=source_id, origin=origin + f":this:{b.oid[alloc]}", certainty=certainty)
    for i, (arg, param) in enumerate(zip(op["args"], target.params)):
        for alloc in allocs:
            body = guard + (b.point(entry, caller_ctx, caller.key, arg, alloc),)
            b.rule(b.point(entry, callee_ctx, target.key, param.name, alloc), body,
                   source=source_id, origin=origin + f":arg:{i}:{b.oid[alloc]}", certainty=certainty)
    if op["dst"] is not None:
        for alloc in allocs:
            body = guard + (b.ret(entry, callee_ctx, target.key, alloc),)
            b.rule(b.point(entry, caller_ctx, caller.key, op["dst"], alloc), body,
                   source=source_id, origin=origin + f":ret:{b.oid[alloc]}", certainty=certainty)


def _finish(b: Builder) -> dict[str, Any]:
    b.facts.sort(key=lambda x: (x["origin"], x["atom"]))
    b.rules.sort(key=lambda x: (x["origin"], x["head"], tuple(x["body"]), x["weight"], x["certainty"]))
    atoms = sorted({x["atom"] for x in b.facts} | b.queries |
                   {r["head"] for r in b.rules} |
                   {a for r in b.rules for a in r["body"]})
    if len(atoms) > 20_000 or len(b.rules) > 40_000 or sum(len(r["body"]) for r in b.rules) > 120_000:
        raise ValueError("ground bound")
    if any(len(x) > 160 for x in atoms):
        raise ValueError("atom name bound")
    index = {name: i for i, name in enumerate(atoms)}
    fact_atoms = sorted({x["atom"] for x in b.facts})
    program = {
        "atoms": atoms,
        "facts": [index[x] for x in fact_atoms],
        "rules": [{"head": index[r["head"]], "body": sorted(index[x] for x in r["body"])} for r in b.rules],
        "queries": [index[x] for x in sorted(b.queries)],
    }
    ir = {
        "language": IR_LANGUAGE,
        "variant": b.variant.document(),
        "catalog": b.catalog.document(),
        "atoms": atoms,
        "facts": b.facts,
        "rules": b.rules,
        "queries": sorted(b.queries),
    }
    coverage = make_coverage(b.source, b.facts, b.rules)
    return {"ir": ir, "program": program, "coverage": coverage}


def make_coverage(source: SourceProgram, facts: list[dict[str, Any]],
                  rules: list[dict[str, Any]]) -> dict[str, Any]:
    rule_counts: dict[str, list[int]] = {}
    for rule in rules:
        counts = rule_counts.setdefault(rule["source"], [0, 0, 0])
        counts[0] += 1
        counts[1] += rule["certainty"] == "opaque-trigger"
        counts[2] += rule["certainty"] == "opaque-effect"
    fact_counts: dict[str, int] = {}
    for fact in facts:
        key = fact["source"]
        fact_counts[key] = fact_counts.get(key, 0) + 1
    rows: list[dict[str, Any]] = []
    for method in sorted(source.method_map.values(), key=lambda x: x.key):
        for stmt in method.body:
            counts = rule_counts.get(stmt["id"], (0, 0, 0))
            rows.append({"id": stmt["id"], "method": method.key, "op": stmt["op"],
                         "facts": 0, "rules": counts[0],
                         "opaque_triggers": counts[1], "opaque_effects": counts[2]})
    entry_rows = []
    for entry in sorted(source.entries, key=lambda x: x.name):
        key = f"entry:{entry.name}"
        entry_rows.append({"id": key,
                           "facts": fact_counts.get(key, 0),
                           "rules": rule_counts.get(key, (0, 0, 0))[0]})
    return {"language": COVERAGE_LANGUAGE, "entries": entry_rows, "statements": rows,
            "totals": {"facts": len(facts), "rules": len(rules),
                       "statements": len(rows), "entries": len(entry_rows)}}
