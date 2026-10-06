#!/usr/bin/env python3
"""Run the 336-case BFIL framework campaign with one bounded worker."""
from __future__ import annotations
import argparse,csv,json,os,time
try:
    import resource
except ImportError:
    resource = None
from pathlib import Path
from typing import Any

from pcpe.framework_cases import (
    revision_pair, field_case, profile_for_seed, revision_signature, structural_signature,
)
from pcpe.source_model import parse_source
from pcpe.evidence import build_evidence
from pcpe.source_oracle import permission_oracle,opaque_sites
from pcpe.lowering import lower,Variant
from pcpe.model import parse_program
from pcpe.producer import extract
from pcpe.checker import validate
from pcpe.source_checker import validate_source_evidence
from pcpe.source_revision import transport_complete
from pcpe.public_slice import validate_public_slice
from pcpe.framework_faults import CASES,mutate

ROOT=Path(__file__).resolve().parent

def require(condition:bool,message:str)->None:
    if not condition:
        raise RuntimeError(message)

def bounded_runtime()->None:
    if hasattr(os,'sched_getaffinity'):
        allowed=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(allowed)})
    if resource is None:
        # Windows: the fixed case inventory and parser/ground bounds still
        # apply; POSIX process limits are unavailable and are not claimed.
        return
    memory=3*1024**3
    _,hard=resource.getrlimit(resource.RLIMIT_AS);memory=min(memory,hard) if hard>=0 else memory
    resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
    _,hard=resource.getrlimit(resource.RLIMIT_CPU);cap=min(1800,hard) if hard>=0 else 1800
    resource.setrlimit(resource.RLIMIT_CPU,(cap,cap))

def peak_rss_kib()->int:
    if resource is not None:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD),
                  ("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),
                  ("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),
                  ("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),
                  ("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t)]
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    psapi=ctypes.WinDLL("psapi",use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        raise OSError(ctypes.get_last_error(),"GetProcessMemoryInfo")
    return counters.PeakWorkingSetSize//1024

def write_json(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def pairs(compiled:dict[str,Any],cert:dict[str,Any])->set[tuple[str,str]]:
    names=compiled['program']['atoms'];cat=compiled['ir']['catalog']
    out=set()
    for node in cert['nodes']:
        name=names[node['atom']]
        if name.startswith('P:'):
            _,e,p=name.split(':');out.add((cat['entries'][int(e[1:])],cat['permissions'][int(p[1:])]))
    return out

def run_variant(source:dict[str,Any],variant:Variant)->tuple[set[tuple[str,str]],dict[str,int],dict[str,Any]]:
    compiled=lower(source,variant);cert,stats=extract(parse_program(compiled['program']))
    verdict=validate(compiled['program'],cert)
    require(verdict.accepted,f'variant certificate rejected: {verdict.reason}')
    return pairs(compiled,cert),{'graph_operations':stats['graph_operations'],'checker_steps':verdict.steps},compiled

def score(gold:set[tuple[str,str]],got:set[tuple[str,str]])->tuple[int,int,int]:
    return len(gold&got),len(got-gold),len(gold-got)

def completion_check(source:dict[str,Any])->dict[str,Any]:
    """Enumerate all independent opaque-site completions for a generated case."""
    sites=opaque_sites(source)
    if len(sites)>16:raise ValueError('completion enumeration bound')
    models=[];events=iterations=0
    for mask in range(1<<len(sites)):
        enabled={sites[i] for i in range(len(sites)) if mask&(1<<i)}
        permissions,stats=permission_oracle(source,enabled)
        models.append(permissions);events+=stats['events'];iterations+=stats['iterations']
    lower=models[0];upper=models[-1]
    intersection=set.intersection(*(set(x) for x in models)) if models else set()
    union=set.union(*(set(x) for x in models)) if models else set()
    envelope=all(lower<=x<=upper for x in models)
    exact=envelope and intersection==lower and union==upper
    return {'sites':sites,'models':len(models),'lower':lower,'upper':upper,'exact':exact,
            'events':events,'iterations':iterations}

def main()->None:
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    bounded_runtime();out=args.out.resolve()
    if out.exists() and any(out.iterdir()):ap.error('output directory must be empty')
    out.mkdir(parents=True,exist_ok=True)
    cpu0=time.process_time();wall0=time.monotonic()
    revision_rows=[];baseline_rows=[];structure_rows=[]
    totals={'graph_operations':0,'checker_steps':0,'weighted_rule_scans':0,'transport_rule_scans':0,
            'oracle_events':0,'oracle_iterations':0,'completion_oracle_events':0,'completion_oracle_iterations':0,
            'completion_models':0,'core_closure_calls':0,'core_rule_scans':0}
    maxima={'methods':0,'fields':0,'statements':0,'lower_atoms':0,'lower_rules':0,'upper_atoms':0,'upper_rules':0,
            'premise_incidences':0,'certificate_nodes':0}
    baseline_agg={x:{'tp':0,'fp':0,'fn':0,'exact':0} for x in ('full','field-insensitive','context-insensitive','cha')}
    unresolved=0;unresolved_costs=[];unresolved_core_sizes=[];preserving=changing=transport_exact=0
    transport_exact_preserving=transport_exact_changing=0;reuse_sum=cert_sum=0
    pair_signatures:set[str]=set();new_shapes:set[str]=set()
    endpoint_exact=0;max_opaque_sites=0;completion_models_total=0
    samples={0,1,100,101,200,201}
    for index in range(300):
        family,old,new,declared_preserving=revision_pair(index)
        profile=profile_for_seed(index%100)
        pair_sig=revision_signature(index);new_shape=structural_signature(new)
        require(pair_sig not in pair_signatures,f'duplicate identifier-erased revision pair: {index}')
        require(new_shape not in new_shapes,f'duplicate identifier-erased new program: {index}')
        pair_signatures.add(pair_sig);new_shapes.add(new_shape)
        structure_rows.append({'case':index,'family':family,**profile.document(),
                               'semantic_preserving':declared_preserving,
                               'old_shape':structural_signature(old),'new_shape':new_shape})
        old_e,old_stats=build_evidence(old);new_e,new_stats=build_evidence(new)
        old_gold,old_oracle=permission_oracle(old);new_gold,new_oracle=permission_oracle(new)
        completion=completion_check(new)
        full_new=pairs(new_e['lower'],new_e['lower']['certificate'])
        upper_new=pairs(new_e['upper'],new_e['upper']['certificate'])
        require(pairs(old_e['lower'],old_e['lower']['certificate'])==old_gold,
                f'old lowering/oracle disagreement: {index}')
        require(full_new==new_gold==completion['lower'],f'lower endpoint disagreement: {index}')
        require(upper_new==completion['upper'],f'upper endpoint disagreement: {index}')
        require(completion['exact'],f'completion envelope disagreement: {index}')
        endpoint_exact+=1;max_opaque_sites=max(max_opaque_sites,len(completion['sites']))
        completion_models_total+=completion['models']
        totals['completion_oracle_events']+=completion['events']
        totals['completion_oracle_iterations']+=completion['iterations']
        totals['completion_models']+=completion['models']
        actual_preserving=old_gold==new_gold
        require(actual_preserving==declared_preserving,f'revision label disagreement: {index}')
        preserving+=int(actual_preserving);changing+=int(not actual_preserving)
        new_compiled={k:new_e['lower'][k] for k in ('ir','program','coverage')}
        moved,ts=transport_complete(old_e['lower'],new_compiled)
        require(pairs(new_compiled,moved)==new_gold,f'transport completion disagreement: {index}')
        transport_exact+=int(ts['conservative_exact'])
        transport_exact_preserving+=int(actual_preserving and ts['conservative_exact'])
        transport_exact_changing+=int((not actual_preserving) and ts['conservative_exact'])
        reuse_sum+=ts['reused_nodes'];cert_sum+=ts['new_certificate_nodes']
        totals['transport_rule_scans']+=ts['rule_scans']
        variants={
          'full':full_new,
          'field-insensitive':run_variant(new,Variant(fields='insensitive'))[0],
          'context-insensitive':run_variant(new,Variant(context='insensitive'))[0],
          'cha':run_variant(new,Variant(dispatch='cha'))[0],
        }
        for name,got in variants.items():
            tp,fp,fn=score(new_gold,got);a=baseline_agg[name];a['tp']+=tp;a['fp']+=fp;a['fn']+=fn;a['exact']+=int(got==new_gold)
            baseline_rows.append({'case':index,'family':family,'baseline':name,'gold':';'.join(f'{a0}|{p0}' for a0,p0 in sorted(new_gold)),
                                  'reported':';'.join(f'{a0}|{p0}' for a0,p0 in sorted(got)),'tp':tp,'fp':fp,'fn':fn,'exact':got==new_gold})
        for row in new_e['classification']:
            if row['status']=='unresolved':
                unresolved+=1;unresolved_costs.append(row['minimum_opaque_uses']);unresolved_core_sizes.append(len(row['inclusion_minimal_opaque_sites']))
        p=parse_source(new)
        statement_count=sum(len(m.body) for m in p.method_map.values())
        premise_count=sum(len(r['body']) for r in new_e['upper']['program']['rules'])
        dimensions={'methods':len(p.method_map),'fields':len(p.field_map),'statements':statement_count,
                    'lower_atoms':new_stats['lower_atoms'],'lower_rules':new_stats['lower_rules'],
                    'upper_atoms':new_stats['upper_atoms'],'upper_rules':new_stats['upper_rules'],
                    'premise_incidences':premise_count,'certificate_nodes':len(new_e['upper']['certificate']['nodes'])}
        for k,v in dimensions.items():maxima[k]=max(maxima[k],v)
        for st in (old_stats,new_stats):
            totals['graph_operations']+=st['lower_graph_operations']+st['upper_graph_operations']
            totals['checker_steps']+=st['checker_steps'];totals['weighted_rule_scans']+=st['weighted_rule_scans'];totals['core_closure_calls']+=st['core_closure_calls'];totals['core_rule_scans']+=st['core_rule_scans']
        totals['oracle_events']+=old_oracle['events']+new_oracle['events'];totals['oracle_iterations']+=old_oracle['iterations']+new_oracle['iterations']
        revision_rows.append({'case':index,'family':family,'semantic_preserving':actual_preserving,
          'old_permissions':';'.join(f'{a}|{p}' for a,p in sorted(old_gold)),
          'new_permissions':';'.join(f'{a}|{p}' for a,p in sorted(new_gold)),
          'transport_exact_without_completion':ts['conservative_exact'],'reused_nodes':ts['reused_nodes'],
          'completed_nodes':ts['completed_nodes'],'new_certificate_nodes':ts['new_certificate_nodes'],
          'unresolved_queries':sum(x['status']=='unresolved' for x in new_e['classification']),
          'minimum_unresolved_cost':min((x['minimum_opaque_uses'] for x in new_e['classification'] if x['status']=='unresolved'),default=''),
          'minimum_unresolved_core_size':min((len(x['inclusion_minimal_opaque_sites']) for x in new_e['classification'] if x['status']=='unresolved'),default=''),
          'opaque_sites':len(completion['sites']),'completion_models':completion['models'],
          'endpoint_envelope_exact':completion['exact'],**profile.document(),
          'revision_form':('changing' if not actual_preserving else
                           ('reachable-refactoring' if ((index%100)//2)%3==0 else 'closure-neutral-addition')),
          **dimensions})
        if index in samples:
            write_json(out/f'sample-{index:03d}-source.json',new)
            write_json(out/f'sample-{index:03d}-evidence.json',new_e)
    # Public-source slices.
    public_rows=[]
    for path in sorted((ROOT/'inputs'/'public-slices').glob('*.json')):
        record=json.loads(path.read_text());sv=validate_public_slice(record)
        require(sv.accepted,f'public slice rejected: {path.name}: {sv.reason}')
        evidence,stats=build_evidence(record['source']);vv=validate_source_evidence(record['source'],evidence)
        require(vv.accepted,f'public source evidence rejected: {path.name}: {vv.reason}')
        must=[x for x in evidence['classification'] if x['status']=='must']
        require(len(must)==1,f'public slice must-query count: {path.name}')
        public_rows.append({'id':record['id'],'path':record['provenance']['path'],'start_line':record['provenance']['start_line'],
          'end_line':record['provenance']['end_line'],'permission':record['anchor']['permission'],'slice_anchor_accepted':sv.accepted,
          'lexical_projection_accepted':sv.accepted,'source_evidence_accepted':vv.accepted,'must_queries':len(must),
          'lower_rules':stats['lower_rules'],'checker_steps':stats['checker_steps']})
        totals['graph_operations']+=stats['lower_graph_operations']+stats['upper_graph_operations'];totals['checker_steps']+=stats['checker_steps'];totals['weighted_rule_scans']+=stats['weighted_rule_scans'];totals['core_closure_calls']+=stats['core_closure_calls'];totals['core_rule_scans']+=stats['core_rule_scans']
    require(len(public_rows)==12,'public slice inventory')
    # 24 frozen fault fixtures.
    base=field_case(0);base_e,_=build_evidence(base);fault_rows=[]
    specs=sorted((ROOT/'inputs'/'framework-faults').glob('fault-*.json'))
    require(len(specs)==24,'fault fixture inventory')
    for spec_path,mutation in zip(specs,CASES):
        spec=json.loads(spec_path.read_text())
        require(spec['mutation']==mutation,f'fault fixture order: {spec_path.name}')
        bad_s,bad_e=mutate(mutation,base,base_e);v=validate_source_evidence(bad_s,bad_e)
        passed=(not v.accepted and v.reason==spec['expected_reason'])
        require(passed,f"fault outcome mismatch: {spec['case']}: {v.reason}")
        fault_rows.append({'case':spec['case'],'mutation':mutation,'expected_reason':spec['expected_reason'],
                           'observed_reason':v.reason,'rejected':not v.accepted,'passed':passed})
        totals['checker_steps']+=v.steps
    require(len(pair_signatures)==300 and len(new_shapes)==300,'structural diversity inventory')
    write_csv(out/'generated-revisions.csv',revision_rows);write_csv(out/'baseline-results.csv',baseline_rows)
    write_csv(out/'structural-diversity.csv',structure_rows)
    write_csv(out/'public-slices.csv',public_rows);write_csv(out/'fault-fixtures.csv',fault_rows)
    cpu=time.process_time()-cpu0;wall=time.monotonic()-wall0
    for name,a in baseline_agg.items():
        denom_p=a['tp']+a['fp'];denom_r=a['tp']+a['fn']
        a['precision']=a['tp']/denom_p if denom_p else 1.0;a['recall']=a['tp']/denom_r if denom_r else 1.0
    summary={'cases':{'generated_revisions':300,'public_slices':12,'fault_fixtures':24,'total':336},
      'revisions':{'semantic_preserving':preserving,'semantic_changing':changing,
                   'conservative_transport_exact':transport_exact,
                   'conservative_transport_exact_preserving':transport_exact_preserving,
                   'conservative_transport_exact_changing':transport_exact_changing,
                   'completion_required':300-transport_exact,
                   'reused_nodes':reuse_sum,'certificate_nodes':cert_sum,
                   'mean_reused_fraction':reuse_sum/cert_sum if cert_sum else 0.0},
      'diversity':{'identifier_erased_revision_pairs':len(pair_signatures),
                   'identifier_erased_new_programs':len(new_shapes),
                   'profiles_per_family':100,
                   'profile_grid':{'alias_depth':[0,4],'width':[0,4],
                                   'structure_depth':[0,3],'opaque_depth':[0,3]}},
      'classification':{'unresolved_queries':unresolved,
                        'minimum_cost_histogram':{str(x):unresolved_costs.count(x) for x in sorted(set(unresolved_costs))},
                        'inclusion_minimal_core_size_histogram':{str(x):unresolved_core_sizes.count(x) for x in sorted(set(unresolved_core_sizes))},
                        'completion_models':completion_models_total,'endpoint_envelope_exact':endpoint_exact,
                        'max_opaque_sites':max_opaque_sites},
      'baselines':baseline_agg,'maxima':maxima,'counters':totals,
      'resources':{'cpu_seconds':cpu,'wall_seconds':wall,'process_peak_rss_kib':peak_rss_kib(),
                   'platform':os.name,'os_resource_limits':resource is not None,
                   'workers':1,'download_bytes_during_campaign':0},'errors':0}
    write_json(out/'summary.json',summary)
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
