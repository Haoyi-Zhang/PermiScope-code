"""Validation for exact, bounded public-source permission-call slices.

This is intentionally not a Java frontend.  Each retained slice is a small,
line-bounded Apache-2.0 AOSP excerpt whose declared permission call is anchored
by exact text.  The semantic BFIL projection is checked separately.  Statements
outside the retained line range are not covered and no whole-method or
whole-framework guarantee follows.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import re
from typing import Any
from .source_model import parse_source
from .java_slice import extract_permission_calls

@dataclass(frozen=True)
class SliceVerdict:
    accepted: bool
    reason: str


def validate_public_slice(record: Any) -> SliceVerdict:
    def bad(x:str)->SliceVerdict:return SliceVerdict(False,x)
    if type(record) is not dict or set(record)!={"id","provenance","excerpt","anchor","source"}:
        return bad("slice-schema")
    if type(record["id"]) is not str or not record["id"]:return bad("slice-id")
    p=record["provenance"]
    if type(p) is not dict or set(p)!={"repository","tag","path","start_line","end_line","url","license","file_blob_sha1","excerpt_sha256"}:
        return bad("provenance-schema")
    if p["repository"]!="aosp-mirror/platform_frameworks_base" or p["tag"]!="android-14.0.0_r1" or p["license"]!="Apache-2.0":
        return bad("provenance-identity")
    if type(p["start_line"]) is not int or type(p["end_line"]) is not int or p["start_line"]>p["end_line"]:return bad("line-range")
    if type(p["file_blob_sha1"]) is not str or re.fullmatch(r"[0-9a-f]{40}",p["file_blob_sha1"]) is None:return bad("file-blob-sha1")
    if type(p["excerpt_sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}",p["excerpt_sha256"]) is None:return bad("excerpt-sha256")
    text=record["excerpt"]
    if type(text) is not str or not text.endswith("\n"):return bad("excerpt-text")
    if hashlib.sha256(text.encode("utf-8")).hexdigest()!=p["excerpt_sha256"]:return bad("excerpt-digest")
    if len(text.rstrip("\n").split("\n"))!=p["end_line"]-p["start_line"]+1:return bad("excerpt-line-count")
    a=record["anchor"]
    if type(a) is not dict or set(a)!={"primitive","literal","permission"}:return bad("anchor-schema")
    if any(type(a[k]) is not str or not a[k] for k in a):return bad("anchor-value")
    if text.count(a["primitive"])!=1 or text.count(a["literal"])!=1:return bad("anchor-cardinality")
    calls=extract_permission_calls(text)
    matching=[x for x in calls if x.primitive==a["primitive"] and x.literal==a["literal"]]
    if len(matching)!=1:return bad("lexical-anchor")
    if matching[0].permission!=a["permission"]:return bad("lexical-permission")
    try:source=parse_source(record["source"])
    except ValueError as exc:return bad("source-"+str(exc))
    checks=[s for m in source.method_map.values() for s in m.body if s["op"]=="check"]
    nonreturns=[s for m in source.method_map.values() for s in m.body if s["op"]!="return"]
    if len(checks)!=1 or len(nonreturns)!=1 or checks[0]["permission"]!=a["permission"]:
        return bad("projection-anchor")
    if tuple(source.permissions)!=(a["permission"],):return bad("projection-permissions")
    return SliceVerdict(True,"accepted")
