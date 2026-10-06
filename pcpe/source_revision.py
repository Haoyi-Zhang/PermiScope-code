"""Certificate transport across BFIL revisions by stable named identities.

Transport is conservative.  It reuses only facts and selected rules whose full
named records survive, then completes the new least model and submits the whole
result to the independent ground checker.  Source coverage for the new revision
is checked separately by ``source_checker``; reuse never bypasses that scan.
"""
from __future__ import annotations

from typing import Any

from .checker import validate
from .source_identity import SemanticCatalog


def transport_complete(old_item: dict[str,Any], new_compiled: dict[str,Any]) -> tuple[dict[str,Any],dict[str,Any]]:
    old_program=old_item["program"];old_ir=old_item["ir"];old_cert=old_item["certificate"]
    new_program=new_compiled["program"];new_ir=new_compiled["ir"]
    if not validate(old_program, old_cert).accepted:
        raise ValueError("invalid old certificate")
    old_semantics=SemanticCatalog(old_ir);new_semantics=SemanticCatalog(new_ir)
    old_names=old_program["atoms"]
    new_index={new_semantics.atom(x):i for i,x in enumerate(new_program["atoms"])}
    new_fact_records={new_semantics.fact(x) for x in new_ir["facts"]}
    old_fact_by_atom: dict[tuple[Any,...],set[tuple[Any,...]]] = {}
    for record in old_ir["facts"]:
        old_fact_by_atom.setdefault(old_semantics.atom(record["atom"]),set()).add(old_semantics.fact(record))
    new_rule_index={new_semantics.rule(r):i for i,r in enumerate(new_ir["rules"])}
    nodes=[];seen:set[int]=set();reused=0;skipped=0
    # New facts are foundations.  Preserve old fact nodes when their full record
    # survives; add genuinely new facts as nonreused foundations first.
    old_node_by_name={old_semantics.atom(old_names[n["atom"]]):n for n in old_cert["nodes"]}
    for atom in sorted(new_program["facts"]):
        name=new_semantics.atom(new_program["atoms"][atom])
        old_node=old_node_by_name.get(name)
        if (old_node is not None and old_node["rule"]==-1
                and old_fact_by_atom.get(name,set()) & new_fact_records):
            nodes.append({"atom":atom,"rule":-1});seen.add(atom);reused+=1
        else:
            nodes.append({"atom":atom,"rule":-1});seen.add(atom)
    # Reuse surviving nonfact selected witnesses in their old topological order.
    for old_node in old_cert["nodes"]:
        if old_node["rule"]==-1:continue
        name=old_semantics.atom(old_names[old_node["atom"]])
        if name not in new_index:skipped+=1;continue
        old_rule=old_ir["rules"][old_node["rule"]]
        rid=new_rule_index.get(old_semantics.rule(old_rule))
        if rid is None:skipped+=1;continue
        target=new_index[name]
        if target in seen:continue
        body=new_program["rules"][rid]["body"]
        if all(x in seen for x in body):
            nodes.append({"atom":target,"rule":rid});seen.add(target);reused+=1
        else:skipped+=1
    # Complete all consequences.  Repeated deterministic scans are adequate for
    # bounded cases and make the executed work explicit.
    scans=0;added=0;changed=True
    while changed:
        changed=False
        for rid,rule in enumerate(new_program["rules"]):
            scans+=1
            if rule["head"] not in seen and all(x in seen for x in rule["body"]):
                nodes.append({"atom":rule["head"],"rule":rid});seen.add(rule["head"])
                added+=1;changed=True
    cert={"nodes":nodes,"reported":sorted(set(new_program["queries"])&seen)}
    verdict=validate(new_program,cert)
    if not verdict.accepted:raise AssertionError(verdict)
    # The mapped old prefix AND every new fact, without rule completion.
    # This is not a claim that old nodes alone are already exact.
    prefix_count=len(nodes)-added
    prefix_nodes=nodes[:prefix_count]
    prefix_seen={x["atom"] for x in prefix_nodes}
    prefix={"nodes":prefix_nodes,"reported":sorted(set(new_program["queries"])&prefix_seen)}
    prefix_verdict=validate(new_program,prefix)
    stats={"reused_nodes":reused,"completed_nodes":added,"skipped_old_nodes":skipped,
           "new_certificate_nodes":len(nodes),"rule_scans":scans,
           "conservative_exact":prefix_verdict.accepted,
           "conservative_reason":prefix_verdict.reason,
           "checker_steps":verdict.steps}
    return cert,stats
