#!/usr/bin/env python3
"""Reproduce bounded kernel evidence, one worker, no network or dependencies.

Every exhaustive partition is atomic and separately resumable. --resume only
trusts existing successful chunk summaries; it does not recheck saved raw rows;
for a scientific clean replay omit --resume and use a fresh output directory.
"""
from __future__ import annotations
import argparse,csv,itertools,json,os,resource,sys,tempfile,time
from pathlib import Path
from typing import Any,Callable
from pcpe.model import parse_program
from pcpe.producer import extract
from pcpe.checker import validate
from pcpe.oracle import exact_model
from pcpe.revision import transport
from pcpe.core import activation_core

ROOT=Path(__file__).resolve().parent

def require(condition: bool, message: object) -> None:
    """Enforce campaign invariants even when Python is run with ``-O``."""
    if not condition:
        raise RuntimeError(str(message))

def bounded_runtime() -> None:
    if hasattr(os,'sched_getaffinity'):
        allowed=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(allowed)})
    memory=2*1024**3
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    memory=min(memory,hard) if hard>=0 else memory
    resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
    soft,hard=resource.getrlimit(resource.RLIMIT_CPU)
    cap=min(600,hard) if hard>=0 else 600
    resource.setrlimit(resource.RLIMIT_CPU,(cap,cap))

def atom_subset(n:int,mask:int)->list[int]:return [i for i in range(n) if mask>>i&1]

def program(n:int,facts:list[int],rules:tuple[tuple[int,int],...])->dict[str,Any]:
    return {'atoms':['a'+str(i) for i in range(n)],'facts':facts,
            'rules':[{'head':h,'body':atom_subset(n,b)} for h,b in rules],
            'queries':list(range(n))}

def theories(n:int):
    pool=tuple((h,b) for h in range(n) for b in range(1<<n))
    yield (),()
    for k in (1,2):
        for ix in itertools.combinations(range(len(pool)),k):
            yield ix,tuple(pool[i] for i in ix)

def write_json(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');temp.replace(path)

def timed(fn:Callable[[],dict[str,Any]]) -> dict[str,Any]:
    cpu=time.process_time();wall=time.monotonic()
    x=fn();x['cpu_seconds']=time.process_time()-cpu;x['wall_seconds']=time.monotonic()-wall
    # Linux ru_maxrss is KiB; this is process high-water RSS after the chunk,
    # not a reset per-case peak and not an estimate of framework-tool memory.
    x['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return x

def fixtures(out:Path)->dict[str,Any]:
    rows=[];checker_steps=0;graph_ops=0;assignments=0
    for file in sorted((ROOT/'inputs').glob('case[0-9][0-9].json')):
        f=json.loads(file.read_text());d=f['program'];c=f['certificate'];v=validate(d,c)
        expected=f['expected'];ok=(v.accepted==expected['accepted'] and v.reason==expected['reason'])
        # A malformed program has no semantics; do not silently normalize it.
        try:
            p=parse_program(d)
        except ValueError:
            repaired_good=None;oracle_ok=None
        else:
            good,stat=extract(p);vg=validate(d,good);oracle,states=exact_model(d)
            assignments+=states;graph_ops+=stat['graph_operations'];checker_steps+=vg.steps
            repaired_good=vg.accepted
            oracle_ok=oracle==frozenset(x['atom'] for x in good['nodes'])
            ok=ok and repaired_good and oracle_ok
        checker_steps+=v.steps
        rows.append({'case':f['case'],'purpose':f['purpose'],'accepted':v.accepted,
                     'reason':v.reason,'expected_reason':expected['reason'],
                     'valid_control_accepted':repaired_good,'oracle_agreement':oracle_ok,'passed':ok})
    require(len(rows)==24 and all(x['passed'] for x in rows), rows)
    boundary=json.loads((ROOT/'inputs'/'trusted-boundary.json').read_text())
    inc=validate(boundary['omitted_model'],boundary['omitted_certificate'])
    full=validate(boundary['full_model'],boundary['omitted_certificate'])
    require(inc.accepted and not full.accepted, 'trusted-boundary control failed')
    write_json(out/'fixture-results.json',rows)
    write_json(out/'trusted-boundary.json',{'accepted_against_omitted_model':inc.accepted,
               'accepted_against_complete_model':full.accepted,'complete_model_reason':full.reason})
    return {'negative_fixtures':len(rows),'rejections':sum(not x['accepted'] for x in rows),
            'valid_controls':sum(x['valid_control_accepted'] is True for x in rows),
            'malformed_programs':sum(x['valid_control_accepted'] is None for x in rows),
            'oracle_assignments':assignments,'checker_steps':checker_steps+inc.steps+full.steps,
            'graph_operations':graph_ops,'errors':0}

def exhaustive_partition(out:Path,n:int,fmask:int)->dict[str,Any]:
    rows=[];assignments=0;checker_steps=0;graph_ops=0;checks=0
    for ix,rules in theories(n):
        d=program(n,atom_subset(n,fmask),rules)
        exact,states=exact_model(d);assignments+=states
        cert,stat=extract(parse_program(d));graph_ops+=stat['graph_operations']
        got=frozenset(x['atom'] for x in cert['nodes']);require(got==exact,(d,got,exact))
        accepted=0;errors=0
        for mask in range(1<<n):
            target=frozenset(atom_subset(n,mask))
            nodes=[dict(x) for x in cert['nodes'] if x['atom'] in target]
            # Every subset of the atom inventory is attempted. Unknown atoms
            # are deliberately offered as unjustified leaves, not ignored.
            nodes.extend({'atom':a,'rule':-1} for a in sorted(target-got))
            candidate={'nodes':nodes,'reported':sorted(target)}
            v=validate(d,candidate);checks+=1;checker_steps+=v.steps
            accepted+=int(v.accepted);errors+=int(v.accepted!=(target==exact))
        require(errors==0 and accepted==1,(d,errors,accepted))
        rows.append({'rule_indices':';'.join(map(str,ix)),
                     'least_model_mask':sum(1<<x for x in exact),'candidate_checks':1<<n,
                     'accepted_candidates':accepted,'errors':errors})
    p=out/f'exhaustive-atoms{n}-facts{fmask:02d}.csv';p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix('.csv.tmp')
    with t.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    t.replace(p)
    return {'atoms':n,'fact_mask':fmask,'programs':len(rows),'candidate_checks':checks,
            'oracle_assignments':assignments,'checker_steps':checker_steps,'graph_operations':graph_ops,'errors':0}

def revisions(out:Path)->dict[str,Any]:
    n=3;pool=tuple((h,b) for h in range(n) for b in range(1<<n))
    total=0;accepted=0;equal=0;miss=0;witness_accept_bad=0;oracle_states=0;ops=0;steps=0
    rows=[];pair_rows=[]
    for fmask in range(1<<n):
        counts={'fact_mask':fmask,'pairs':0,'accepted_transport':0,'semantic_equality':0,
                'equal_but_not_transported':0,'witness_only_false_completeness':0,'errors':0}
        for ix,rules in theories(n):
            old=program(n,atom_subset(n,fmask),rules);cert,stat=extract(parse_program(old));ops+=stat['graph_operations']
            old_atoms=frozenset(x['atom'] for x in cert['nodes'])
            variants=[]
            for bit in range(n):variants.append(('fact',bit,program(n,atom_subset(n,fmask^(1<<bit)),rules)))
            chosen=set(ix)
            for rid in range(len(pool)):
                newix=sorted(chosen^{rid});variants.append(('rule',rid,program(n,atom_subset(n,fmask),tuple(pool[j] for j in newix))))
            for kind,pos,new in variants:
                total+=1;counts['pairs']+=1
                oracle,states=exact_model(new);oracle_states+=states
                fresh,stat=extract(parse_program(new));ops+=stat['graph_operations']
                vf=validate(new,fresh);steps+=vf.steps
                require(vf.accepted and frozenset(x['atom'] for x in fresh['nodes'])==oracle,
                        ('fresh revision certificate mismatch', old, new))
                moved,v=transport(old,new,cert);steps+=v.steps
                weak_accepted=None
                same=(old_atoms==oracle);equal+=int(same);counts['semantic_equality']+=int(same)
                if v.accepted:
                    require(same, 'transport accepted a semantic change');accepted+=1;counts['accepted_transport']+=1
                elif same:
                    miss+=1;counts['equal_but_not_transported']+=1
                if moved is not None:
                    vw=validate(new,moved,closure=False);steps+=vw.steps;weak_accepted=vw.accepted
                    if vw.accepted and not same:
                        witness_accept_bad+=1;counts['witness_only_false_completeness']+=1
                pair_rows.append({'initial_fact_mask':fmask,'old_rule_indices':';'.join(map(str,ix)),
                    'edit_kind':kind,'edit_index':pos,'old_least_model_mask':sum(1<<a for a in old_atoms),
                    'new_least_model_mask':sum(1<<a for a in oracle),'transport_accepted':v.accepted,
                    'transport_reason':v.reason,'witness_only_accepted':weak_accepted,'errors':0})
        rows.append(counts)
    with (out/'revision-pairs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(pair_rows[0]));w.writeheader();w.writerows(pair_rows)
    write_json(out/'revision-results.json',rows)
    return {'revision_pairs':total,'accepted_transport':accepted,'semantic_equality':equal,
            'equal_but_not_transported':miss,'witness_only_false_completeness':witness_accept_bad,
            'oracle_assignments':oracle_states,'graph_operations':ops,
            'checker_steps':steps,'errors':0}

def optional_facts(out:Path)->dict[str,Any]:
    n=3;programs=0;queries=0;completions=0;oracle_assignments=0;core_queries=0;core_sat=0;extraction_calls=0
    extra_assignments=0;counts={'graph_operations':0};query_rows=[]
    for ix,rs in theories(n):
        # 0=absent, 1=known true, 2=optional. This is all disjoint B,U pairs.
        for status in itertools.product(range(3),repeat=n):
            facts=[i for i,s in enumerate(status) if s==1];optional=[i for i,s in enumerate(status) if s==2]
            d=program(n,facts,rs);programs+=1
            models=[]
            for mask in range(1<<len(optional)):
                dd=dict(d);dd['facts']=sorted(facts+[optional[j] for j in range(len(optional)) if mask>>j&1])
                truth,states=exact_model(dd);models.append(truth);completions+=1;oracle_assignments+=states
            lower=models[0];upper=models[-1]
            intersection=set.intersection(*(set(x) for x in models));union=set.union(*(set(x) for x in models))
            require(intersection==set(lower) and union==set(upper),
                    'endpoint/intersection-union mismatch')
            for q in range(n):
                queries+=1
                category='present' if q in lower else 'absent' if q not in upper else 'unresolved'
                values={q in x for x in models}
                require((category=='unresolved')==(len(values)>1),
                        'classification/completion mismatch')
                cores=[]
                for order in (optional,list(reversed(optional))):
                    core,calls=activation_core(d,optional,q,order,counters=counts);cores.append(core);extraction_calls+=calls;core_queries+=1
                    if core is None:
                        require(q not in upper, 'core search missed an upper-reachable query')
                        continue
                    core_sat+=1
                    dd=dict(d);dd['facts']=sorted(facts+core);model,states=exact_model(dd);extra_assignments+=states
                    require(q in model, 'reported activation core does not activate query')
                    for size in range(len(core)):
                        for subset in itertools.combinations(core,size):
                            dd=dict(d);dd['facts']=sorted(facts+list(subset));model,states=exact_model(dd);extra_assignments+=states
                            require(q not in model, 'activation core is not subset-minimal')
                query_rows.append({'rule_indices':';'.join(map(str,ix)),'initial_fact_mask':sum(1<<a for a in facts),
                    'optional_mask':sum(1<<a for a in optional),'query':q,'classification':category,
                    'forward_core':json.dumps(cores[0]),'reverse_core':json.dumps(cores[1]),'errors':0})
    with (out/'optional-queries.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(query_rows[0]));w.writeheader();w.writerows(query_rows)
    examples=[]
    for x in json.loads((ROOT/'inputs'/'activation-examples.json').read_text()):
        result=[]
        for order in (x['optional'],list(reversed(x['optional']))):
            core,calls=activation_core(x['program'],x['optional'],x['query'],order,counters=counts)
            result.append({'deletion_order':order,'core':core,'extractor_calls':calls})
        examples.append({'case':x['case'],'results':result})
    write_json(out/'activation-examples.json',examples)
    return {'partial_programs':programs,'query_classifications':queries,'completion_models':completions,
            'completion_oracle_assignments':oracle_assignments,'minimality_oracle_assignments':extra_assignments,
            'graph_operations':counts['graph_operations'],'ordered_core_queries':core_queries,
            'activating_cores':core_sat,'extractor_calls_in_core_search':extraction_calls,'errors':0}

def family_program(k:int)->tuple[dict[str,Any],list[int],int]:
    # Optional atoms u_i,v_i; clause c_i iff either option is enabled;
    # a prefix conjunction enforces all k independent choices. Body width <=2.
    atoms=[name+str(i) for i in range(k) for name in ('u','v')]
    atoms += ['c'+str(i) for i in range(k)]+['s'+str(i) for i in range(k+1)]
    rules=[]
    for i in range(k):
        c=2*k+i;s=3*k+i
        rules.extend([{'head':c,'body':[2*i]}, {'head':c,'body':[2*i+1]},
                      {'head':s+1,'body':[c,s]}])
    q=4*k
    return {'atoms':atoms,'facts':[3*k],'rules':rules,'queries':[q]},list(range(2*k)),q

def families(out:Path)->dict[str,Any]:
    rows=[];ops=0;checks=0;queries=0
    for k in range(1,7):
        d,optional,q=family_program(k);holds=[]
        for mask in range(1<<len(optional)):
            dd=dict(d);dd['facts']=sorted(d['facts']+atom_subset(2*k,mask))
            cert,stat=extract(parse_program(dd));v=validate(dd,cert)
            ops+=stat['graph_operations'];checks+=v.steps;queries+=1
            require(v.accepted, 'family certificate rejected')
            got=q in cert['reported'];expected=all(mask & (3<<(2*i)) for i in range(k))
            require(got==expected, ('family oracle mismatch', k, mask, got, expected))
            holds.append(got)
        minimal=[m for m,val in enumerate(holds) if val and
                 all(not holds[m^(1<<i)] for i in range(2*k) if m>>i&1)]
        require(len(minimal)==2**k, ('unexpected number of minimal sets', k, len(minimal)))
        rows.append({'k':k,'atoms':len(d['atoms']),'rules':len(d['rules']),
                     'assignments':len(holds),'minimal_activating_sets':len(minimal),
                     'minimal_masks':minimal,'errors':0})
        write_json(out/f'family-{k}-input.json',d)
    # An exactly-one choice makes the all-options endpoint inadmissible.
    d={'atoms':['u','v','q'],'facts':[],
       'rules':[{'head':2,'body':[0,1]}],'queries':[2]}
    admissible=[];oracle_states=0
    for facts in ([0],[1]):
        dd=dict(d);dd['facts']=facts;truth,states=exact_model(dd);oracle_states+=states
        admissible.append(2 in truth)
    dd=dict(d);dd['facts']=[0,1];truth,states=exact_model(dd);oracle_states+=states
    require(not any(admissible) and 2 in truth, 'correlated-completion counterexample failed')
    write_json(out/'correlated-completion.json',{'program':d,'admissible_fact_sets':[[0],[1]],
          'admissible_query_values':admissible,'all_options_query_value':2 in truth,
          'interpretation':'The all-options endpoint is not an admissible completion.'})
    write_json(out/'family-results.json',rows)
    return {'families':len(rows),'optional_assignments':queries,
            'minimal_sets':sum(x['minimal_activating_sets'] for x in rows),
            'correlation_counterexamples':1,'oracle_assignments':oracle_states,
            'graph_operations':ops,'checker_steps':checks,'errors':0}

def scale(out:Path,n:int,edges:int,seeded:bool)->dict[str,Any]:
    if edges<n-1:raise ValueError('edge budget cannot cover a chain')
    rules=[(i,(i-1,)) for i in range(1,n)];remaining=edges-(n-1);i=0
    while remaining:
        a=(37*i+5)%n;b=(a+1+(i%7))%n
        if a==b:b=(a+1)%n
        body=tuple(sorted((a,b))) if remaining>=2 else (a,)
        rules.append(((97*i+3)%n,body));remaining-=len(body);i+=1
    d={'atoms':['dependency'+str(i) for i in range(n)],'facts':[0] if seeded else [],
       'rules':[{'head':h,'body':list(b)} for h,b in rules],
       'queries':list(range(0,n,32))}
    cert,stat=extract(parse_program(d));v=validate(d,cert)
    require(v.accepted and len(cert['nodes'])==(n if seeded else 0),
            ('scale certificate mismatch', n, seeded, v.reason, len(cert['nodes'])))
    stem=f'scale-{n}-{int(seeded)}'
    write_json(out/(stem+'-certificate.json'),cert)
    write_json(out/(stem+'-input.json'),d)
    return {'atoms':n,'rules':len(rules),'premise_incidences':edges,
            'max_rule_body':max(len(b) for _,b in rules),'queries':len(d['queries']),
            'initial_facts':len(d['facts']),'proof_nodes':len(cert['nodes']),
            'encoded_input_bytes':len(json.dumps(d,separators=(',',':')).encode()),
            'encoded_certificate_bytes':len(json.dumps(cert,separators=(',',':')).encode()),
            'graph_operations':stat['graph_operations'],'checker_steps':v.steps,'errors':0}

def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--part',choices=['all','fixtures','exhaustive','revisions','optional','families','scale'],default='all')
    parser.add_argument('--atoms',type=int,choices=[3,4],default=4)
    parser.add_argument('--fact-mask',type=int)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();bounded_runtime()
    out=args.out.resolve()
    # Do not silently overwrite the checked-in evidence on the default path.
    if out==ROOT or out in ROOT.parents or out.is_relative_to(ROOT/'results'):
        parser.error('use a fresh output directory, not the checked-in observed evidence')
    if out.exists() and any(out.iterdir()) and not args.resume:
        parser.error('output directory is not empty; use a new directory or --resume')
    out.mkdir(parents=True,exist_ok=True)
    if args.fact_mask is not None and not 0<=args.fact_mask<(1<<args.atoms):parser.error('fact mask out of range')
    records=[];start=time.process_time()
    def chunk(name:str,fn:Callable[[],dict[str,Any]])->None:
        path=out/(name+'-summary.json')
        if path.exists():
            if not args.resume:raise FileExistsError(f'output already exists: {path}; use a fresh directory or --resume')
            old=json.loads(path.read_text())
            if old.get('errors')!=0 or old.get('chunk')!=name:raise ValueError('invalid saved chunk')
            # Resumption never purports to be an independent reproduction.
            records.append({'chunk':name,'reused_saved_chunk':True});print(name,'resumed',flush=True);return
        result=timed(fn);result['chunk']=name;write_json(path,result);records.append(result)
        print(name,json.dumps(result,sort_keys=True),flush=True)
    if args.part in ('all','fixtures'):chunk('fixtures',lambda:fixtures(out))
    if args.part in ('all','exhaustive'):
        masks=[args.fact_mask] if args.fact_mask is not None else range(1<<args.atoms)
        for f in masks:chunk(f'exhaustive-atoms{args.atoms}-facts{f:02d}',lambda f=f:exhaustive_partition(out,args.atoms,f))
    if args.part in ('all','revisions'):chunk('revisions',lambda:revisions(out))
    if args.part in ('all','optional'):chunk('optional',lambda:optional_facts(out))
    if args.part in ('all','families'):chunk('families',lambda:families(out))
    if args.part in ('all','scale'):
        for n,edges in [(128,400),(1280,4000),(12800,40000)]:
            for seeded in (False,True):
                chunk(f'scale-{n}-{int(seeded)}',lambda n=n,edges=edges,seeded=seeded:scale(out,n,edges,seeded))
    write_json(out/(f'run-{args.part}-summary.json'),{'part':args.part,'chunks':records,
               'this_process_cpu_seconds':time.process_time()-start,
               'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'workers':1,'network_used':False,'errors':0})
if __name__=='__main__':main()
