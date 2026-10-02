"""Owned source/evidence fault injections for the 24-case negative suite."""
from __future__ import annotations
import copy
from typing import Any


def mutate(case: str, source: dict[str,Any], evidence: dict[str,Any]) -> tuple[dict[str,Any],dict[str,Any]]:
    s=copy.deepcopy(source);e=copy.deepcopy(evidence)
    service=next(c for c in s['classes'] if c['name'].endswith('_Service'))
    guards=[c for c in s['classes'] if c['name'].endswith('_GuardA')]
    api=next(m for m in service['methods'] if m['name']=='api')
    if case=='source-duplicate-statement':
        api['body'][1]['id']=api['body'][0]['id']
    elif case=='source-unknown-super':
        s['classes'][0]['super']='MissingClass'
    elif case=='source-inheritance-cycle':
        s['classes'][0]['super']=s['classes'][1]['name']
    elif case=='source-duplicate-class':
        s['classes'].append(copy.deepcopy(s['classes'][0]))
    elif case=='source-unknown-field-type':
        service['fields'][0]['type']='MissingClass'
    elif case=='source-override-signature':
        guards[0]['methods'][0]['returns']=guards[0]['name']
    elif case=='source-service-subtype':
        s['services'][0]['implementation_class']=s['classes'][0]['name']
    elif case=='source-entry-arity':
        s['entries'][0]['arg_classes']=[s['classes'][0]['name']]
    elif case=='source-unknown-permission':
        guards[0]['methods'][0]['body'][0]['permission']='PERM_UNKNOWN'
    elif case=='source-unknown-variable':
        next(x for x in api['body'] if x['op']=='invoke')['recv']='missing'
    elif case=='source-invalid-field':
        next(x for x in api['body'] if x['op']=='load')['field']='Missing.field'
    elif case=='source-unsupported-candidate':
        next(x for x in api['body'] if x['op']=='opaque')['candidates'][0]['op']='new'
    elif case=='evidence-schema':
        e.pop('classification')
    elif case=='lower-schema':
        e['lower'].pop('coverage')
    elif case=='upper-schema':
        e['upper'].pop('minimum')
    elif case=='lower-ir-omission':
        e['lower']['ir']['rules'].pop()
    elif case=='lower-program-query':
        e['lower']['program']['queries'].pop()
    elif case=='lower-coverage-count':
        e['lower']['coverage']['totals']['rules']+=1
    elif case=='lower-certificate-omission':
        e['lower']['certificate']['nodes'].pop()
    elif case=='lower-certificate-reason':
        node=next(n for n in e['lower']['certificate']['nodes'] if n['rule']>=0)
        node['rule']=0 if node['rule']!=0 else min(1,len(e['lower']['program']['rules'])-1)
    elif case=='upper-ir-origin':
        e['upper']['ir']['rules'][0]['origin']+=':mutated'
    elif case=='upper-program-fact':
        e['upper']['program']['facts'].pop()
    elif case=='upper-minimum-distance':
        q=e['upper']['program']['queries'][-1]
        old=e['upper']['minimum']['distances'][q]
        e['upper']['minimum']['distances'][q]=0 if old is None or old>0 else 1
    elif case=='classification-mutation':
        e['classification'][0]['status']='impossible'
    else:raise ValueError(case)
    return s,e

CASES=(
'source-duplicate-statement','source-unknown-super','source-inheritance-cycle','source-duplicate-class',
'source-unknown-field-type','source-override-signature','source-service-subtype','source-entry-arity',
'source-unknown-permission','source-unknown-variable','source-invalid-field','source-unsupported-candidate',
'evidence-schema','lower-schema','upper-schema','lower-ir-omission','lower-program-query','lower-coverage-count',
'lower-certificate-omission','lower-certificate-reason','upper-ir-origin','upper-program-fact',
'upper-minimum-distance','classification-mutation')
