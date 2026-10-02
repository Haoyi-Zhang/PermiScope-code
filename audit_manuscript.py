#!/usr/bin/env python3
"""Offline integrity audit for the bibliography and public-source evidence.

The audit deliberately performs no network access.  The CSV files record the
publisher/official URLs that were checked during curation; this script checks
that the retained manuscript, audit inventories, and packaged excerpts agree.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

EXPECTED_REFERENCE_COUNT = 68
EXPECTED_PUBLIC_SLICE_COUNT = 12
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
HEX40_RE = re.compile(r"[0-9a-f]{40}\Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")


class AuditError(ValueError):
    pass


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise AuditError(f"empty csv: {path}")
    return rows


def _unique(values: Iterable[str], label: str) -> None:
    materialized = list(values)
    if len(materialized) != len(set(materialized)):
        raise AuditError(f"duplicate {label}")


def _plain_title(value: str) -> str:
    # The bibliography uses only a small amount of TeX.  Normalize enough to
    # compare retained titles without trying to implement a TeX parser.
    value = value.replace("\\&", " and ").replace("~", " ")
    value = re.sub(r"\\['\"`^~=.uvHckbdtr]\s*\{?([A-Za-z])\}?", r"\1", value)
    value = re.sub(r"\\[A-Za-z]+\*?(?:\[[^]]*\])?", " ", value)
    value = value.replace("{", "").replace("}", "")
    value = value.replace("---", "-").replace("--", "-")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def parse_bibliography(path: Path) -> dict[str, tuple[str, int]]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, tuple[str, int]] = {}
    for match in re.finditer(r"\\bibitem\{([^}]+)\}\s*(.*)", text):
        key, record = match.group(1), match.group(2)
        title_match = re.search(r"``(.*?)''", record)
        if title_match is None:
            raise AuditError(f"bibliography title missing: {key}")
        if key in result:
            raise AuditError(f"duplicate bibliography key: {key}")
        # Ignore DOI-assignment years when extracting the publication year.
        before_doi = record.split("doi:", 1)[0]
        years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", before_doi)
        if not years:
            raise AuditError(f"bibliography year missing: {key}")
        result[key] = (title_match.group(1).rstrip(","), int(years[-1]))
    return result


def parse_citations(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
    keys: set[str] = set()
    for match in re.finditer(r"\\cite\s*\{([^}]*)\}", text, re.DOTALL):
        for key in match.group(1).split(","):
            key = key.strip()
            if key:
                keys.add(key)
    return keys


def audit_references(repo_root: Path, paper_dir: Path | None = None) -> dict[str, int]:
    rows = _read_csv(repo_root / "reference_audit.csv")
    required = {
        "key", "title", "year", "persistent_id", "verification_url",
        "verification_source", "relevance_role", "status", "access_date", "notes",
    }
    if set(rows[0]) != required:
        raise AuditError("reference audit schema")
    if len(rows) != EXPECTED_REFERENCE_COUNT:
        raise AuditError(f"reference count: {len(rows)}")
    _unique((row["key"] for row in rows), "reference key")
    _unique((row["title"] for row in rows), "reference title")
    for row in rows:
        key = row["key"]
        if not re.fullmatch(r"[a-z][a-z0-9-]*", key):
            raise AuditError(f"reference key syntax: {key}")
        if not row["title"].strip() or not row["relevance_role"].strip():
            raise AuditError(f"reference content: {key}")
        try:
            year = int(row["year"])
        except ValueError as exc:
            raise AuditError(f"reference year: {key}") from exc
        if not 1970 <= year <= 2026:
            raise AuditError(f"reference year range: {key}")
        if row["status"] != "verified":
            raise AuditError(f"unverified reference: {key}")
        if not DATE_RE.fullmatch(row["access_date"]):
            raise AuditError(f"access date: {key}")
        if not row["verification_url"].startswith("https://"):
            raise AuditError(f"verification url: {key}")
        if not row["persistent_id"].strip() or not row["verification_source"].strip():
            raise AuditError(f"reference provenance: {key}")
        if row["persistent_id"].lower().startswith("doi:"):
            doi = row["persistent_id"][4:]
            if row["verification_url"].lower() != "https://doi.org/" + doi.lower():
                raise AuditError(f"doi/url mismatch: {key}")
    if paper_dir is not None:
        bibliography = parse_bibliography(paper_dir / "references.tex")
        citations = parse_citations(paper_dir / "main.tex")
        audit_by_key = {row["key"]: row for row in rows}
        if len(bibliography) != EXPECTED_REFERENCE_COUNT:
            raise AuditError(f"bibliography count: {len(bibliography)}")
        if set(bibliography) != set(audit_by_key):
            raise AuditError("bibliography/audit key mismatch")
        undefined = citations - set(bibliography)
        uncited = set(bibliography) - citations
        if undefined:
            raise AuditError("undefined citations: " + ",".join(sorted(undefined)))
        if uncited:
            raise AuditError("uncited bibliography: " + ",".join(sorted(uncited)))
        for key, (title, year) in bibliography.items():
            if _plain_title(title) != _plain_title(audit_by_key[key]["title"]):
                raise AuditError(f"title mismatch: {key}")
            if year != int(audit_by_key[key]["year"]):
                raise AuditError(f"year mismatch: {key}")
    return {"references": len(rows)}


def audit_public_sources(repo_root: Path) -> dict[str, int]:
    rows = _read_csv(repo_root / "public_source_audit.csv")
    required = {
        "id", "repository", "tag", "path", "start_line", "end_line",
        "file_blob_sha1", "excerpt_sha256", "primitive", "literal",
        "permission", "verification_url", "verification_method", "access_date", "status",
    }
    if set(rows[0]) != required:
        raise AuditError("public source audit schema")
    if len(rows) != EXPECTED_PUBLIC_SLICE_COUNT:
        raise AuditError(f"public source count: {len(rows)}")
    _unique((row["id"] for row in rows), "public source id")
    row_by_id = {row["id"]: row for row in rows}
    paths = sorted((repo_root / "inputs" / "public-slices").glob("*.json"))
    if len(paths) != EXPECTED_PUBLIC_SLICE_COUNT:
        raise AuditError(f"public slice file count: {len(paths)}")
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        sid = record.get("id")
        if sid not in row_by_id:
            raise AuditError(f"missing public audit row: {sid}")
        row = row_by_id[sid]
        provenance = record["provenance"]
        anchor = record["anchor"]
        expected = {
            "repository": provenance["repository"],
            "tag": provenance["tag"],
            "path": provenance["path"],
            "start_line": str(provenance["start_line"]),
            "end_line": str(provenance["end_line"]),
            "file_blob_sha1": provenance["file_blob_sha1"],
            "excerpt_sha256": provenance["excerpt_sha256"],
            "primitive": anchor["primitive"],
            "literal": anchor["literal"],
            "permission": anchor["permission"],
            "verification_url": provenance["url"],
        }
        for field, value in expected.items():
            if row[field] != value:
                raise AuditError(f"public source mismatch {sid}: {field}")
        if row["status"] != "verified" or not DATE_RE.fullmatch(row["access_date"]):
            raise AuditError(f"public source status/date: {sid}")
        if not HEX40_RE.fullmatch(row["file_blob_sha1"]):
            raise AuditError(f"public source blob hash: {sid}")
        if not HEX64_RE.fullmatch(row["excerpt_sha256"]):
            raise AuditError(f"public source excerpt hash: {sid}")
        actual = hashlib.sha256(record["excerpt"].encode("utf-8")).hexdigest()
        if actual != row["excerpt_sha256"]:
            raise AuditError(f"public source digest: {sid}")
    return {"public_sources": len(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--paper-dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = {
            **audit_references(args.repo_root, args.paper_dir),
            **audit_public_sources(args.repo_root),
            "status": "accepted",
        }
    except (AuditError, OSError, json.JSONDecodeError, csv.Error) as exc:
        print(f"audit rejected: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
