#!/usr/bin/env python3
"""Reconcile a completed BFIL 336-case campaign from its serialized results."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_BASELINES = ("full", "field-insensitive", "context-insensitive", "cha")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_bool(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"invalid boolean {value!r}")


def as_int(value: str) -> int:
    return int(value)


def fail(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    root = args.results.resolve()
    errors: list[str] = []

    required = {
        "generated-revisions.csv",
        "baseline-results.csv",
        "public-slices.csv",
        "fault-fixtures.csv",
        "structural-diversity.csv",
        "summary.json",
    }
    present = {p.name for p in root.iterdir() if p.is_file()}
    fail(errors, required <= present, f"missing files: {sorted(required - present)}")
    if errors:
        raise SystemExit("\n".join(errors))

    revisions = read_csv(root / "generated-revisions.csv")
    baselines = read_csv(root / "baseline-results.csv")
    public = read_csv(root / "public-slices.csv")
    faults = read_csv(root / "fault-fixtures.csv")
    structures = read_csv(root / "structural-diversity.csv")
    summary: dict[str, Any] = json.loads((root / "summary.json").read_text(encoding="utf-8"))

    fail(errors, len(revisions) == 300, f"revision rows: {len(revisions)}")
    fail(errors, len(baselines) == 1200, f"baseline rows: {len(baselines)}")
    fail(errors, len(public) == 12, f"public rows: {len(public)}")
    fail(errors, len(faults) == 24, f"fault rows: {len(faults)}")
    fail(errors, len(structures) == 300, f"structure rows: {len(structures)}")
    fail(errors, sorted(as_int(row["case"]) for row in revisions) == list(range(300)), "revision case inventory")
    fail(errors, sorted(as_int(row["case"]) for row in structures) == list(range(300)), "structure case inventory")
    pair_shapes={(row["family"],row["semantic_preserving"],row["old_shape"],row["new_shape"]) for row in structures}
    new_shapes={row["new_shape"] for row in structures}
    fail(errors, len(pair_shapes) == 300, "identifier-erased revision-pair diversity")
    fail(errors, len(new_shapes) == 300, "identifier-erased new-program diversity")
    for family in ("field","context","hierarchy"):
        rows=[row for row in structures if row["family"] == family]
        profiles={(as_int(row["alias_depth"]),as_int(row["width"]),as_int(row["structure_depth"])) for row in rows}
        fail(errors, len(rows) == 100 and len(profiles) == 100, f"profile grid {family}")

    grouped: dict[int, list[dict[str, str]]] = {i: [] for i in range(300)}
    for row in baselines:
        case = as_int(row["case"])
        if case in grouped:
            grouped[case].append(row)
        else:
            errors.append(f"unexpected baseline case {case}")
    for case, rows in grouped.items():
        fail(errors, sorted(row["baseline"] for row in rows) == sorted(EXPECTED_BASELINES),
             f"baseline inventory case {case}")

    preserving = sum(as_bool(row["semantic_preserving"]) for row in revisions)
    changing = len(revisions) - preserving
    transport_exact = sum(as_bool(row["transport_exact_without_completion"]) for row in revisions)
    unresolved = sum(as_int(row["unresolved_queries"]) for row in revisions)
    cost_hist = Counter(
        row["minimum_unresolved_cost"]
        for row in revisions
        if row["minimum_unresolved_cost"] != ""
    )
    core_hist = Counter(
        row["minimum_unresolved_core_size"]
        for row in revisions
        if row["minimum_unresolved_core_size"] != ""
    )
    completion_models = sum(as_int(row["completion_models"]) for row in revisions)
    endpoint_exact = sum(as_bool(row["endpoint_envelope_exact"]) for row in revisions)
    max_opaque_sites = max(as_int(row["opaque_sites"]) for row in revisions)
    reused = sum(as_int(row["reused_nodes"]) for row in revisions)
    nodes = sum(as_int(row["new_certificate_nodes"]) for row in revisions)

    dimensions = (
        "methods", "fields", "statements", "lower_atoms", "lower_rules",
        "upper_atoms", "upper_rules", "premise_incidences", "certificate_nodes",
    )
    maxima = {key: max(as_int(row[key]) for row in revisions) for key in dimensions}

    aggregate: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_BASELINES:
        rows = [row for row in baselines if row["baseline"] == name]
        tp = sum(as_int(row["tp"]) for row in rows)
        fp = sum(as_int(row["fp"]) for row in rows)
        fn = sum(as_int(row["fn"]) for row in rows)
        exact = sum(as_bool(row["exact"]) for row in rows)
        aggregate[name] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "exact": exact,
            "precision": tp / (tp + fp) if tp + fp else 1.0,
            "recall": tp / (tp + fn) if tp + fn else 1.0,
        }

    expected_cases = {"generated_revisions": 300, "public_slices": 12, "fault_fixtures": 24, "total": 336}
    fail(errors, summary.get("cases") == expected_cases, "summary case counts")
    revisions_summary = summary.get("revisions", {})
    fail(errors, revisions_summary.get("semantic_preserving") == preserving, "summary preserving")
    fail(errors, revisions_summary.get("semantic_changing") == changing, "summary changing")
    fail(errors, revisions_summary.get("conservative_transport_exact") == transport_exact, "summary transport exact")
    exact_preserving=sum(as_bool(row["transport_exact_without_completion"]) and as_bool(row["semantic_preserving"]) for row in revisions)
    exact_changing=sum(as_bool(row["transport_exact_without_completion"]) and not as_bool(row["semantic_preserving"]) for row in revisions)
    fail(errors, revisions_summary.get("conservative_transport_exact_preserving") == exact_preserving, "summary exact preserving")
    fail(errors, revisions_summary.get("conservative_transport_exact_changing") == exact_changing, "summary exact changing")
    fail(errors, revisions_summary.get("completion_required") == 300-transport_exact, "summary completion required")
    fail(errors, revisions_summary.get("reused_nodes") == reused, "summary reused nodes")
    fail(errors, revisions_summary.get("certificate_nodes") == nodes, "summary certificate nodes")
    observed_fraction = revisions_summary.get("mean_reused_fraction")
    expected_fraction = reused / nodes if nodes else 0.0
    fail(errors, isinstance(observed_fraction, (int, float)) and math.isclose(observed_fraction, expected_fraction, rel_tol=0, abs_tol=1e-15),
         "summary reuse fraction")
    diversity=summary.get("diversity", {})
    fail(errors, diversity.get("identifier_erased_revision_pairs") == len(pair_shapes), "summary revision-pair diversity")
    fail(errors, diversity.get("identifier_erased_new_programs") == len(new_shapes), "summary new-program diversity")
    fail(errors, diversity.get("profiles_per_family") == 100, "summary profiles per family")
    fail(errors, summary.get("classification", {}).get("unresolved_queries") == unresolved, "summary unresolved count")
    fail(errors, summary.get("classification", {}).get("minimum_cost_histogram") == dict(sorted(cost_hist.items())),
         "summary cost histogram")
    fail(errors, summary.get("classification", {}).get("inclusion_minimal_core_size_histogram") == dict(sorted(core_hist.items())),
         "summary core-size histogram")
    fail(errors, summary.get("classification", {}).get("completion_models") == completion_models,
         "summary completion models")
    fail(errors, summary.get("classification", {}).get("endpoint_envelope_exact") == endpoint_exact,
         "summary endpoint exact")
    fail(errors, summary.get("classification", {}).get("max_opaque_sites") == max_opaque_sites,
         "summary max opaque sites")
    fail(errors, summary.get("maxima") == maxima, "summary maxima")
    fail(errors, summary.get("baselines") == aggregate, "summary baseline aggregates")
    fail(errors, summary.get("errors") == 0, "summary errors")

    for row in public:
        fail(errors, as_bool(row["slice_anchor_accepted"]), f"public anchor {row['id']}")
        fail(errors, as_bool(row["lexical_projection_accepted"]), f"public lexical projection {row['id']}")
        fail(errors, as_bool(row["source_evidence_accepted"]), f"public evidence {row['id']}")
        fail(errors, as_int(row["must_queries"]) == 1, f"public must count {row['id']}")
    fail(errors, len({row["id"] for row in public}) == 12, "public id uniqueness")

    for row in faults:
        fail(errors, as_bool(row["rejected"]), f"fault not rejected {row['case']}")
        fail(errors, as_bool(row["passed"]), f"fault did not match {row['case']}")
        fail(errors, row["expected_reason"] == row["observed_reason"], f"fault reason {row['case']}")
    fail(errors, len({row["case"] for row in faults}) == 24, "fault id uniqueness")

    report = {
        "accepted": not errors,
        "errors": errors,
        "files_checked": len(required),
        "rows_checked": len(revisions) + len(baselines) + len(public) + len(faults) + len(structures),
        "recomputed": {
            "semantic_preserving": preserving,
            "semantic_changing": changing,
            "transport_exact": transport_exact,
            "mean_reused_fraction": expected_fraction,
            "unresolved_queries": unresolved,
            "minimum_cost_histogram": dict(sorted(cost_hist.items())),
            "inclusion_minimal_core_size_histogram": dict(sorted(core_hist.items())),
            "completion_models": completion_models,
            "endpoint_envelope_exact": endpoint_exact,
            "max_opaque_sites": max_opaque_sites,
            "identifier_erased_revision_pairs": len(pair_shapes),
            "identifier_erased_new_programs": len(new_shapes),
            "baselines": aggregate,
            "maxima": maxima,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
