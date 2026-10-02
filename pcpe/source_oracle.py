"""Independent direct fixed-point evaluator for definite and completion BFIL semantics.

The evaluator works over named reachability, points-to, heap, return, and
permission relations.  It does not construct Horn rules and imports neither
lowering nor certificate code.  By default opaque source statements have no
effect (the lower endpoint).  A caller may enable a set of opaque statement
identifiers; every declared candidate at each enabled site then executes (a
completion).  Enabling every site yields the upper endpoint used by the
bounded completion checks.
"""
from __future__ import annotations

from typing import Any, AbstractSet

from .source_model import parse_source, resolve_method, is_subtype


def opaque_sites(document: Any) -> tuple[str, ...]:
    """Return the sorted opaque-statement inventory after strict parsing."""
    source = parse_source(document)
    return tuple(sorted(
        stmt["id"]
        for method in source.method_map.values()
        for stmt in method.body
        if stmt["op"] == "opaque"
    ))


def permission_oracle(
    document: Any,
    enabled_opaque_sites: AbstractSet[str] | None = None,
) -> tuple[set[tuple[str, str]], dict[str, int]]:
    """Evaluate the finite BFIL program directly.

    ``enabled_opaque_sites`` must be a subset of the source program's opaque
    statement identifiers.  Each enabled site activates all candidates
    declared at that site, matching BFIL's independent completion semantics.
    The routine intentionally does not reuse lowering or proof production.
    """
    source = parse_source(document)
    all_opaque = {
        stmt["id"]
        for method in source.method_map.values()
        for stmt in method.body
        if stmt["op"] == "opaque"
    }
    enabled = set() if enabled_opaque_sites is None else set(enabled_opaque_sites)
    if not enabled <= all_opaque:
        raise ValueError("unknown opaque site")

    alloc_class: dict[str, str] = {}
    for entry in source.entries:
        service = source.service_map[entry.service]
        alloc_class[f"entry:{entry.name}:receiver"] = service.implementation_class
        for i, cls in enumerate(entry.arg_classes):
            alloc_class[f"entry:{entry.name}:arg:{i}"] = cls
    for method in source.method_map.values():
        for stmt in method.body:
            if stmt["op"] == "new":
                alloc_class[f"new:{method.key}:{stmt['id']}"] = stmt["class"]

    reach: set[tuple[str, str, str]] = set()
    points: dict[tuple[str, str, str, str], set[str]] = {}
    heap: dict[tuple[str, str, str], set[str]] = {}
    returns: dict[tuple[str, str, str], set[str]] = {}
    permissions: set[tuple[str, str]] = set()
    events = 0

    def addmap(table: dict, key: tuple, values: set[str]) -> bool:
        nonlocal events
        slot = table.setdefault(key, set())
        before = len(slot)
        slot.update(values)
        events += len(values)
        return len(slot) != before

    for entry in source.entries:
        service = source.service_map[entry.service]
        target = resolve_method(source, service.implementation_class, entry.selector)
        if target is None:
            raise ValueError(f'entry target did not resolve: {entry.name}')
        ctx = f"root:{entry.name}"
        reach.add((entry.name, ctx, target.key))
        addmap(points, (entry.name, ctx, target.key, "this"), {f"entry:{entry.name}:receiver"})
        for i, param in enumerate(target.params):
            addmap(points, (entry.name, ctx, target.key, param.name), {f"entry:{entry.name}:arg:{i}"})

    changed = True
    iterations = 0
    while changed:
        changed = False
        iterations += 1
        for api, ctx, mkey in sorted(reach):
            method = source.method_map[mkey]

            def pts(var: str) -> set[str]:
                return set(points.get((api, ctx, mkey, var), set()))

            def execute(op: dict[str, Any], source_id: str, candidate_index: int | None = None) -> bool:
                local_changed = False
                kind = op["op"]
                suffix = "" if candidate_index is None else f"#{candidate_index}"
                if kind == "new":
                    local_changed |= addmap(
                        points,
                        (api, ctx, mkey, op["dst"]),
                        {f"new:{mkey}:{source_id}"},
                    )
                elif kind == "move":
                    local_changed |= addmap(points, (api, ctx, mkey, op["dst"]), pts(op["src"]))
                elif kind == "store":
                    for base in pts(op["base"]):
                        local_changed |= addmap(heap, (api, base, op["field"]), pts(op["src"]))
                elif kind == "load":
                    values: set[str] = set()
                    for base in pts(op["base"]):
                        values.update(heap.get((api, base, op["field"]), set()))
                    local_changed |= addmap(points, (api, ctx, mkey, op["dst"]), values)
                elif kind == "check":
                    before = len(permissions)
                    permissions.add((api, op["permission"]))
                    local_changed |= len(permissions) != before
                elif kind == "return":
                    if op["src"] is not None:
                        local_changed |= addmap(returns, (api, ctx, mkey), pts(op["src"]))
                elif kind == "direct":
                    target = source.method_map[op["target"]]
                    callee_ctx = f"site:{source_id}{suffix}"
                    before = len(reach)
                    reach.add((api, callee_ctx, target.key))
                    local_changed |= len(reach) != before
                    local_changed |= addmap(points, (api, callee_ctx, target.key, "this"), pts("this"))
                    for arg, param in zip(op["args"], target.params):
                        local_changed |= addmap(points, (api, callee_ctx, target.key, param.name), pts(arg))
                    if op["dst"] is not None:
                        local_changed |= addmap(
                            points,
                            (api, ctx, mkey, op["dst"]),
                            set(returns.get((api, callee_ctx, target.key), set())),
                        )
                elif kind == "invoke":
                    callee_ctx = f"site:{source_id}{suffix}"
                    for obj in pts(op["recv"]):
                        cls = alloc_class[obj]
                        if not is_subtype(source, cls, method.variables[op["recv"]]):
                            continue
                        target = resolve_method(source, cls, op["selector"])
                        if target is None:
                            continue
                        before = len(reach)
                        reach.add((api, callee_ctx, target.key))
                        local_changed |= len(reach) != before
                        local_changed |= addmap(points, (api, callee_ctx, target.key, "this"), {obj})
                        for arg, param in zip(op["args"], target.params):
                            local_changed |= addmap(points, (api, callee_ctx, target.key, param.name), pts(arg))
                        if op["dst"] is not None:
                            local_changed |= addmap(
                                points,
                                (api, ctx, mkey, op["dst"]),
                                set(returns.get((api, callee_ctx, target.key), set())),
                            )
                else:
                    raise AssertionError(kind)
                return local_changed

            for stmt in method.body:
                if stmt["op"] == "opaque":
                    if stmt["id"] in enabled:
                        for index, candidate in enumerate(stmt["candidates"]):
                            changed |= execute(candidate, stmt["id"], index)
                else:
                    changed |= execute(stmt, stmt["id"])
        if iterations > 10_000:
            raise ValueError("oracle did not converge")

    return permissions, {
        "iterations": iterations,
        "events": events,
        "reachable_method_contexts": len(reach),
        "enabled_opaque_sites": len(enabled),
    }
