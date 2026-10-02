"""Deterministic, structurally diverse BFIL revision pairs.

The campaign contains exactly 100 pairs for each of three separating families.
A seed is decoded into a 5 x 5 x 4 grid of *semantic structure* rather than
being used only to rename declarations:

* ``alias_depth`` (0..4) changes the reachable value-flow chain;
* ``width`` (0..4) changes reachable field/call/subclass alternatives; and
* ``structure_depth`` (0..3) changes wrapper or inheritance depth.

Every fifth seed also carries a one-, two-, or three-site positive opaque chain.
The public ``structural_signature`` function erases user-chosen identifiers and
is used by the campaign to reject accidental clone inflation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


def _var(name: str, type_: str) -> dict[str, str]:
    return {"name": name, "type": type_}


def _method(
    name: str,
    params: list[dict[str, str]],
    returns: str | None,
    locals_: list[dict[str, str]],
    body: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"name": name, "params": params, "returns": returns, "locals": locals_, "body": body}


def _cls(
    name: str,
    super_: str | None,
    fields: list[tuple[str, str]],
    methods: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "super": super_,
        "fields": [{"name": n, "type": t} for n, t in fields],
        "methods": methods,
    }


@dataclass(frozen=True)
class CaseProfile:
    alias_depth: int
    width: int
    structure_depth: int
    opaque_depth: int

    def document(self) -> dict[str, int]:
        return {
            "alias_depth": self.alias_depth,
            "width": self.width,
            "structure_depth": self.structure_depth,
            "opaque_depth": self.opaque_depth,
        }


def profile_for_seed(seed: int) -> CaseProfile:
    """Decode ``0 <= seed < 100`` into a unique 5 x 5 x 4 profile."""
    if not 0 <= seed < 100:
        raise ValueError("seed")
    alias_depth = seed % 5
    width = (seed // 5) % 5
    structure_depth = (seed // 25) % 4
    # Preserve seed 0 as the canonical two-site unit-test case while covering
    # depths 1, 2, and 3 across every family.
    opaque_depth = 0 if seed % 5 else 1 + ((seed // 5 + 1) % 3)
    return CaseProfile(alias_depth, width, structure_depth, opaque_depth)


def _guard_classes(prefix: str) -> list[dict[str, Any]]:
    return [
        _cls(
            prefix + "Guard",
            None,
            [],
            [_method("guard", [], None, [], [{"id": prefix + "base_return", "op": "return", "src": None}])],
        ),
        _cls(
            prefix + "GuardA",
            prefix + "Guard",
            [],
            [
                _method(
                    "guard",
                    [],
                    None,
                    [],
                    [
                        {"id": prefix + "check_a", "op": "check", "permission": "PERM_A"},
                        {"id": prefix + "a_return", "op": "return", "src": None},
                    ],
                )
            ],
        ),
        _cls(
            prefix + "GuardB",
            prefix + "Guard",
            [],
            [
                _method(
                    "guard",
                    [],
                    None,
                    [],
                    [
                        {"id": prefix + "check_b", "op": "check", "permission": "PERM_B"},
                        {"id": prefix + "b_return", "op": "return", "src": None},
                    ],
                )
            ],
        ),
    ]


def _opaque_chain(prefix: str, owner: str, depth: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return helper methods and the first positive opaque operation.

    All ``depth`` source sites are necessary to reach ``PERM_C``.  A depth-one
    chain is a single opaque check.  Longer chains begin with an opaque direct
    call and end in an opaque check.
    """
    if depth == 0:
        return [], []
    if not 1 <= depth <= 3:
        raise ValueError("opaque depth")
    if depth == 1:
        return [], [
            {
                "id": prefix + "opaque_0",
                "op": "opaque",
                "summary": "declared unknown permission branch",
                "candidates": [{"op": "check", "permission": "PERM_C"}],
            }
        ]

    helpers: list[dict[str, Any]] = []
    for index in range(1, depth):
        if index == depth - 1:
            candidate: dict[str, Any] = {"op": "check", "permission": "PERM_C"}
        else:
            candidate = {
                "op": "direct",
                "dst": None,
                "target": f"{owner}.opaque_step_{index + 1}",
                "args": [],
            }
        helpers.append(
            _method(
                f"opaque_step_{index}",
                [],
                None,
                [],
                [
                    {
                        "id": f"{prefix}opaque_{index}",
                        "op": "opaque",
                        "summary": "declared unknown helper effect",
                        "candidates": [candidate],
                    },
                    {"id": f"{prefix}opaque_return_{index}", "op": "return", "src": None},
                ],
            )
        )
    outer = [
        {
            "id": prefix + "opaque_0",
            "op": "opaque",
            "summary": "declared unknown helper dispatch",
            "candidates": [
                {"op": "direct", "dst": None, "target": f"{owner}.opaque_step_1", "args": []}
            ],
        }
    ]
    return helpers, outer


def _flow_suffix(
    prefix: str,
    guard: str,
    start: str,
    alias_depth: int,
    preserve: bool,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], str]:
    """Create a reachable move chain and an optional preserving refactoring."""
    locals_: list[dict[str, str]] = []
    body: list[dict[str, Any]] = []
    current = start
    for index in range(alias_depth):
        nxt = f"alias_{index}"
        locals_.append(_var(nxt, guard))
        body.append({"id": f"{prefix}alias_move_{index}", "op": "move", "dst": nxt, "src": current})
        current = nxt
    if preserve:
        locals_.append(_var("preserved", guard))
        body.append({"id": prefix + "preserving_move", "op": "move", "dst": "preserved", "src": current})
        current = "preserved"
    return locals_, body, current


def _preserve_mode(seed: int, preserve: bool) -> int:
    """Return 0 for reachable refactoring, 1/2 for closure-neutral additions."""
    return (seed // 2) % 3 if preserve else -1


def _unused_class(prefix: str, permission: str = "PERM_A") -> dict[str, Any]:
    return _cls(
        "ZZ" + prefix + "Unused",
        None,
        [],
        [
            _method(
                "unused",
                [],
                None,
                [],
                [
                    {"id": prefix + "unused_check", "op": "check", "permission": permission},
                    {"id": prefix + "unused_return", "op": "return", "src": None},
                ],
            )
        ],
    )


def field_case(seed: int, changed: bool = False, preserve: bool = False) -> dict[str, Any]:
    profile = profile_for_seed(seed)
    preserve_mode = _preserve_mode(seed, preserve)
    p = f"F{seed}_"
    guard = p + "Guard"
    service = p + "Service"

    wrapper_methods: list[dict[str, Any]] = []
    for index in range(profile.structure_depth):
        wrapper_methods.append(
            _method(
                f"pass_{index}",
                [_var("value", guard)],
                guard,
                [],
                [{"id": f"{p}pass_return_{index}", "op": "return", "src": "value"}],
            )
        )

    opaque_methods, opaque_entry = _opaque_chain(p, service, profile.opaque_depth)
    fields = [("selected", guard), ("other", guard)] + [
        (f"decoy_{index}", guard) for index in range(profile.width)
    ]
    if preserve_mode == 2:
        fields.append(("zz_unused", guard))
    locals_: list[dict[str, str]] = [_var("a", guard), _var("b", guard), _var("x", guard)]
    body: list[dict[str, Any]] = [
        {"id": p + "new_a", "op": "new", "dst": "a", "class": p + "GuardA"},
        {"id": p + "new_b", "op": "new", "dst": "b", "class": p + "GuardB"},
        {"id": p + "store_a", "op": "store", "base": "this", "field": f"{service}.selected", "src": "a"},
        {"id": p + "store_b", "op": "store", "base": "this", "field": f"{service}.other", "src": "b"},
    ]
    for index in range(profile.width):
        name = f"decoy_value_{index}"
        locals_.append(_var(name, guard))
        cls = p + ("GuardA" if index % 2 == 0 else "GuardB")
        src = "a" if index % 2 == 0 else "b"
        body.extend(
            [
                {"id": f"{p}new_decoy_{index}", "op": "new", "dst": name, "class": cls},
                {
                    "id": f"{p}store_decoy_{index}",
                    "op": "store",
                    "base": "this",
                    "field": f"{service}.decoy_{index}",
                    "src": name,
                },
                # Keep the original A/B values live as well: the allocation is
                # not a mere unreachable size perturbation.
                {"id": f"{p}refresh_decoy_{index}", "op": "move", "dst": name, "src": src},
            ]
        )
    load_field = f"{service}.other" if changed else f"{service}.selected"
    body.append({"id": p + "load", "op": "load", "dst": "x", "base": "this", "field": load_field})
    current = "x"
    for index in range(profile.structure_depth):
        dst = f"wrapped_{index}"
        locals_.append(_var(dst, guard))
        body.append(
            {
                "id": f"{p}pass_call_{index}",
                "op": "direct",
                "dst": dst,
                "target": f"{service}.pass_{index}",
                "args": [current],
            }
        )
        current = dst
    extra_locals, flow, current = _flow_suffix(
        p, guard, current, profile.alias_depth, preserve_mode == 0
    )
    locals_.extend(extra_locals)
    body.extend(flow)
    body.extend(
        [
            {"id": p + "invoke_guard", "op": "invoke", "dst": None, "recv": current, "selector": "guard", "args": []},
            *opaque_entry,
            {"id": p + "return", "op": "return", "src": None},
        ]
    )
    api = _method("api", [], None, locals_, body)
    classes = _guard_classes(p) + [
        _cls(service, None, fields, [api, *wrapper_methods, *opaque_methods])
    ]
    if preserve_mode == 1:
        classes.append(_unused_class(p))
    return {
        "language": "bfil-1",
        "permissions": ["PERM_A", "PERM_B", "PERM_C"],
        "classes": classes,
        "services": [{"name": p + "svc", "declared_class": service, "implementation_class": service}],
        "entries": [{"name": p + "API", "service": p + "svc", "selector": "api", "arg_classes": []}],
    }


def context_case(seed: int, changed: bool = False, preserve: bool = False) -> dict[str, Any]:
    profile = profile_for_seed(seed)
    preserve_mode = _preserve_mode(seed, preserve)
    p = f"C{seed}_"
    guard = p + "Guard"
    helper_base = p + "Helper"
    service = p + "Service"

    helper_method = _method(
        "identity",
        [_var("value", guard)],
        guard,
        [],
        [{"id": p + "id_return", "op": "return", "src": "value"}],
    )
    helper_classes = [_cls(helper_base, None, [], [helper_method])]
    helper_impl = helper_base
    for index in range(profile.structure_depth):
        child = f"{p}HelperLayer{index}"
        helper_classes.append(_cls(child, helper_impl, [], []))
        helper_impl = child

    opaque_methods, opaque_entry = _opaque_chain(p, service, profile.opaque_depth)
    locals_: list[dict[str, str]] = [
        _var("h", helper_base),
        _var("a", guard),
        _var("b", guard),
        _var("ra", guard),
        _var("rb", guard),
    ]
    body: list[dict[str, Any]] = [
        {"id": p + "new_h", "op": "new", "dst": "h", "class": helper_impl},
        {"id": p + "new_a", "op": "new", "dst": "a", "class": p + "GuardA"},
        {"id": p + "new_b", "op": "new", "dst": "b", "class": p + "GuardB"},
        {"id": p + "call_a", "op": "invoke", "dst": "ra", "recv": "h", "selector": "identity", "args": ["a"]},
        {"id": p + "call_b", "op": "invoke", "dst": "rb", "recv": "h", "selector": "identity", "args": ["b"]},
    ]
    for index in range(profile.width):
        dst = f"decoy_result_{index}"
        locals_.append(_var(dst, guard))
        body.append(
            {
                "id": f"{p}decoy_call_{index}",
                "op": "invoke",
                "dst": dst,
                "recv": "h",
                "selector": "identity",
                "args": ["a" if index % 2 == 0 else "b"],
            }
        )
    chosen = "rb" if changed else "ra"
    extra_locals, flow, chosen = _flow_suffix(
        p, guard, chosen, profile.alias_depth, preserve_mode == 0
    )
    locals_.extend(extra_locals)
    body.extend(flow)
    body.extend(
        [
            {"id": p + "invoke_guard", "op": "invoke", "dst": None, "recv": chosen, "selector": "guard", "args": []},
            *opaque_entry,
            {"id": p + "return", "op": "return", "src": None},
        ]
    )
    api = _method("api", [], None, locals_, body)
    classes = _guard_classes(p) + helper_classes + [
        _cls(service, None, [], [api, *opaque_methods])
    ]
    if preserve_mode == 1:
        classes.append(_unused_class(p))
    elif preserve_mode == 2:
        classes.append(_cls("ZZ" + p + "UnusedHelper", helper_base, [], []))
    return {
        "language": "bfil-1",
        "permissions": ["PERM_A", "PERM_B", "PERM_C"],
        "classes": classes,
        "services": [{"name": p + "svc", "declared_class": service, "implementation_class": service}],
        "entries": [{"name": p + "API", "service": p + "svc", "selector": "api", "arg_classes": []}],
    }


def _hierarchy_impl_methods(
    prefix: str,
    owner: str,
    permission: str,
    call_depth: int,
    opaque_depth: int,
    preserve: bool,
) -> list[dict[str, Any]]:
    opaque_methods, opaque_entry = _opaque_chain(prefix, owner, opaque_depth)
    helper_methods: list[dict[str, Any]] = []
    if call_depth == 0:
        permission_ops: list[dict[str, Any]] = [
            {"id": prefix + "check", "op": "check", "permission": permission}
        ]
    else:
        permission_ops = [
            {
                "id": prefix + "call_step_0",
                "op": "direct",
                "dst": None,
                "target": f"{owner}.step_0",
                "args": [],
            }
        ]
        for index in range(call_depth):
            if index == call_depth - 1:
                ops: list[dict[str, Any]] = [
                    {"id": f"{prefix}step_check_{index}", "op": "check", "permission": permission}
                ]
            else:
                ops = [
                    {
                        "id": f"{prefix}call_step_{index + 1}",
                        "op": "direct",
                        "dst": None,
                        "target": f"{owner}.step_{index + 1}",
                        "args": [],
                    }
                ]
            ops.append({"id": f"{prefix}step_return_{index}", "op": "return", "src": None})
            helper_methods.append(_method(f"step_{index}", [], None, [], ops))

    noop_methods: list[dict[str, Any]] = []
    preserve_ops: list[dict[str, Any]] = []
    if preserve:
        noop_methods.append(
            _method(
                "preserving_noop",
                [],
                None,
                [],
                [{"id": prefix + "noop_return", "op": "return", "src": None}],
            )
        )
        preserve_ops.append(
            {
                "id": prefix + "call_preserving_noop",
                "op": "direct",
                "dst": None,
                "target": f"{owner}.preserving_noop",
                "args": [],
            }
        )
    api = _method(
        "api",
        [],
        None,
        [],
        [*preserve_ops, *permission_ops, *opaque_entry, {"id": prefix + "api_return", "op": "return", "src": None}],
    )
    return [api, *helper_methods, *opaque_methods, *noop_methods]


def hierarchy_case(seed: int, changed: bool = False, preserve: bool = False) -> dict[str, Any]:
    profile = profile_for_seed(seed)
    preserve_mode = _preserve_mode(seed, preserve)
    p = f"H{seed}_"
    base = p + "BaseService"
    base_classes = [
        _cls(base, None, [], [_method("api", [], None, [], [{"id": p + "base_return", "op": "return", "src": None}])])
    ]
    parent = base
    for index in range(profile.structure_depth):
        child = f"{p}BaseLayer{index}"
        base_classes.append(_cls(child, parent, [], []))
        parent = child

    a = p + "ImplA"
    b = p + "ImplB"
    selected = b if changed else a
    classes = list(base_classes)
    classes.append(
        _cls(
            a,
            parent,
            [],
            _hierarchy_impl_methods(
                p + "A_",
                a,
                "PERM_A",
                profile.alias_depth,
                profile.opaque_depth if selected == a else 0,
                preserve_mode == 0 and selected == a,
            ),
        )
    )
    classes.append(
        _cls(
            b,
            parent,
            [],
            _hierarchy_impl_methods(
                p + "B_",
                b,
                "PERM_B",
                profile.alias_depth,
                profile.opaque_depth if selected == b else 0,
                preserve_mode == 0 and selected == b,
            ),
        )
    )
    for index in range(profile.width):
        owner = f"{p}Decoy{index}"
        permission = "PERM_A" if index % 2 == 0 else "PERM_B"
        classes.append(
            _cls(
                owner,
                parent,
                [],
                _hierarchy_impl_methods(
                    f"{p}D{index}_", owner, permission, profile.alias_depth, 0, False
                ),
            )
        )
    if preserve_mode == 1:
        owner = "ZZ" + p + "UnusedImpl"
        classes.append(
            _cls(owner, parent, [], _hierarchy_impl_methods(p + "ZU_", owner, "PERM_A", 0, 0, False))
        )
    elif preserve_mode == 2:
        classes.append(_cls("ZZ" + p + "UnusedLayer", parent, [], []))
    return {
        "language": "bfil-1",
        "permissions": ["PERM_A", "PERM_B", "PERM_C"],
        "classes": classes,
        "services": [{"name": p + "svc", "declared_class": base, "implementation_class": selected}],
        "entries": [{"name": p + "API", "service": p + "svc", "selector": "api", "arg_classes": []}],
    }


def revision_pair(index: int) -> tuple[str, dict[str, Any], dict[str, Any], bool]:
    if not 0 <= index < 300:
        raise ValueError("revision index")
    family = ("field", "context", "hierarchy")[index // 100]
    seed = index % 100
    changing = seed % 2 == 1
    maker = {"field": field_case, "context": context_case, "hierarchy": hierarchy_case}[family]
    old = maker(seed)
    new = maker(seed, changed=changing, preserve=not changing)
    return family, old, new, not changing


def _canonical_operation(
    op: dict[str, Any],
    *,
    variables: dict[str, str],
    classes: dict[str, str],
    fields: dict[str, str],
    methods: dict[str, str],
    selectors: dict[str, str],
    permissions: dict[str, str],
) -> tuple[Any, ...]:
    kind = op["op"]
    if kind == "new":
        return (kind, variables[op["dst"]], classes[op["class"]])
    if kind == "move":
        return (kind, variables[op["dst"]], variables[op["src"]])
    if kind == "store":
        return (kind, variables[op["base"]], fields[op["field"]], variables[op["src"]])
    if kind == "load":
        return (kind, variables[op["dst"]], variables[op["base"]], fields[op["field"]])
    if kind == "invoke":
        return (
            kind,
            None if op["dst"] is None else variables[op["dst"]],
            variables[op["recv"]],
            selectors[op["selector"]],
            tuple(variables[x] for x in op["args"]),
        )
    if kind == "direct":
        return (
            kind,
            None if op["dst"] is None else variables[op["dst"]],
            methods[op["target"]],
            tuple(variables[x] for x in op["args"]),
        )
    if kind == "check":
        return (kind, permissions[op["permission"]])
    if kind == "return":
        return (kind, None if op["src"] is None else variables[op["src"]])
    if kind == "opaque":
        return (
            kind,
            tuple(
                _canonical_operation(
                    candidate,
                    variables=variables,
                    classes=classes,
                    fields=fields,
                    methods=methods,
                    selectors=selectors,
                    permissions=permissions,
                )
                for candidate in op["candidates"]
            ),
        )
    raise ValueError("operation")


def structural_signature(document: dict[str, Any]) -> str:
    """Return a deterministic identifier-erased BFIL structural signature.

    Declaration order remains observable, but all user-selected class, method,
    field, variable, service, entry, permission, and statement identifiers are
    replaced by canonical tokens.  Statement IDs, spans, and summaries are
    intentionally ignored.  The result is a compact JSON string suitable for
    equality and diversity checks; it is not a cryptographic digest.
    """
    raw_classes = document["classes"]
    classes = {raw["name"]: f"c{index}" for index, raw in enumerate(raw_classes)}
    permissions = {name: f"p{index}" for index, name in enumerate(document["permissions"])}
    services = {raw["name"]: f"s{index}" for index, raw in enumerate(document["services"])}

    selectors: dict[str, str] = {}
    for raw in raw_classes:
        for method in raw["methods"]:
            selectors.setdefault(method["name"], f"q{len(selectors)}")

    methods: dict[str, str] = {}
    fields: dict[str, str] = {}
    for ci, raw in enumerate(raw_classes):
        for fi, field in enumerate(raw["fields"]):
            fields[f"{raw['name']}.{field['name']}"] = f"f{ci}.{fi}"
        for mi, method in enumerate(raw["methods"]):
            methods[f"{raw['name']}.{method['name']}"] = f"m{ci}.{mi}"

    class_rows: list[Any] = []
    for raw in raw_classes:
        field_rows = tuple((fields[f"{raw['name']}.{f['name']}"], classes[f["type"]]) for f in raw["fields"])
        method_rows: list[Any] = []
        for method in raw["methods"]:
            variables = {"this": "v0"}
            for item in [*method["params"], *method["locals"]]:
                variables[item["name"]] = f"v{len(variables)}"
            body = tuple(
                _canonical_operation(
                    stmt,
                    variables=variables,
                    classes=classes,
                    fields=fields,
                    methods=methods,
                    selectors=selectors,
                    permissions=permissions,
                )
                for stmt in method["body"]
            )
            method_rows.append(
                (
                    methods[f"{raw['name']}.{method['name']}"],
                    selectors[method["name"]],
                    tuple(classes[x["type"]] for x in method["params"]),
                    None if method["returns"] is None else classes[method["returns"]],
                    tuple(classes[x["type"]] for x in method["locals"]),
                    body,
                )
            )
        class_rows.append(
            (
                classes[raw["name"]],
                None if raw["super"] is None else classes[raw["super"]],
                field_rows,
                tuple(method_rows),
            )
        )

    service_rows = tuple(
        (services[x["name"]], classes[x["declared_class"]], classes[x["implementation_class"]])
        for x in document["services"]
    )
    entry_rows = tuple(
        (
            f"e{index}",
            services[x["service"]],
            selectors[x["selector"]],
            tuple(classes[y] for y in x["arg_classes"]),
        )
        for index, x in enumerate(document["entries"])
    )
    shape = (
        tuple(permissions.values()),
        tuple(class_rows),
        service_rows,
        entry_rows,
    )
    return json.dumps(shape, separators=(",", ":"))


def revision_signature(index: int) -> str:
    family, old, new, preserving = revision_pair(index)
    return json.dumps(
        [family, preserving, structural_signature(old), structural_signature(new)],
        separators=(",", ":"),
    )
