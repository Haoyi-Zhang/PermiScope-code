"""Decode version-local BFIL tokens into stable, structured semantic records.

This is a producer-side transport utility, not part of the source checker.
Local e0/p0/m0/... tokens have meaning only under their own IR catalog.
"""
from __future__ import annotations

from typing import Any


class SemanticCatalog:
    def __init__(self, ir: dict[str, Any]):
        self.catalog = ir["catalog"]
        self.variant = tuple(sorted(ir["variant"].items()))
        self.tokens: dict[str, tuple[Any, ...]] = {}
        for prefix, column in (("e", "entries"), ("p", "permissions"),
                               ("m", "methods"), ("f", "fields"),
                               ("c", "contexts"), ("s", "statements")):
            for index, name in enumerate(self.catalog[column]):
                self.tokens[f"{prefix}{index}"] = (column, name)
        for index, name in enumerate(self.catalog["allocations"]):
            self.tokens[f"o{index}"] = (
                "allocations", name, self.catalog["allocation_classes"][name])
        self.tokens["fx"] = ("fields", "*")
        self.atoms = {name: self._atom(name) for name in ir["atoms"]}

    def _atom(self, name: str) -> tuple[Any, ...]:
        parts = name.split(":")
        kind = parts[0]
        schemas = {"R": "ecm", "V": "ecmvo", "H": "eofo",
                   "T": "ecmo", "P": "ep", "U": "ecms"}
        schema = schemas.get(kind)
        if schema is None or len(parts) != len(schema) + 1:
            raise ValueError("semantic atom schema")
        decoded: list[Any] = [kind]
        for position, (token, prefix) in enumerate(zip(parts[1:], schema)):
            if prefix == "v":
                method = self.tokens[parts[3]][1]
                variables = self.catalog["variables"][method]
                if not token.startswith("v") or not token[1:].isdigit():
                    raise ValueError("semantic variable token")
                decoded.append(("variables", method, variables[int(token[1:])]))
            else:
                if not token.startswith(prefix) or token not in self.tokens:
                    raise ValueError("semantic catalog token")
                decoded.append(self.tokens[token])
        return tuple(decoded)

    def atom(self, name: str) -> tuple[Any, ...]:
        return self.atoms[name]

    def fact(self, record: dict[str, Any]) -> tuple[Any, ...]:
        # Entry origins contain source names and structured method keys, not
        # local catalog tokens. No split of dotted owner/member names is used.
        return (self.variant, self.atom(record["atom"]),
                ("entry", record["source"]), record["origin"])

    def rule(self, record: dict[str, Any]) -> tuple[Any, ...]:
        prefix = "stmt:" + record["source"] + ":"
        if not record["origin"].startswith(prefix):
            raise ValueError("semantic rule origin")
        # Remove the exact statement prefix first: source names may themselves
        # contain colons and strings such as e0. Only generated suffix tokens
        # are catalog-relative.
        suffix = record["origin"][len(prefix):].split(":")
        origin = tuple(self.tokens.get(token, ("literal", token)) for token in suffix)
        return (self.variant, self.atom(record["head"]),
                frozenset(self.atom(name) for name in record["body"]),
                ("statement", record["source"]), origin,
                record["weight"], record["certainty"])
