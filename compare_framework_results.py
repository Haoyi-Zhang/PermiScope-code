#!/usr/bin/env python3
"""Compare two BFIL campaign directories, excluding nondeterministic resource fields."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

SEMANTIC_FILES = (
    "generated-revisions.csv",
    "baseline-results.csv",
    "public-slices.csv",
    "fault-fixtures.csv",
    "structural-diversity.csv",
)


def normalized_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalized_summary(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("resources", None)
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    args = parser.parse_args()
    expected = args.expected.resolve()
    actual = args.actual.resolve()
    mismatches: list[str] = []

    for name in SEMANTIC_FILES:
        if normalized_csv(expected / name) != normalized_csv(actual / name):
            mismatches.append(name)
    if normalized_summary(expected / "summary.json") != normalized_summary(actual / "summary.json"):
        mismatches.append("summary.json (semantic fields)")

    expected_samples = sorted(p.name for p in expected.glob("sample-*.json"))
    actual_samples = sorted(p.name for p in actual.glob("sample-*.json"))
    if expected_samples != actual_samples:
        mismatches.append("sample inventory")
    else:
        for name in expected_samples:
            if json.loads((expected / name).read_text(encoding="utf-8")) != json.loads((actual / name).read_text(encoding="utf-8")):
                mismatches.append(name)

    report = {
        "accepted": not mismatches,
        "compared_csv_files": len(SEMANTIC_FILES),
        "compared_sample_files": len(expected_samples),
        "excluded_summary_fields": ["resources"],
        "mismatches": mismatches,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
