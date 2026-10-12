"""A deliberately narrow source translator for the two owned Python fixtures.

This is an experimental bridge, not a Python or Java coverage guarantee and
not an execution sandbox. It consumes class/method syntax rather than a BFIL
document. Unsupported AST constructs are rejected, never silently skipped.
The only conditional is a declared independent enabled("site") choice; it
becomes an explicit opaque statement. Runtime comparison is restricted to
reviewed owned fixtures by the separate experiment driver.
"""
from __future__ import annotations

import ast
from typing import Any

from .source_model import parse_source


def _name(node: ast.AST) -> str:
    if not isinstance(node, ast.Name) or node.id.startswith("__"):
        raise ValueError("owned subset requires a simple name")
    return "this" if node.id == "self" else node.id


def _literal(node: ast.AST) -> str:
    if not isinstance(node, ast.Constant) or type(node.value) is not str:
        raise ValueError("owned subset requires a string literal")
    return node.value


def _type(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and node.value is None:
        return None
    if node is None:
        raise ValueError("owned subset requires type annotations")
    return _name(node)


def translate_owned(text: str, unit: str) -> dict[str, Any]:
    if type(text) is not str or len(text) > 32_768:
        raise ValueError("owned source text bound")
    tree = ast.parse(text, filename=unit)
    declarations = {}
    for node in tree.body:
        if (not isinstance(node, ast.ClassDef) or node.decorator_list or
            node.keywords or len(node.bases) > 1 or node.name.startswith("__") or
            getattr(node, "type_params", ()) or node.name in declarations):
            raise ValueError("owned subset class declaration")
        declarations[node.name] = node
    fields = {}
    for owner, cls in declarations.items():
        for node in cls.body:
            if isinstance(node, ast.AnnAssign):
                if node.value is not None or not node.simple:
                    raise ValueError("owned subset field declaration")
                field = _name(node.target)
                if (owner, field) in fields:
                    raise ValueError("duplicate owned field")
                fields[owner, field] = _type(node.annotation)
            elif not isinstance(node, ast.FunctionDef):
                raise ValueError("owned subset class member")

    def field_ref(base: str, member: str, variables: dict[str, str]):
        owner = variables[base]
        seen = set()
        while owner not in seen and owner in declarations:
            seen.add(owner)
            if (owner, member) in fields:
                return {"owner": owner, "member": member}
            bases = declarations[owner].bases
            owner = _name(bases[0]) if bases else ""
        raise ValueError("owned subset unknown field")

    permissions = set()
    classes = []
    opaque_ids = set()
    for owner, cls in declarations.items():
        methods = []
        for method in cls.body:
            if not isinstance(method, ast.FunctionDef):
                continue
            args = method.args
            if (method.decorator_list or method.name.startswith("__") or
                getattr(method, "type_params", ()) or args.posonlyargs or
                args.kwonlyargs or args.vararg or args.kwarg or args.defaults or
                not args.args or args.args[0].arg != "self" or
                args.args[0].annotation is not None):
                raise ValueError("owned subset method signature")
            params = [{"name": x.arg, "type": _type(x.annotation)} for x in args.args[1:]]
            variables = {"this": owner, **{p["name"]: p["type"] for p in params}}
            locals_ = []
            body = []

            def effect(node: ast.AST, dst: str | None = None):
                if isinstance(node, ast.Name) and dst is not None:
                    return dict(op="move", dst=dst, src=_name(node))
                if isinstance(node, ast.Attribute) and dst is not None:
                    base = _name(node.value)
                    return dict(op="load", dst=dst, base=base,
                                field=field_ref(base, node.attr, variables))
                if not isinstance(node, ast.Call) or node.keywords:
                    raise ValueError("owned subset effect")
                if isinstance(node.func, ast.Name):
                    if node.func.id in declarations and not node.args and dst is not None:
                        return dict(op="new", dst=dst, **{"class": node.func.id})
                    if node.func.id == "check" and len(node.args) == 1 and dst is None:
                        permission = _literal(node.args[0])
                        permissions.add(permission)
                        return dict(op="check", permission=permission)
                    raise ValueError("owned subset free call")
                if isinstance(node.func, ast.Attribute):
                    recv = _name(node.func.value)
                    call_args = [_name(x) for x in node.args]
                    if recv == "this":
                        return dict(op="direct", dst=dst,
                            target={"owner": owner, "member": node.func.attr}, args=call_args)
                    return dict(op="invoke", dst=dst, recv=recv,
                                selector=node.func.attr, args=call_args)
                raise ValueError("owned subset call target")

            def statement(node: ast.stmt, index: int):
                sid = f"{owner}:{method.name}:{index}"
                if isinstance(node, ast.AnnAssign) and node.simple and node.value is not None:
                    dst = _name(node.target)
                    if dst in variables:
                        raise ValueError("owned subset forbids local reassignment")
                    variables[dst] = _type(node.annotation)
                    locals_.append(dict(name=dst, type=variables[dst]))
                    out = effect(node.value, dst)
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute):
                    target = node.targets[0]
                    base = _name(target.value)
                    out = dict(op="store", base=base,
                               field=field_ref(base, target.attr, variables), src=_name(node.value))
                elif isinstance(node, ast.Expr):
                    out = effect(node.value)
                elif isinstance(node, ast.Return):
                    out = dict(op="return", src=None if node.value is None else _name(node.value))
                elif isinstance(node, ast.If):
                    test = node.test
                    if (node.orelse or not isinstance(test, ast.Call) or
                        not isinstance(test.func, ast.Name) or test.func.id != "enabled" or
                        test.keywords or len(test.args) != 1 or not node.body):
                        raise ValueError("owned subset conditional")
                    sid = _literal(test.args[0])
                    if sid in opaque_ids:
                        raise ValueError("duplicate owned opaque site")
                    opaque_ids.add(sid)
                    candidates = []
                    for candidate in node.body:
                        if not isinstance(candidate, ast.Expr):
                            raise ValueError("owned subset opaque candidate")
                        op = effect(candidate.value)
                        if op["op"] not in {"check", "direct", "invoke"}:
                            raise ValueError("owned subset opaque effect")
                        candidates.append(op)
                    out = dict(op="opaque", candidates=candidates)
                else:
                    raise ValueError("owned subset statement")
                return dict(id=sid, span=dict(unit=unit, start_line=node.lineno,
                    end_line=node.end_lineno), **out)

            for index, node in enumerate(method.body):
                # An early return would have a kill/control-flow meaning that
                # BFIL lacks. The fixtures use only terminal returns.
                if isinstance(node, ast.Return) and index != len(method.body) - 1:
                    raise ValueError("owned subset requires terminal returns")
                body.append(statement(node, index))
            methods.append(dict(name=method.name, params=params, returns=_type(method.returns),
                                locals=locals_, body=body))
        classes.append(dict(name=owner, super=_name(cls.bases[0]) if cls.bases else None,
            fields=[dict(name=f, type=t) for (o, f), t in fields.items() if o == owner], methods=methods))
    document = dict(language="bfil-1", permissions=sorted(permissions), classes=classes,
        services=[dict(name="service", declared_class="Service", implementation_class="Service")],
        entries=[dict(name="API", service="service", selector="run", arg_classes=[])])
    parse_source(document)
    return document
