"""Consumer-side BFIL coverage and analysis-evidence checker.

The checker shares the strict AST parser/type model (part of the declared
trusted base) but does not import the untrusted lowering, producer, revision,
or weighted producer.  It independently rebuilds every expected ground fact
and rule from every source occurrence, compares the complete named inventory,
then delegates only the already-independent ground and weighted checks.

Declaration keys come from the parser's injective owner/member serialization.
Compact atom tokens are interpreted under the reconstructed endpoint catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .source_model import parse_source, resolve_method, possible_dispatch, is_subtype, Method, SourceProgram
from .checker import validate as validate_ground
from .weighted_checker import validate_weighted


@dataclass(frozen=True)
class SourceVerdict:
    accepted: bool
    reason: str
    steps: int


def _variant(raw: Any) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != {"context", "fields", "dispatch", "include_opaque"}:
        raise ValueError("variant-schema")
    if raw["context"] not in {"1call", "insensitive"}:
        raise ValueError("variant-context")
    if raw["fields"] not in {"sensitive", "insensitive"}:
        raise ValueError("variant-fields")
    if raw["dispatch"] not in {"points-to", "cha"}:
        raise ValueError("variant-dispatch")
    if type(raw["include_opaque"]) is not bool:
        raise ValueError("variant-opaque")
    return dict(raw)


class ReferenceBuilder:
    def __init__(self, source: SourceProgram, variant: dict[str, Any]):
        self.source = source
        self.variant = variant
        self.entries = tuple(sorted(e.name for e in source.entries))
        self.permissions = tuple(sorted(source.permissions))
        self.methods = tuple(sorted(source.method_map))
        self.fields = tuple(sorted(source.field_map))
        self.statements = tuple(sorted(s["id"] for m in source.method_map.values() for s in m.body))
        self.variables = {m.key: tuple(sorted(m.variables)) for m in source.method_map.values()}
        contexts = {f"root:{e}" for e in self.entries}
        if variant["context"] == "insensitive":
            self.contexts = ("*",)
        else:
            for method in source.method_map.values():
                for stmt in method.body:
                    if stmt["op"] in {"invoke", "direct"}:
                        contexts.add(f"site:{stmt['id']}")
                    if stmt["op"] == "opaque":
                        for i, candidate in enumerate(stmt["candidates"]):
                            if candidate["op"] in {"invoke", "direct"}:
                                contexts.add(f"site:{stmt['id']}#{i}")
            self.contexts = tuple(sorted(contexts))
        self.alloc_classes: dict[str, str] = {}
        for entry in source.entries:
            service = source.service_map[entry.service]
            self.alloc_classes[f"entry:{entry.name}:receiver"] = service.implementation_class
            for i, cls in enumerate(entry.arg_classes):
                self.alloc_classes[f"entry:{entry.name}:arg:{i}"] = cls
        for method in source.method_map.values():
            for stmt in method.body:
                if stmt["op"] == "new":
                    self.alloc_classes[f"new:{method.key}:{stmt['id']}"] = stmt["class"]
        self.allocs = tuple(sorted(self.alloc_classes))
        self.eid = {x: f"e{i}" for i, x in enumerate(self.entries)}
        self.pid = {x: f"p{i}" for i, x in enumerate(self.permissions)}
        self.mid = {x: f"m{i}" for i, x in enumerate(self.methods)}
        self.fid = {x: f"f{i}" for i, x in enumerate(self.fields)}
        self.cid = {x: f"c{i}" for i, x in enumerate(self.contexts)}
        self.oid = {x: f"o{i}" for i, x in enumerate(self.allocs)}
        self.sid = {x: f"s{i}" for i, x in enumerate(self.statements)}
        self.vid = {(m, v): f"v{i}" for m in self.methods for i, v in enumerate(self.variables[m])}
        self.facts: list[dict[str, Any]] = []
        self.rules: list[dict[str, Any]] = []
        self.queries: set[str] = set()
        self._atoms: set[str] = set()
        self._premises = 0

    def C(self, raw: str) -> str:
        return "*" if self.variant["context"] == "insensitive" else raw

    def R(self, e: str, c: str, m: str) -> str:
        return f"R:{self.eid[e]}:{self.cid[c]}:{self.mid[m]}"

    def V(self, e: str, c: str, m: str, v: str, o: str) -> str:
        return f"V:{self.eid[e]}:{self.cid[c]}:{self.mid[m]}:{self.vid[(m,v)]}:{self.oid[o]}"

    def H(self, e: str, b: str, f: str, v: str) -> str:
        token = self.fid[f] if self.variant["fields"] == "sensitive" else "fx"
        return f"H:{self.eid[e]}:{self.oid[b]}:{token}:{self.oid[v]}"

    def T(self, e: str, c: str, m: str, o: str) -> str:
        return f"T:{self.eid[e]}:{self.cid[c]}:{self.mid[m]}:{self.oid[o]}"

    def P(self, e: str, p: str) -> str:
        return f"P:{self.eid[e]}:{self.pid[p]}"

    def U(self, e: str, c: str, m: str, s: str) -> str:
        return f"U:{self.eid[e]}:{self.cid[c]}:{self.mid[m]}:{self.sid[s]}"

    def fact(self, atom: str, source: str, origin: str) -> None:
        self._admit_atoms((atom,))
        self.facts.append({"atom": atom, "source": source, "origin": origin})

    def _admit_atoms(self, atoms: Iterable[str]) -> None:
        fresh = set(atoms).difference(self._atoms)
        if len(self._atoms) + len(fresh) > 20_000 or any(len(x) > 160 for x in fresh):
            raise ValueError("ground-bound")
        self._atoms.update(fresh)

    def query(self, atom: str) -> None:
        self._admit_atoms((atom,))
        self.queries.add(atom)

    def rule(self, head: str, body: Iterable[str], source: str, origin: str,
             weight: int = 0, certainty: str = "definite") -> None:
        premises = sorted(set(body))
        if len(self.rules) == 40_000 or self._premises + len(premises) > 120_000:
            raise ValueError("ground-bound")
        self._admit_atoms([head, *premises])
        self._premises += len(premises)
        self.rules.append({"head": head, "body": premises, "source": source,
                           "origin": origin, "weight": weight, "certainty": certainty})


def reference_lower(source_document: Any, variant_document: Any) -> dict[str, Any]:
    source = parse_source(source_document)
    v = _variant(variant_document)
    b = ReferenceBuilder(source, v)
    _entries(b)
    for method in sorted(source.method_map.values(), key=lambda x: x.key):
        for entry in b.entries:
            for context in b.contexts:
                for stmt in method.body:
                    if stmt["op"] == "opaque":
                        if v["include_opaque"]:
                            _opaque(b, entry, context, method, stmt)
                    else:
                        _op(b, entry, context, method, stmt, stmt["id"], f"stmt:{stmt['id']}", (), "definite", None)
    return _finish(b)


def _entries(b: ReferenceBuilder) -> None:
    for entry in sorted(b.source.entries, key=lambda x: x.name):
        service = b.source.service_map[entry.service]
        root = b.C(f"root:{entry.name}")
        recv = f"entry:{entry.name}:receiver"
        targets = ((resolve_method(b.source, service.implementation_class, entry.selector),)
                   if b.variant["dispatch"] == "points-to"
                   else possible_dispatch(b.source, service.declared_class, entry.selector))
        for target in targets:
            if target is None:
                continue
            pre = f"entry:{entry.name}:target:{target.key}"
            src = f"entry:{entry.name}"
            b.fact(b.R(entry.name, root, target.key), src, pre + ":reach")
            b.fact(b.V(entry.name, root, target.key, "this", recv), src, pre + ":this")
            for i, param in enumerate(target.params):
                b.fact(b.V(entry.name, root, target.key, param.name, f"entry:{entry.name}:arg:{i}"),
                       src, pre + f":arg:{i}")
        for permission in b.source.permissions:
            b.query(b.P(entry.name, permission))


def _opaque(b: ReferenceBuilder, e: str, c: str, m: Method, stmt: dict[str, Any]) -> None:
    active = b.U(e, c, m.key, stmt["id"])
    b.rule(active, [b.R(e, c, m.key)], stmt["id"],
           f"stmt:{stmt['id']}:activate:{b.eid[e]}:{b.cid[c]}", 1, "opaque-trigger")
    for i, cand in enumerate(stmt["candidates"]):
        _op(b, e, c, m, cand, stmt["id"], f"stmt:{stmt['id']}:candidate:{i}",
            (active,), "opaque-effect", i)


def _op(b: ReferenceBuilder, e: str, c: str, m: Method, op: dict[str, Any], source_id: str,
        prefix: str, extra: tuple[str, ...], certainty: str, candidate_index: int | None) -> None:
    kind = op["op"]
    guard = extra if extra else (b.R(e, c, m.key),)
    suffix = f":{b.eid[e]}:{b.cid[c]}"
    if kind == "new":
        o = f"new:{m.key}:{op['id']}"
        b.rule(b.V(e, c, m.key, op["dst"], o), guard, source_id, prefix + suffix + ":new", 0, certainty)
    elif kind == "move":
        for o in b.allocs:
            b.rule(b.V(e, c, m.key, op["dst"], o), guard + (b.V(e,c,m.key,op["src"],o),),
                   source_id, prefix + suffix + f":move:{b.oid[o]}", 0, certainty)
    elif kind == "store":
        for x in b.allocs:
            for y in b.allocs:
                b.rule(b.H(e,x,op["field"],y), guard + (b.V(e,c,m.key,op["base"],x), b.V(e,c,m.key,op["src"],y)),
                       source_id, prefix + suffix + f":store:{b.oid[x]}:{b.oid[y]}", 0, certainty)
    elif kind == "load":
        for x in b.allocs:
            for y in b.allocs:
                b.rule(b.V(e,c,m.key,op["dst"],y), guard + (b.V(e,c,m.key,op["base"],x), b.H(e,x,op["field"],y)),
                       source_id, prefix + suffix + f":load:{b.oid[x]}:{b.oid[y]}", 0, certainty)
    elif kind == "check":
        b.rule(b.P(e,op["permission"]), guard, source_id, prefix + suffix + ":check", 0, certainty)
    elif kind == "return":
        if op["src"] is not None:
            for o in b.allocs:
                b.rule(b.T(e,c,m.key,o), guard + (b.V(e,c,m.key,op["src"],o),),
                       source_id, prefix + suffix + f":return:{b.oid[o]}", 0, certainty)
    elif kind == "direct":
        target = b.source.method_map[op["target"]]
        site = f"site:{source_id}" if candidate_index is None else f"site:{source_id}#{candidate_index}"
        _call(b,e,c,m,target,op,guard,source_id,prefix+suffix+":direct",b.C(site),certainty,"this",None)
    elif kind == "invoke":
        static = m.variables[op["recv"]]
        site = f"site:{source_id}" if candidate_index is None else f"site:{source_id}#{candidate_index}"
        cc = b.C(site)
        if b.variant["dispatch"] == "points-to":
            for o in b.allocs:
                cls = b.alloc_classes[o]
                if not is_subtype(b.source, cls, static):
                    continue
                target = resolve_method(b.source, cls, op["selector"])
                if target is None:
                    continue
                g = guard + (b.V(e,c,m.key,op["recv"],o),)
                _call(b,e,c,m,target,op,g,source_id,prefix+suffix+f":invoke:{b.oid[o]}:{b.mid[target.key]}",cc,certainty,op["recv"],o)
        else:
            for target in possible_dispatch(b.source, static, op["selector"]):
                _call(b,e,c,m,target,op,guard,source_id,prefix+suffix+f":cha:{b.mid[target.key]}",cc,certainty,op["recv"],"CHA")
    else:
        raise ValueError("checker-operation")


def _call(b: ReferenceBuilder, e: str, caller_c: str, caller: Method, target: Method,
          op: dict[str, Any], guard: tuple[str, ...], source_id: str, origin: str,
          callee_c: str, certainty: str, receiver_var: str, dynamic: str | None) -> None:
    b.rule(b.R(e,callee_c,target.key), guard, source_id, origin+":reach", 0, certainty)
    recv_allocs = (dynamic,) if dynamic not in (None,"CHA") else b.allocs
    for o in recv_allocs:
        if dynamic == "CHA" and not is_subtype(b.source,b.alloc_classes[o],caller.variables[receiver_var]):
            continue
        b.rule(b.V(e,callee_c,target.key,"this",o), guard + (b.V(e,caller_c,caller.key,receiver_var,o),),
               source_id,origin+f":this:{b.oid[o]}",0,certainty)
    for i,(arg,param) in enumerate(zip(op["args"],target.params)):
        for o in b.allocs:
            b.rule(b.V(e,callee_c,target.key,param.name,o), guard + (b.V(e,caller_c,caller.key,arg,o),),
                   source_id,origin+f":arg:{i}:{b.oid[o]}",0,certainty)
    if op["dst"] is not None:
        for o in b.allocs:
            b.rule(b.V(e,caller_c,caller.key,op["dst"],o), guard + (b.T(e,callee_c,target.key,o),),
                   source_id,origin+f":ret:{b.oid[o]}",0,certainty)


def _finish(b: ReferenceBuilder) -> dict[str, Any]:
    b.facts.sort(key=lambda x:(x["origin"],x["atom"]))
    b.rules.sort(key=lambda x:(x["origin"],x["head"],tuple(x["body"]),x["weight"],x["certainty"]))
    atoms=sorted({x["atom"] for x in b.facts}|b.queries|{r["head"] for r in b.rules}|{x for r in b.rules for x in r["body"]})
    if len(atoms)>20_000 or len(b.rules)>40_000 or sum(len(r["body"]) for r in b.rules)>120_000 or any(len(x)>160 for x in atoms):
        raise ValueError("ground-bound")
    ix={x:i for i,x in enumerate(atoms)}
    program={"atoms":atoms,"facts":[ix[x] for x in sorted({f["atom"] for f in b.facts})],
             "rules":[{"head":ix[r["head"]],"body":sorted(ix[x] for x in r["body"])} for r in b.rules],
             "queries":[ix[x] for x in sorted(b.queries)]}
    catalog={"entries":list(b.entries),"permissions":list(b.permissions),"methods":list(b.methods),
             "fields":list(b.fields),"contexts":list(b.contexts),"allocations":list(b.allocs),
             "allocation_classes":dict(sorted(b.alloc_classes.items())),
             "variables":{k:list(v) for k,v in sorted(b.variables.items())},"statements":list(b.statements)}
    ir={"language":"bfil-ir-1","variant":b.variant,"catalog":catalog,"atoms":atoms,
        "facts":b.facts,"rules":b.rules,"queries":sorted(b.queries)}
    obligations={}
    for r in b.rules:
        key=r["source"]
        if key not in obligations:
            obligations[key]=[0,0,0]
        obligations[key][0]+=1
        if r["certainty"]=="opaque-trigger":
            obligations[key][1]+=1
        elif r["certainty"]=="opaque-effect":
            obligations[key][2]+=1
    entry_facts={}
    for f in b.facts:
        key=f["source"]
        entry_facts[key]=entry_facts.get(key,0)+1
    rows=[]
    for m in sorted(b.source.method_map.values(),key=lambda x:x.key):
        for s in m.body:
            count,trigger,effect=obligations.get(s["id"],(0,0,0))
            rows.append({"id":s["id"],"method":m.key,"op":s["op"],"facts":0,"rules":count,
                         "opaque_triggers":trigger,"opaque_effects":effect})
    erows=[]
    for e in sorted(b.source.entries,key=lambda x:x.name):
        key=f"entry:{e.name}"
        erows.append({"id":key,"facts":entry_facts.get(key,0),
                      "rules":obligations.get(key,(0,0,0))[0]})
    coverage={"language":"bfil-coverage-1","entries":erows,"statements":rows,
              "totals":{"facts":len(b.facts),"rules":len(b.rules),"statements":len(rows),"entries":len(erows)}}
    return {"ir":ir,"program":program,"coverage":coverage}


def validate_source_evidence(source: Any, evidence: Any) -> SourceVerdict:
    """Check complete lower/upper source evidence.

    Expected evidence keys are ``lower`` and ``upper``; each contains ``ir``,
    ``program``, ``coverage``, and ``certificate``.  The upper entry additionally
    contains ``minimum``.  ``classification`` is compared with independently
    recomputed must/unresolved/impossible rows.
    """
    steps=0
    def bad(reason: str) -> SourceVerdict:
        return SourceVerdict(False,reason,steps)
    if type(evidence) is not dict or set(evidence)!={"language","lower","upper","classification"} or evidence.get("language")!="bfil-evidence-1":
        return bad("evidence-schema")
    try:
        expected_lower=reference_lower(source,{"context":"1call","fields":"sensitive","dispatch":"points-to","include_opaque":False})
        expected_upper=reference_lower(source,{"context":"1call","fields":"sensitive","dispatch":"points-to","include_opaque":True})
    except ValueError as exc:
        return bad("source-"+str(exc))
    for label,expected in (("lower",expected_lower),("upper",expected_upper)):
        item=evidence[label]
        required={"ir","program","coverage","certificate"}|({"minimum"} if label=="upper" else set())
        if type(item) is not dict or set(item)!=required:
            return bad(label+"-schema")
        steps+=1
        if item["ir"]!=expected["ir"]: return bad(label+"-ir-mismatch")
        if item["program"]!=expected["program"]: return bad(label+"-program-mismatch")
        if item["coverage"]!=expected["coverage"]: return bad(label+"-coverage-mismatch")
        verdict=validate_ground(item["program"],item["certificate"]);steps+=verdict.steps
        if not verdict.accepted:return bad(label+"-certificate-"+verdict.reason)
        if label=="upper":
            weights=[r["weight"] for r in item["ir"]["rules"]]
            wv=validate_weighted(item["program"],weights,item["minimum"]);steps+=wv.steps
            if not wv.accepted:return bad("upper-minimum-"+wv.reason)
    expected_classification=classify_from_certificates(evidence["lower"],evidence["upper"],evidence["upper"]["minimum"])
    if evidence["classification"]!=expected_classification:
        return bad("classification-mismatch")
    return SourceVerdict(True,"accepted",steps)


def classify_from_certificates(lower: dict[str,Any], upper: dict[str,Any],
                               minimum: dict[str,Any])->list[dict[str,Any]]:
    low_names={lower["program"]["atoms"][n["atom"]] for n in lower["certificate"]["nodes"]}
    up_names={upper["program"]["atoms"][n["atom"]] for n in upper["certificate"]["nodes"]}
    distances=minimum["distances"]
    chosen={n["atom"]:n["rule"] for n in minimum["nodes"]}
    all_sites=sorted({r["source"] for r in upper["ir"]["rules"]
                      if r["certainty"]=="opaque-trigger"})
    rows=[]
    def sites_for(atom:int)->list[str]:
        out=[]
        pending=[atom]
        while pending:
            a=pending.pop()
            # A founded zero-cost subtree has no positive-weight occurrences.
            if distances[a]==0:
                continue
            rid=chosen[a]
            if rid==-1:continue
            weight=upper["ir"]["rules"][rid]["weight"]
            if weight:
                out.extend([upper["ir"]["rules"][rid]["source"]]*weight)
            pending.extend(reversed(upper["program"]["rules"][rid]["body"]))
        return out
    for qname in upper["ir"]["queries"]:
        qi=upper["program"]["atoms"].index(qname)
        if qname in low_names:
            status="must";cost=0;sites=[];core=[]
        elif qname not in up_names:
            status="impossible";cost=None;sites=[];core=[]
        else:
            status="unresolved";cost=distances[qi];sites=sites_for(qi)
            if cost!=len(sites):
                raise ValueError("minimum-site-count")
            core=_reference_minimal_sites(upper,qi,all_sites)
        rows.append({"query":qname,"status":status,"minimum_opaque_uses":cost,
                     "witness_opaque_sites":sites,
                     "inclusion_minimal_opaque_sites":core})
    return rows


def _reference_closure(item:dict[str,Any],enabled:set[str])->set[int]:
    reached=set(item["program"]["facts"])
    changed=True
    while changed:
        changed=False
        for rid,rule in enumerate(item["program"]["rules"]):
            meta=item["ir"]["rules"][rid]
            if meta["certainty"]=="opaque-trigger" and meta["source"] not in enabled:
                continue
            if rule["head"] not in reached and all(x in reached for x in rule["body"]):
                reached.add(rule["head"]);changed=True
    return reached


def _reference_minimal_sites(item:dict[str,Any],query:int,all_sites:list[str])->list[str]:
    keep=list(all_sites)
    if query not in _reference_closure(item,set(keep)):
        raise ValueError("upper-query-absent")
    for site in list(all_sites):
        trial=[x for x in keep if x!=site]
        if query in _reference_closure(item,set(trial)):
            keep=trial
    if query not in _reference_closure(item,set(keep)):
        raise ValueError("core-not-activating")
    for site in keep:
        if query in _reference_closure(item,set(keep)-{site}):
            raise ValueError("core-not-minimal")
    return keep
