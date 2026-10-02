"""Small lexical bridge for the retained line-bounded AOSP permission slices.

This module is deliberately *not* a Java parser.  It recognizes a narrow,
declared family of calls whose first argument is an
``android.Manifest.permission.CONSTANT`` token.  The public-slice validator
uses it only to prove that the stored BFIL check agrees with the exact retained
source lines.  Comments, aliases, string flows, control flow, and statements
outside the line range remain outside the guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

CALL_RE = re.compile(
    r"(?P<primitive>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)"
    r"\s*\(\s*(?P<literal>android\.Manifest\.permission\.[A-Z][A-Z0-9_]*)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class PermissionCall:
    primitive: str
    literal: str
    permission: str
    start_offset: int


def permission_from_literal(literal: str) -> str:
    prefix = "android.Manifest.permission."
    if not literal.startswith(prefix):
        raise ValueError("permission literal")
    return "android.permission." + literal[len(prefix):]


def extract_permission_calls(text: str) -> tuple[PermissionCall, ...]:
    if type(text) is not str:
        raise ValueError("excerpt text")
    calls = []
    for match in CALL_RE.finditer(text):
        literal = match.group("literal")
        calls.append(PermissionCall(
            primitive=match.group("primitive"),
            literal=literal,
            permission=permission_from_literal(literal),
            start_offset=match.start(),
        ))
    return tuple(calls)
