#!/usr/bin/env python3
"""Compare two reviewed owned sources with their BFIL translations, offline.

Only inputs/source-semantics/old.py and new.py are executed. This experiment
does not execute public excerpts, accept an arbitrary executable input path,
or establish semantics preservation for Python/Java in general.
"""
from __future__ import annotations

import argparse
import builtins
import copy
import json
import sys
from pathlib import Path

from pcpe.checker import validate
from pcpe.evidence import build_evidence
from pcpe.lowering import Variant, lower
from pcpe.model import parse_program
from pcpe.owned_subset import translate_owned
from pcpe.producer import extract
from pcpe.source_oracle import opaque_sites, permission_oracle
from pcpe.source_revision import transport_complete

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "inputs/source-semantics"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def pairs(item, certificate):
    catalog = item["ir"]["catalog"]
    result = set()
    for node in certificate["nodes"]:
        parts = item["program"]["atoms"][node["atom"]].split(":")
        if parts[0] == "P":
            result.add((catalog["entries"][int(parts[1][1:])],
                        catalog["permissions"][int(parts[2][1:])]))
    return result


def concrete_owned(version, enabled):
    if version not in ("old", "new"):
        raise ValueError("only the two reviewed owned fixtures may be executed")
    path = FIXTURES / (version + ".py")
    text = path.read_text(encoding="utf-8")
    # This syntax check is not an execution sandbox. Execution authority comes
    # from the fixed owned path and human-readable reviewed fixture contents.
    source = translate_owned(text, path.name)
    require(set(enabled) <= set(opaque_sites(source)), "unknown owned choice")
    permissions = set()
    namespace = {"__name__": "owned_fixture",
        "__builtins__": {"__build_class__": builtins.__build_class__},
        "check": permissions.add,
        "enabled": lambda site: site in enabled}
    exec(compile(text, str(path), "exec"), namespace)
    trace = []
    heap = {}

    def profile(frame, event, arg):
        if event != "return" or frame.f_code.co_filename != str(path):
            return
        local = frame.f_locals
        if frame.f_code.co_name == "relay":
            trace.append(dict(caller_line=frame.f_back.f_lineno,
                              argument_class=type(local["value"]).__name__,
                              returned_same_object=arg is local["value"]))
        elif frame.f_code.co_name == "run":
            heap.update(alias_same_box=local["alias"] is local["box"],
                        selected_same_a=local["alias"].selected is local["a"],
                        other_same_b=local["box"].other is local["b"])

    previous = sys.getprofile()
    try:
        sys.setprofile(profile)
        namespace["Service"]().run()
    finally:
        sys.setprofile(previous)
    require(len(trace) == 2 and len({x["caller_line"] for x in trace}) == 2,
            "expected two distinct relay call sites")
    require({x["argument_class"] for x in trace} == {"GuardA", "GuardB"} and
            all(x["returned_same_object"] for x in trace), "relay alias semantics")
    require(len(heap) == 3 and all(heap.values()), "heap alias semantics")
    return {("API", p) for p in permissions}, dict(relay_calls=trace, heap_aliases=heap)


def compare():
    documents = {}
    evidence = {}
    rows = []
    ablations = []
    for version in ("old", "new"):
        path = FIXTURES / (version + ".py")
        source = translate_owned(path.read_text(encoding="utf-8"), path.name)
        documents[version] = source
        evidence[version], _ = build_evidence(source)
        sites = opaque_sites(source)
        require(len(sites) == 2, "fixed owned opaque inventory")
        upper = evidence[version]["upper"]
        for mask in range(1 << len(sites)):
            enabled = {sites[i] for i in range(len(sites)) if mask & (1 << i)}
            native, runtime = concrete_owned(version, enabled)
            direct, stats = permission_oracle(source, enabled)
            # Disabled active atoms have no foundation. Candidate rules remain
            # guarded and inert; this is the upper program restricted to V.
            program = copy.deepcopy(upper["program"])
            program["rules"] = [rule for rule, meta in zip(program["rules"], upper["ir"]["rules"])
                if meta["certainty"] != "opaque-trigger" or meta["source"] in enabled]
            certificate, _ = extract(parse_program(program))
            verdict = validate(program, certificate)
            completion_item = {"ir": upper["ir"], "program": program}
            horn = pairs(completion_item, certificate)
            require(verdict.accepted and native == direct == horn, "owned source semantic mismatch")
            expected = {("API", "P_A")}
            if version == "new":
                expected.add(("API", "P_B"))
            if len(enabled) == 2:
                expected.add(("API", "P_C"))
            require(native == expected, "owned control expectation")
            rows.append(dict(version=version, enabled_sites=sorted(enabled),
                native_permissions=sorted(native), direct_permissions=sorted(direct),
                horn_permissions=sorted(horn), ground_accepted=verdict.accepted,
                direct_reachable_contexts=stats["reachable_method_contexts"], **runtime))
        gold, _ = concrete_owned(version, set())
        for label, variant in (("full", Variant()),
                               ("field-insensitive", Variant(fields="insensitive")),
                               ("context-insensitive", Variant(context="insensitive"))):
            compiled = lower(source, variant)
            certificate, _ = extract(parse_program(compiled["program"]))
            require(validate(compiled["program"], certificate).accepted, "owned variant certificate")
            got = pairs(compiled, certificate)
            ablations.append(dict(version=version, variant=label, gold=sorted(gold),
                reported=sorted(got), false_positives=sorted(got - gold), false_negatives=sorted(gold - got)))
    old = evidence["old"]["lower"]
    new = {k: evidence["new"]["lower"][k] for k in ("ir", "program", "coverage")}
    moved, transport = transport_complete(old, new)
    require(pairs(new, moved) == concrete_owned("new", set())[0], "owned revised semantics")
    require(not transport["conservative_exact"] and transport["completed_nodes"] > 0,
            "owned revision must require new consequences")
    report = dict(scope="two owned annotated Python fixtures; permission projections only; not Android/Java",
        concrete_completions=len(rows), mismatches=0, completions=rows,
        lower_endpoint_ablations=ablations, changing_revision_transport=transport)
    return report, documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / "results") or (out.exists() and any(out.iterdir())):
        parser.error("use a fresh directory within this candidate's results")
    report, documents = compare()
    out.mkdir(parents=True, exist_ok=True)
    for name, doc in [("summary", report), *documents.items()]:
        with (out / (name + ".json")).open("x", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=2, sort_keys=True)
            handle.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
