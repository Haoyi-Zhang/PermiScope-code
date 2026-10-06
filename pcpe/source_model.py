"""Strict model for the bounded framework intermediate language (BFIL-1).

BFIL is deliberately finite and source-facing: classes use single inheritance,
methods contain typed monotone flow statements, service entries select concrete
implementations, and unsupported source fragments appear explicitly as opaque
statements with declared candidate effects.  This module is part of the declared trusted parsing/type-model base shared by
the producer and consumer.  ``source_checker.py`` independently repeats the
source-to-rule lowering but deliberately reuses this strict parser and resolver.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

LANGUAGE = "bfil-1"
MAX_CLASSES = 64
MAX_METHODS = 400
MAX_FIELDS = 2_000
MAX_STATEMENTS = 4_000
MAX_ENTRIES = 64
MAX_PERMISSIONS = 128
MAX_ARGS = 8
MAX_LOCALS = 32
MAX_CANDIDATES = 8

NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.$:-")


def member_key(owner: str, member: str) -> str:
    """Injective serialization of a structured declaration identity.

    A dot is legal in either component, so dotted display names are not keys.
    JSON delimiters cannot occur in source names.
    """
    return json.dumps([owner, member], separators=(",", ":"))


def _member_reference(raw: Any, label: str) -> str:
    if type(raw) is dict:
        ref = _exact(raw, {"owner", "member"}, label)
        return member_key(_name(ref["owner"], label + " owner", limit=64),
                          _name(ref["member"], label + " member", limit=48))
    return _name(raw, label, limit=96)


def _resolve_reference(reference: str, inventory: dict[str, Any], label: str) -> str:
    if reference in inventory:
        return reference
    # Backward-compatible dotted references are accepted only if unique.
    matches = [item.key for item in inventory.values()
               if f"{item.owner}.{item.name}" == reference]
    if len(matches) > 1:
        raise ValueError("ambiguous " + label + " reference")
    return matches[0] if matches else reference


def _name(value: Any, label: str, *, limit: int = 96) -> str:
    if type(value) is not str or not value or len(value) > limit or any(c not in NAME_CHARS for c in value):
        raise ValueError(f"invalid {label}")
    return value


def _exact(d: Any, keys: set[str], label: str, optional: set[str] | None = None) -> dict[str, Any]:
    if type(d) is not dict:
        raise ValueError(f"{label} must be an object")
    optional = optional or set()
    if not keys <= set(d) or not set(d) <= keys | optional:
        raise ValueError(f"{label} schema")
    return d


def _list(value: Any, label: str, maximum: int) -> list[Any]:
    if type(value) is not list or len(value) > maximum:
        raise ValueError(f"{label} bound or type")
    return value


@dataclass(frozen=True)
class Variable:
    name: str
    type: str


@dataclass(frozen=True)
class Field:
    owner: str
    name: str
    type: str

    @property
    def key(self) -> str:
        return member_key(self.owner, self.name)


@dataclass(frozen=True)
class Method:
    owner: str
    name: str
    params: tuple[Variable, ...]
    returns: str | None
    locals: tuple[Variable, ...]
    body: tuple[dict[str, Any], ...]

    @property
    def key(self) -> str:
        return member_key(self.owner, self.name)

    @property
    def variables(self) -> dict[str, str]:
        out = {"this": self.owner}
        for item in self.params + self.locals:
            out[item.name] = item.type
        return out


@dataclass(frozen=True)
class ClassDef:
    name: str
    super: str | None
    fields: tuple[Field, ...]
    methods: tuple[Method, ...]


@dataclass(frozen=True)
class Service:
    name: str
    declared_class: str
    implementation_class: str


@dataclass(frozen=True)
class Entry:
    name: str
    service: str
    selector: str
    arg_classes: tuple[str, ...]


@dataclass(frozen=True)
class SourceProgram:
    permissions: tuple[str, ...]
    classes: tuple[ClassDef, ...]
    services: tuple[Service, ...]
    entries: tuple[Entry, ...]

    @property
    def class_map(self) -> dict[str, ClassDef]:
        return {x.name: x for x in self.classes}

    @property
    def method_map(self) -> dict[str, Method]:
        return {m.key: m for c in self.classes for m in c.methods}

    @property
    def field_map(self) -> dict[str, Field]:
        return {f.key: f for c in self.classes for f in c.fields}

    @property
    def service_map(self) -> dict[str, Service]:
        return {s.name: s for s in self.services}


def is_subtype(program: SourceProgram, child: str, parent: str) -> bool:
    classes = program.class_map
    seen: set[str] = set()
    cur: str | None = child
    while cur is not None:
        if cur == parent:
            return True
        if cur in seen or cur not in classes:
            return False
        seen.add(cur)
        cur = classes[cur].super
    return False


def resolve_method(program: SourceProgram, cls: str, selector: str) -> Method | None:
    classes = program.class_map
    seen: set[str] = set()
    cur: str | None = cls
    while cur is not None:
        if cur in seen or cur not in classes:
            return None
        seen.add(cur)
        for method in classes[cur].methods:
            if method.name == selector:
                return method
        cur = classes[cur].super
    return None


def possible_dispatch(program: SourceProgram, declared: str, selector: str) -> tuple[Method, ...]:
    found: dict[str, Method] = {}
    for cls in program.classes:
        if is_subtype(program, cls.name, declared):
            method = resolve_method(program, cls.name, selector)
            if method is not None:
                found[method.key] = method
    return tuple(found[k] for k in sorted(found))


def resolve_field(program: SourceProgram, static_class: str, field_key: str) -> Field | None:
    field = program.field_map.get(field_key)
    if field is None or not is_subtype(program, static_class, field.owner):
        return None
    return field


def _parse_var(raw: Any, label: str) -> Variable:
    d = _exact(raw, {"name", "type"}, label)
    return Variable(_name(d["name"], label + " name", limit=48), _name(d["type"], label + " type", limit=64))


def _parse_candidate(raw: Any, label: str) -> dict[str, Any]:
    if type(raw) is not dict or type(raw.get("op")) is not str:
        raise ValueError(label + " schema")
    op = raw["op"]
    schemas: dict[str, tuple[set[str], set[str]]] = {
        "check": ({"op", "permission"}, set()),
        "move": ({"op", "dst", "src"}, set()),
        "store": ({"op", "base", "field", "src"}, set()),
        "load": ({"op", "dst", "base", "field"}, set()),
        "invoke": ({"op", "dst", "recv", "selector", "args"}, set()),
        "direct": ({"op", "dst", "target", "args"}, set()),
    }
    if op not in schemas:
        raise ValueError(label + " unsupported op")
    required, optional = schemas[op]
    _exact(raw, required, label, optional)
    out = dict(raw)
    for key in ("permission", "dst", "src", "base", "recv", "selector"):
        if key in out and out[key] is not None:
            out[key] = _name(out[key], label + " " + key, limit=96)
    for key in ("field", "target"):
        if key in out:
            out[key] = _member_reference(out[key], label + " " + key)
    if "args" in out:
        args = _list(out["args"], label + " args", MAX_ARGS)
        out["args"] = [_name(x, label + " arg", limit=48) for x in args]
    return out


def _parse_statement(raw: Any, label: str) -> dict[str, Any]:
    if type(raw) is not dict or type(raw.get("op")) is not str:
        raise ValueError(label + " schema")
    op = raw["op"]
    schemas: dict[str, tuple[set[str], set[str]]] = {
        "new": ({"id", "op", "dst", "class"}, {"span"}),
        "move": ({"id", "op", "dst", "src"}, {"span"}),
        "store": ({"id", "op", "base", "field", "src"}, {"span"}),
        "load": ({"id", "op", "dst", "base", "field"}, {"span"}),
        "invoke": ({"id", "op", "dst", "recv", "selector", "args"}, {"span"}),
        "direct": ({"id", "op", "dst", "target", "args"}, {"span"}),
        "check": ({"id", "op", "permission"}, {"span"}),
        "return": ({"id", "op", "src"}, {"span"}),
        "opaque": ({"id", "op", "candidates"}, {"span", "summary"}),
    }
    if op not in schemas:
        raise ValueError(label + " unsupported op")
    required, optional = schemas[op]
    _exact(raw, required, label, optional)
    out = dict(raw)
    out["id"] = _name(out["id"], label + " id", limit=64)
    for key in ("dst", "src", "base", "recv", "selector", "permission", "class"):
        if key in out and out[key] is not None:
            out[key] = _name(out[key], label + " " + key, limit=96)
    for key in ("field", "target"):
        if key in out:
            out[key] = _member_reference(out[key], label + " " + key)
    if "args" in out:
        out["args"] = [_name(x, label + " arg", limit=48) for x in _list(out["args"], label + " args", MAX_ARGS)]
    if op == "opaque":
        out["candidates"] = [_parse_candidate(x, label + " candidate")
                               for x in _list(out["candidates"], label + " candidates", MAX_CANDIDATES)]
        if "summary" in out and (type(out["summary"]) is not str or len(out["summary"]) > 240):
            raise ValueError(label + " summary")
    if "span" in out:
        span = _exact(out["span"], {"unit", "start_line", "end_line"}, label + " span")
        _name(span["unit"], label + " span unit", limit=96)
        if type(span["start_line"]) is not int or type(span["end_line"]) is not int or not 1 <= span["start_line"] <= span["end_line"]:
            raise ValueError(label + " span lines")
    return out


def parse_source(doc: Any) -> SourceProgram:
    d = _exact(doc, {"language", "permissions", "classes", "services", "entries"}, "source")
    if d["language"] != LANGUAGE:
        raise ValueError("language")
    permissions = tuple(_name(x, "permission", limit=96)
                        for x in _list(d["permissions"], "permissions", MAX_PERMISSIONS))
    if len(set(permissions)) != len(permissions):
        raise ValueError("duplicate permission")

    raw_classes = _list(d["classes"], "classes", MAX_CLASSES)
    classes: list[ClassDef] = []
    class_names: set[str] = set()
    statement_ids: set[str] = set()
    method_count = field_count = statement_count = 0
    for ci, raw_class in enumerate(raw_classes):
        cd = _exact(raw_class, {"name", "super", "fields", "methods"}, f"class {ci}")
        cname = _name(cd["name"], "class name", limit=64)
        if cname in class_names:
            raise ValueError("duplicate class")
        class_names.add(cname)
        parent = cd["super"]
        if parent is not None:
            parent = _name(parent, "super class", limit=64)
        fields: list[Field] = []
        field_names: set[str] = set()
        for fi, raw_field in enumerate(_list(cd["fields"], "fields", MAX_FIELDS)):
            fd = _exact(raw_field, {"name", "type"}, f"field {ci}:{fi}")
            fname = _name(fd["name"], "field name", limit=48)
            if fname in field_names:
                raise ValueError("duplicate field")
            field_names.add(fname)
            fields.append(Field(cname, fname, _name(fd["type"], "field type", limit=64)))
            field_count += 1
        methods: list[Method] = []
        method_names: set[str] = set()
        for mi, raw_method in enumerate(_list(cd["methods"], "methods", MAX_METHODS)):
            md = _exact(raw_method, {"name", "params", "returns", "locals", "body"}, f"method {ci}:{mi}")
            mname = _name(md["name"], "method name", limit=48)
            if mname in method_names:
                raise ValueError("duplicate method selector")
            method_names.add(mname)
            params = tuple(_parse_var(x, "parameter") for x in _list(md["params"], "params", MAX_ARGS))
            locals_ = tuple(_parse_var(x, "local") for x in _list(md["locals"], "locals", MAX_LOCALS))
            names = [x.name for x in params + locals_]
            if "this" in names or len(set(names)) != len(names):
                raise ValueError("duplicate variable")
            returns = md["returns"]
            if returns is not None:
                returns = _name(returns, "return type", limit=64)
            body: list[dict[str, Any]] = []
            for si, raw_stmt in enumerate(_list(md["body"], "body", MAX_STATEMENTS)):
                stmt = _parse_statement(raw_stmt, f"statement {ci}:{mi}:{si}")
                if stmt["id"] in statement_ids:
                    raise ValueError("duplicate statement id")
                statement_ids.add(stmt["id"])
                body.append(stmt)
                statement_count += 1
            methods.append(Method(cname, mname, params, returns, locals_, tuple(body)))
            method_count += 1
        classes.append(ClassDef(cname, parent, tuple(fields), tuple(methods)))
    if method_count > MAX_METHODS or field_count > MAX_FIELDS or statement_count > MAX_STATEMENTS:
        raise ValueError("source aggregate bound")

    services: list[Service] = []
    service_names: set[str] = set()
    for i, raw in enumerate(_list(d["services"], "services", MAX_ENTRIES)):
        sd = _exact(raw, {"name", "declared_class", "implementation_class"}, f"service {i}")
        service = Service(_name(sd["name"], "service name", limit=64),
                          _name(sd["declared_class"], "declared class", limit=64),
                          _name(sd["implementation_class"], "implementation class", limit=64))
        if service.name in service_names:
            raise ValueError("duplicate service")
        service_names.add(service.name)
        services.append(service)

    entries: list[Entry] = []
    entry_names: set[str] = set()
    for i, raw in enumerate(_list(d["entries"], "entries", MAX_ENTRIES)):
        ed = _exact(raw, {"name", "service", "selector", "arg_classes"}, f"entry {i}")
        entry = Entry(_name(ed["name"], "entry name", limit=80),
                      _name(ed["service"], "entry service", limit=64),
                      _name(ed["selector"], "entry selector", limit=48),
                      tuple(_name(x, "entry argument class", limit=64)
                            for x in _list(ed["arg_classes"], "entry args", MAX_ARGS)))
        if entry.name in entry_names:
            raise ValueError("duplicate entry")
        entry_names.add(entry.name)
        entries.append(entry)

    program = SourceProgram(permissions, tuple(classes), tuple(services), tuple(entries))
    # Normalize every reference before type checking, without dropping any
    # declaration or silently choosing between colliding display names.
    for method in program.method_map.values():
        for statement in method.body:
            operations = [statement] + statement.get("candidates", [])
            for operation in operations:
                for key, inventory in (("field", program.field_map), ("target", program.method_map)):
                    if key in operation:
                        operation[key] = _resolve_reference(operation[key], inventory, key)
    _validate_semantics(program)
    return program


def _validate_semantics(program: SourceProgram) -> None:
    classes = program.class_map
    if not classes:
        raise ValueError("at least one class required")
    for cls in program.classes:
        if cls.super is not None and cls.super not in classes:
            raise ValueError("unknown super class")
        # cycle check
        seen: set[str] = set()
        cur: str | None = cls.name
        while cur is not None:
            if cur in seen:
                raise ValueError("inheritance cycle")
            seen.add(cur)
            cur = classes[cur].super if cur in classes else None
        for field in cls.fields:
            if field.type not in classes:
                raise ValueError("unknown field type")
        for method in cls.methods:
            if any(v.type not in classes for v in method.params + method.locals):
                raise ValueError("unknown variable type")
            if method.returns is not None and method.returns not in classes:
                raise ValueError("unknown return type")
            # Override signatures are invariant in this bounded language.
            parent = cls.super
            inherited: Method | None = None
            while parent is not None and inherited is None:
                inherited = next((m for m in classes[parent].methods if m.name == method.name), None)
                parent = classes[parent].super
            if inherited is not None:
                sig = (tuple(x.type for x in method.params), method.returns)
                inherited_sig = (tuple(x.type for x in inherited.params), inherited.returns)
                if sig != inherited_sig:
                    raise ValueError("override signature")

    if not program.permissions:
        raise ValueError("at least one permission required")
    methods = program.method_map
    for service in program.services:
        if service.declared_class not in classes or service.implementation_class not in classes:
            raise ValueError("unknown service class")
        if not is_subtype(program, service.implementation_class, service.declared_class):
            raise ValueError("service implementation subtype")
    if not program.entries:
        raise ValueError("at least one entry required")
    for entry in program.entries:
        service = program.service_map.get(entry.service)
        if service is None:
            raise ValueError("unknown entry service")
        target = resolve_method(program, service.implementation_class, entry.selector)
        declared = resolve_method(program, service.declared_class, entry.selector)
        if target is None or declared is None:
            raise ValueError("entry selector")
        if len(entry.arg_classes) != len(target.params):
            raise ValueError("entry arity")
        for actual, formal in zip(entry.arg_classes, target.params):
            if actual not in classes or not is_subtype(program, actual, formal.type):
                raise ValueError("entry argument type")

    permissions = set(program.permissions)
    fields = program.field_map
    for method in methods.values():
        variables = method.variables
        for stmt in method.body:
            _validate_operation(program, method, stmt, variables, fields, permissions, candidate=False)
            if stmt["op"] == "opaque":
                for candidate in stmt["candidates"]:
                    _validate_operation(program, method, candidate, variables, fields, permissions, candidate=True)


def _validate_operation(program: SourceProgram, method: Method, op: dict[str, Any],
                        variables: dict[str, str], fields: dict[str, Field],
                        permissions: set[str], *, candidate: bool) -> None:
    kind = op["op"]
    def var(name: str | None, label: str, allow_none: bool = False) -> str | None:
        if name is None and allow_none:
            return None
        if name not in variables:
            raise ValueError("unknown " + label)
        return variables[name]  # type: ignore[index]
    if kind == "new":
        dst_type = var(op["dst"], "new destination")
        if op["class"] not in program.class_map or not is_subtype(program, op["class"], dst_type):
            raise ValueError("new type")
    elif kind == "move":
        if not is_subtype(program, var(op["src"], "move source"), var(op["dst"], "move destination")):
            raise ValueError("move type")
    elif kind in ("store", "load"):
        base_type = var(op["base"], kind + " base")
        field = fields.get(op["field"])
        if field is None or not is_subtype(program, base_type, field.owner):
            raise ValueError(kind + " field")
        if kind == "store" and not is_subtype(program, var(op["src"], "store source"), field.type):
            raise ValueError("store type")
        if kind == "load" and not is_subtype(program, field.type, var(op["dst"], "load destination")):
            raise ValueError("load type")
    elif kind == "invoke":
        recv_type = var(op["recv"], "invoke receiver")
        target = resolve_method(program, recv_type, op["selector"])
        if target is None:
            raise ValueError("invoke selector")
        _validate_call(program, target, op["args"], op["dst"], variables)
    elif kind == "direct":
        target = methods_get(program, op["target"])
        if target is None or not is_subtype(program, method.owner, target.owner):
            raise ValueError("direct target")
        _validate_call(program, target, op["args"], op["dst"], variables)
    elif kind == "check":
        if op["permission"] not in permissions:
            raise ValueError("unknown permission")
    elif kind == "return":
        if candidate:
            raise ValueError("opaque return not supported")
        if op["src"] is None:
            if method.returns is not None:
                raise ValueError("missing return value")
        else:
            if method.returns is None or not is_subtype(program, var(op["src"], "return source"), method.returns):
                raise ValueError("return type")
    elif kind == "opaque":
        if candidate:
            raise ValueError("nested opaque")
    else:
        raise ValueError("operation")


def methods_get(program: SourceProgram, key: str) -> Method | None:
    return program.method_map.get(key)


def _validate_call(program: SourceProgram, target: Method, args: Iterable[str], dst: str | None,
                   variables: dict[str, str]) -> None:
    args = tuple(args)
    if len(args) != len(target.params):
        raise ValueError("call arity")
    for arg, formal in zip(args, target.params):
        if arg not in variables or not is_subtype(program, variables[arg], formal.type):
            raise ValueError("call argument type")
    if dst is None:
        return
    if dst not in variables or target.returns is None or not is_subtype(program, target.returns, variables[dst]):
        raise ValueError("call return type")
