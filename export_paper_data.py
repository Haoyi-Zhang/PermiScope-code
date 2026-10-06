#!/usr/bin/env python3
"""Export LaTeX macros/tables from reconciled retained results.

The exporter reads, but does not modify, the retained ground-kernel and BFIL
campaign results.  It deliberately emits no claims that are not directly
encoded in those files.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from reconcile import reconcile


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _fmt_float(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def _write_table(path: Path, columns: str, heading: str, rows: list[str]) -> None:
    text = (
        "\\begin{tabular}{" + columns + "}\n"
        "\\toprule\n" + heading + r" \\" + "\n"
        "\\midrule\n" + "".join(row + r" \\" + "\n" for row in rows) +
        "\\bottomrule\n\\end{tabular}\n"
    )
    path.write_text(text, encoding="utf-8")


def export(kernel: Path, framework: Path, out: Path) -> None:
    km = reconcile(kernel)
    ks = json.loads((kernel / "run-all-summary.json").read_text(encoding="utf-8"))
    chunks = {item["chunk"]: item for item in ks["chunks"]}
    fs = json.loads((framework / "summary.json").read_text(encoding="utf-8"))
    revisions = _read_csv(framework / "generated-revisions.csv")
    public = _read_csv(framework / "public-slices.csv")
    faults = _read_csv(framework / "fault-fixtures.csv")
    out.mkdir(parents=True, exist_ok=True)

    definitions = {
        # BFIL campaign.
        "FrameworkCaseCount": f"{fs['cases']['total']:,}",
        "GeneratedRevisionCount": f"{fs['cases']['generated_revisions']:,}",
        "PublicSliceCount": f"{fs['cases']['public_slices']:,}",
        "FrameworkFaultCount": f"{fs['cases']['fault_fixtures']:,}",
        "PreservingRevisionCount": f"{fs['revisions']['semantic_preserving']:,}",
        "ChangingRevisionCount": f"{fs['revisions']['semantic_changing']:,}",
        "TransportExactCount": f"{fs['revisions']['conservative_transport_exact']:,}",
        "TransportCompletionCount": f"{fs['revisions']['completion_required']:,}",
        "StructuralPairCount": f"{fs['diversity']['identifier_erased_revision_pairs']:,}",
        "StructuralProgramCount": f"{fs['diversity']['identifier_erased_new_programs']:,}",
        "MeanReusePercent": _fmt_float(100 * fs['revisions']['mean_reused_fraction'], 1),
        "ReusedNodeCount": f"{fs['revisions']['reused_nodes']:,}",
        "CertificateNodeCount": f"{fs['revisions']['certificate_nodes']:,}",
        "UnresolvedQueryCount": f"{fs['classification']['unresolved_queries']:,}",
        "CompletionModelCount": f"{fs['classification']['completion_models']:,}",
        "EndpointExactCount": f"{fs['classification']['endpoint_envelope_exact']:,}",
        "FrameworkCPUTime": _fmt_float(fs['resources']['cpu_seconds'], 3),
        "FrameworkWallTime": _fmt_float(fs['resources']['wall_seconds'], 3),
        "FrameworkPeakRSS": f"{fs['resources']['process_peak_rss_kib']:,}",
        "FrameworkPeakMiB": _fmt_float(fs['resources']['process_peak_rss_kib'] / 1024, 2),
        "FrameworkCheckerSteps": f"{fs['counters']['checker_steps']:,}",
        "FrameworkGraphOperations": f"{fs['counters']['graph_operations']:,}",
        "FrameworkMaxMethods": f"{fs['maxima']['methods']:,}",
        "FrameworkMaxStatements": f"{fs['maxima']['statements']:,}",
        "FrameworkMaxRules": f"{fs['maxima']['upper_rules']:,}",
        "FrameworkMaxAtoms": f"{fs['maxima']['upper_atoms']:,}",
        "FrameworkMaxCertificateNodes": f"{fs['maxima']['certificate_nodes']:,}",
        # Exhaustive finite kernel.
        "ProgramCount": f"{km['programs']:,}",
        "CandidateCount": f"{km['candidate_checks']:,}",
        "RevisionCount": f"{km['revision_pairs']:,}",
        "TransportCount": f"{km['accepted_transport']:,}",
        "EqualMissCount": f"{km['equal_but_not_transported']:,}",
        "WeakMissCount": f"{km['witness_only_false_completeness']:,}",
        "QueryCount": f"{km['query_classifications']:,}",
        "CoreCount": f"{km['ordered_core_queries']:,}",
        "KernelCPUTime": _fmt_float(km['cpu_seconds'], 3),
        "KernelPeakMiB": _fmt_float(km['process_peak_rss_kib'] / 1024, 2),
    }
    (out / "metrics.tex").write_text(
        "% Derived from retained, reconciled results.\n" +
        "".join(f"\\newcommand{{\\{key}}}{{{value}}}\n" for key, value in definitions.items()),
        encoding="utf-8",
    )

    _write_table(
        out / "campaign-table.tex", "lr", r"Evidence unit & Count",
        [
            f"Generated revision pairs & {fs['cases']['generated_revisions']:,}",
            f"Line-bounded public anchors & {fs['cases']['public_slices']:,}",
            f"Prespecified fault fixtures & {fs['cases']['fault_fixtures']:,}",
            f"Enumerated opaque completions & {fs['classification']['completion_models']:,}",
            f"Exhaustive four-atom programs & {km['programs']:,}",
            f"Candidate certificate checks & {km['candidate_checks']:,}",
        ],
    )

    _write_table(
        out / "resource-table.tex", "lr", r"Metric & Retained value",
        [
            f"Maximum methods / statements & {fs['maxima']['methods']:,} / {fs['maxima']['statements']:,}",
            f"Maximum atoms / rules & {fs['maxima']['upper_atoms']:,} / {fs['maxima']['upper_rules']:,}",
            f"Maximum certificate nodes & {fs['maxima']['certificate_nodes']:,}",
            f"Enumerated completion models & {fs['classification']['completion_models']:,}",
            f"Checker steps / graph operations & {fs['counters']['checker_steps']:,} / {fs['counters']['graph_operations']:,}",
            f"Process CPU seconds & {fs['resources']['cpu_seconds']:.3f}",
            f"{'Peak working set' if fs['resources'].get('platform') == 'nt' else 'Peak process RSS'} (MiB) & {fs['resources']['process_peak_rss_kib'] / 1024:.2f}",
        ],
    )

    baseline_rows = []
    for label, key in [
        ("BFIL full", "full"),
        ("Field-insensitive", "field-insensitive"),
        ("Context-insensitive", "context-insensitive"),
        ("Class hierarchy", "cha"),
    ]:
        item = fs["baselines"][key]
        baseline_rows.append(
            f"{label} & {item['exact']:,}/300 & {item['tp']:,} & {item['fp']:,} & {item['fn']:,} & {item['precision']:.2f}"
        )
    _write_table(
        out / "baseline-table.tex", "lrrrrr",
        r"Variant & Exact & TP & FP & FN & Prec.", baseline_rows,
    )

    _write_table(
        out / "framework-revision-table.tex", "lr",
        r"Revision outcome & Cases",
        [
            f"Permission set preserved & {fs['revisions']['semantic_preserving']:,}",
            f"Permission set changed & {fs['revisions']['semantic_changing']:,}",
            f"Transport prefix already exact & {fs['revisions']['conservative_transport_exact']:,}",
            f"Fresh completion required & {fs['revisions']['completion_required']:,}",
            f"Endpoint envelope exact & {fs['classification']['endpoint_envelope_exact']:,}",
            f"Queries classified unresolved & {fs['classification']['unresolved_queries']:,}",
        ],
    )

    min_cost = fs["classification"]["minimum_cost_histogram"]
    min_core = fs["classification"]["inclusion_minimal_core_size_histogram"]
    all_sizes = sorted({int(k) for k in min_cost} | {int(k) for k in min_core})
    _write_table(
        out / "unresolved-histogram-table.tex", "rrr",
        r"Size & Min. occurrences & Minimal sites",
        [f"{size} & {int(min_cost.get(str(size), 0)):,} & {int(min_core.get(str(size), 0)):,}"
         for size in all_sizes],
    )

    diversity = fs["diversity"]
    grid = diversity["profile_grid"]
    _write_table(
        out / "diversity-table.tex", "lr",
        r"Diversity obligation & Observed",
        [
            f"Identifier-erased revision-pair signatures & {diversity['identifier_erased_revision_pairs']:,}",
            f"Identifier-erased new-program signatures & {diversity['identifier_erased_new_programs']:,}",
            f"Profiles per separator family & {diversity['profiles_per_family']:,}",
            f"Alias-depth range & {grid['alias_depth'][0]}--{grid['alias_depth'][1]}",
            f"Width range & {grid['width'][0]}--{grid['width'][1]}",
            f"Inheritance/call-depth range & {grid['structure_depth'][0]}--{grid['structure_depth'][1]}",
            f"Opaque-site depth range & {grid['opaque_depth'][0]}--{grid['opaque_depth'][1]}",
        ],
    )

    _write_table(
        out / "kernel-table.tex", "lr",
        r"Ground-kernel outcome & Count",
        [
            f"Three-atom revision pairs & {km['revision_pairs']:,}",
            f"Conservative transports accepted & {km['accepted_transport']:,}",
            f"Equal model, transport rejected & {km['equal_but_not_transported']:,}",
            f"Changed model, witness-only accepted & {km['witness_only_false_completeness']:,}",
            f"Optional query classifications & {km['query_classifications']:,}",
            f"Ordered core requests & {km['ordered_core_queries']:,}",
        ],
    )

    def breakable_mono(value: str) -> str:
        value = value.replace("_", r"\_")
        value = value.replace("ManagerService", r"Manager\allowbreak{}Service")
        value = value.replace("-", r"-\allowbreak{}")
        return r"\texttt{" + value + "}"

    public_rows = []
    for row in public:
        location = f"{row['path'].split('/')[-1]}:{row['start_line']}--{row['end_line']}"
        perm = row["permission"].replace("android.permission.", "")
        public_rows.append(
            f"{breakable_mono(row['id'])} & {breakable_mono(location)} & {breakable_mono(perm)}"
        )
    _write_table(out / "public-table.tex", "p{0.24\\linewidth}p{0.39\\linewidth}p{0.27\\linewidth}",
                 r"Identifier & Retained lines & Primitive", public_rows)

    fault_rows = [
        f"{row['case']} & \\texttt{{{row['mutation']}}} & \\texttt{{{row['observed_reason'].replace('_', r'\\_')}}}"
        for row in faults
    ]
    _write_table(out / "framework-fault-table.tex", "lll", r"Case & Mutation & First rejection", fault_rows)

    family_rows = []
    for family in ("field", "context", "hierarchy"):
        rows = [row for row in revisions if row["family"] == family]
        family_rows.append(
            f"{family.capitalize()} & {len(rows)} & "
            f"{sum(row['semantic_preserving'] == 'True' for row in rows)} & "
            f"{sum(int(row['unresolved_queries']) for row in rows)} & "
            f"{max(int(row['upper_rules']) for row in rows):,}"
        )
    _write_table(out / "family-table.tex", "lrrrr", r"Family & Pairs & Preserved & Unresolved & Max rules", family_rows)

    metrics = {"kernel": km, "framework": fs}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_results", type=Path)
    parser.add_argument("--framework", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export(args.kernel_results, args.framework, args.out)
