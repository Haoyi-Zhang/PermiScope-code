"""Produce complete BFIL lower/upper evidence with ordinary and weighted proofs."""
from __future__ import annotations

from typing import Any

from .lowering import lower, Variant
from .model import parse_program
from .producer import extract
from .checker import validate
from .weighted import minimum_cost
from .weighted_checker import validate_weighted
from .source_checker import validate_source_evidence


def build_evidence(source: Any) -> tuple[dict[str, Any], dict[str, int]]:
    lower_source = lower(source, Variant(include_opaque=False))
    upper_source = lower(source, Variant(include_opaque=True))
    lower_cert, low_stats = extract(parse_program(lower_source["program"]))
    upper_cert, up_stats = extract(parse_program(upper_source["program"]))
    weights = [r["weight"] for r in upper_source["ir"]["rules"]]
    minimum, min_stats = minimum_cost(upper_source["program"], weights)
    lower_verdict = validate(lower_source["program"], lower_cert)
    upper_verdict = validate(upper_source["program"], upper_cert)
    weighted_verdict = validate_weighted(upper_source["program"], weights, minimum)
    if not lower_verdict.accepted:
        raise RuntimeError(f'producer emitted invalid lower certificate: {lower_verdict.reason}')
    if not upper_verdict.accepted:
        raise RuntimeError(f'producer emitted invalid upper certificate: {upper_verdict.reason}')
    if not weighted_verdict.accepted:
        raise RuntimeError(f'producer emitted invalid weighted certificate: {weighted_verdict.reason}')
    low_item = {**lower_source, "certificate": lower_cert}
    up_item = {**upper_source, "certificate": upper_cert, "minimum": minimum}
    classification, core_stats = classify(low_item, up_item, minimum)
    evidence = {
        "language": "bfil-evidence-1",
        "lower": low_item,
        "upper": up_item,
        "classification": classification,
    }
    verdict = validate_source_evidence(source, evidence)
    if not verdict.accepted:
        raise AssertionError((verdict, source))
    stats = {
        "lower_graph_operations": low_stats["graph_operations"],
        "upper_graph_operations": up_stats["graph_operations"],
        "weighted_rule_scans": min_stats["rule_scans"],
        "weighted_relaxations": min_stats["relaxations"],
        "core_closure_calls": core_stats["closure_calls"],
        "core_rule_scans": core_stats["rule_scans"],
        "checker_steps": verdict.steps,
        "lower_atoms": len(lower_source["program"]["atoms"]),
        "lower_rules": len(lower_source["program"]["rules"]),
        "upper_atoms": len(upper_source["program"]["atoms"]),
        "upper_rules": len(upper_source["program"]["rules"]),
    }
    return evidence, stats


def classify(lower_item: dict[str, Any], upper_item: dict[str, Any],
             minimum: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Classify queries and construct two complementary unresolved witnesses.

    ``minimum_opaque_uses`` is the exact minimum number of opaque-trigger
    occurrences in a derivation tree, certified by the weighted proof.
    ``inclusion_minimal_opaque_sites`` is a deterministic, inclusion-minimal
    set of distinct source statement identifiers: enabling exactly that set
    derives the query, while deleting any one retained site does not.  It is
    not claimed to have minimum cardinality.
    """
    low_names = {lower_item["program"]["atoms"][n["atom"]] for n in lower_item["certificate"]["nodes"]}
    up_names = {upper_item["program"]["atoms"][n["atom"]] for n in upper_item["certificate"]["nodes"]}
    distances = minimum["distances"]
    rows = []
    stats = {"closure_calls": 0, "rule_scans": 0}
    all_sites = sorted({r["source"] for r in upper_item["ir"]["rules"]
                        if r["certainty"] == "opaque-trigger"})
    for query in upper_item["ir"]["queries"]:
        qid = upper_item["program"]["atoms"].index(query)
        if query in low_names:
            status, cost, sites, core = "must", 0, [], []
        elif query not in up_names:
            status, cost, sites, core = "impossible", None, [], []
        else:
            status, cost = "unresolved", distances[qid]
            sites = _opaque_witness_sites(upper_item, minimum, qid)
            if cost != len(sites):
                raise AssertionError((query, cost, sites))
            core, core_stats = _inclusion_minimal_sites(upper_item, qid, all_sites)
            stats["closure_calls"] += core_stats["closure_calls"]
            stats["rule_scans"] += core_stats["rule_scans"]
        rows.append({"query": query, "status": status,
                     "minimum_opaque_uses": cost,
                     "witness_opaque_sites": sites,
                     "inclusion_minimal_opaque_sites": core})
    return rows, stats


def _closure_with_sites(item: dict[str, Any], enabled: set[str]) -> tuple[set[int], int]:
    program = item["program"]
    named = item["ir"]["rules"]
    reached = set(program["facts"])
    scans = 0
    changed = True
    while changed:
        changed = False
        for rid, rule in enumerate(program["rules"]):
            scans += 1
            meta = named[rid]
            if meta["certainty"] == "opaque-trigger" and meta["source"] not in enabled:
                continue
            if rule["head"] not in reached and all(x in reached for x in rule["body"]):
                reached.add(rule["head"])
                changed = True
    return reached, scans


def _inclusion_minimal_sites(item: dict[str, Any], query: int,
                             all_sites: list[str]) -> tuple[list[str], dict[str, int]]:
    keep = list(all_sites)
    calls = scans = 0
    reached, used = _closure_with_sites(item, set(keep))
    calls += 1; scans += used
    if query not in reached:
        raise AssertionError("upper query absent during core construction")
    for site in list(all_sites):
        trial = [x for x in keep if x != site]
        reached, used = _closure_with_sites(item, set(trial))
        calls += 1; scans += used
        if query in reached:
            keep = trial
    # Directly audit inclusion minimality rather than relying only on the
    # deletion-order argument.
    reached, used = _closure_with_sites(item, set(keep))
    calls += 1; scans += used
    if query not in reached:
        raise AssertionError("core does not activate query")
    for site in keep:
        reached, used = _closure_with_sites(item, set(keep) - {site})
        calls += 1; scans += used
        if query in reached:
            raise AssertionError("core is not inclusion-minimal")
    return keep, {"closure_calls": calls, "rule_scans": scans}


def _opaque_witness_sites(upper_item: dict[str, Any], minimum: dict[str, Any], query: int) -> list[str]:
    selected = {node["atom"]: node["rule"] for node in minimum["nodes"]}
    program = upper_item["program"]
    named = upper_item["ir"]["rules"]
    sites: list[str] = []
    pending = [query]
    while pending:
        atom = pending.pop()
        if minimum["distances"][atom] == 0:
            continue
        rid = selected[atom]
        if rid == -1:
            continue
        if named[rid]["weight"]:
            sites.extend([named[rid]["source"]] * named[rid]["weight"])
        # Reverse the push order to preserve the former preorder serialization.
        pending.extend(reversed(program["rules"][rid]["body"]))
    return sites
