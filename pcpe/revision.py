"""Conservative transport of positive certificates across complete revisions.

This is witness transport plus a *full* closure recheck, not an incremental
speedup algorithm. It remaps surviving rules by complete structural equality.
Identifiers are array positions, never proof of semantic stability.
"""
from __future__ import annotations
from typing import Any
from .checker import validate, Verdict


def transport(old:dict[str,Any],new:dict[str,Any],cert:dict[str,Any]) -> tuple[dict[str,Any]|None,Verdict]:
    first=validate(old,cert)
    if not first.accepted:return None,Verdict(False,'old-certificate-invalid',first.steps)
    if type(new) is not dict or old['atoms']!=new.get('atoms'):
        return None,Verdict(False,'atom-identity-changed',first.steps)
    # The new program is parsed/checkable before rule signatures are indexed.
    schema_check=validate(new,{'nodes':[],'reported':[]})
    allowed={'accepted','missing-initial-fact','closure-violation'}
    count=first.steps+schema_check.steps
    if schema_check.reason not in allowed:return None,Verdict(False,schema_check.reason,count)
    index={ (r['head'],tuple(r['body'])):i for i,r in reversed(list(enumerate(new['rules']))) }
    nodes=[]
    for node in cert['nodes']:
        rid=node['rule'];a=node['atom']
        if rid==-1:
            if a not in new['facts']:return None,Verdict(False,'initial-fact-removed',count)
            nodes.append(dict(node))
        else:
            r=old['rules'][rid];key=(r['head'],tuple(r['body']))
            if key not in index:return None,Verdict(False,'selected-rule-removed',count)
            nodes.append({'atom':a,'rule':index[key]})
    atoms={x['atom'] for x in nodes}
    moved={'nodes':nodes,'reported':sorted(atoms.intersection(new['queries']))}
    verdict=validate(new,moved)
    return moved,Verdict(verdict.accepted,verdict.reason,count+verdict.steps)
