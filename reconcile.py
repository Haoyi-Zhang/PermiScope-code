#!/usr/bin/env python3
"""Reconcile a full prescribed run's raw row inventory and aggregate outcomes."""
from __future__ import annotations
import argparse,csv,itertools,json
from pathlib import Path

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def reconcile(root:Path)->dict:
    def read(name):return json.loads((root/name).read_text())
    def rows(name):
        with (root/name).open(newline='') as f:return list(csv.DictReader(f))
    chunks=read('run-all-summary.json')['chunks']
    names=['fixtures']+[f'exhaustive-atoms4-facts{x:02d}' for x in range(16)]+['revisions','optional','families']+[f'scale-{n}-{s}' for n in (128,1280,12800) for s in (0,1)]
    require([c['chunk'] for c in chunks]==names,'chunk inventory')
    require(all(c['errors']==0 and read(c['chunk']+'-summary.json')==c for c in chunks),'chunk summary mismatch')
    expected=['']+[str(i) for i in range(64)]+[';'.join(map(str,p)) for p in itertools.combinations(range(64),2)]
    for f in range(16):
        rr=rows(f'exhaustive-atoms4-facts{f:02d}.csv');require(len(rr)==2081,'exhaustive row count')
        require([r['rule_indices'] for r in rr]==expected,'exhaustive theory inventory')
        require(all(int(r['candidate_checks'])==16 and int(r['accepted_candidates'])==1 and int(r['errors'])==0 and 0<=int(r['least_model_mask'])<16 for r in rr), 'exhaustive candidate-check invariant')
    rr=rows('revision-pairs.csv');require(len(rr)==65016,'revision-pair row count')
    acc=sum(r['transport_accepted']=='True' for r in rr)
    equal=sum(r['old_least_model_mask']==r['new_least_model_mask'] for r in rr)
    weak=sum(r['witness_only_accepted']=='True' and r['old_least_model_mask']!=r['new_least_model_mask'] for r in rr)
    require(all(r['transport_accepted']!='True' or r['old_least_model_mask']==r['new_least_model_mask'] for r in rr), 'unsound accepted transport')
    require(all(int(r['errors'])==0 for r in rr),'revision-row error')
    rev=read('revisions-summary.json')
    require((acc,equal,equal-acc,weak)==(rev['accepted_transport'],rev['semantic_equality'],rev['equal_but_not_transported'],rev['witness_only_false_completeness']), 'revision summary mismatch')
    require((acc,equal,equal-acc,weak)==(50820,51498,678,9930),'unexpected finite revision counts')
    oo=rows('optional-queries.csv');require(len(oo)==24381,'optional-query row count')
    require(all(r['classification'] in ('present','absent','unresolved') and int(r['errors'])==0 for r in oo),'optional-query invariant')
    cores=[json.loads(r[k]) for r in oo for k in ('forward_core','reverse_core')]
    require(len(cores)==48762 and sum(c is not None for c in cores)==36048,'core inventory mismatch')
    ff=read('fixture-results.json');require(len(ff)==24 and all(r['passed'] and not r['accepted'] for r in ff),'fixture mismatch')
    require(sum(r['valid_control_accepted'] is True for r in ff)==23,'fixture control count')
    families=read('family-results.json');require(len(families)==6,'family count')
    require([r['minimal_activating_sets'] for r in families]==[2**k for k in range(1,7)],'family minimal-set counts')
    require(sum(r['assignments'] for r in families)==5460,'family assignment count')
    run=read('run-all-summary.json')
    return {'programs':33296,'candidate_checks':532736,'revision_pairs':65016,
            'accepted_transport':acc,'equal_but_not_transported':equal-acc,
            'witness_only_false_completeness':weak,'query_classifications':24381,
            'ordered_core_queries':48762,'negative_fixtures':24,'valid_controls':23,
            'graph_operations':sum(c.get('graph_operations',0) for c in chunks),
            'checker_steps':sum(c.get('checker_steps',0) for c in chunks),
            'cpu_seconds':run['this_process_cpu_seconds'],
            'wall_seconds_sum_of_chunks':sum(c['wall_seconds'] for c in chunks),
            'process_peak_rss_kib':run['process_peak_rss_kib'],'errors':0}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results',type=Path);a=p.parse_args()
    try:print(json.dumps(reconcile(a.results),indent=2,sort_keys=True))
    except (OSError,ValueError,RuntimeError,KeyError) as e:p.exit(1,str(e)+'\n')
