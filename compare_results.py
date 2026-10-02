#!/usr/bin/env python3
"""Compare all semantic result content without hashes; ignore timing and RSS."""
import argparse,json
from pathlib import Path
TRANSIENT={'cpu_seconds','wall_seconds','process_peak_rss_kib','this_process_cpu_seconds'}
def normalized(x):
    if isinstance(x,dict):return {k:normalized(v) for k,v in x.items() if k not in TRANSIENT}
    if isinstance(x,list):return [normalized(v) for v in x]
    return x

def compare(a:Path,b:Path)->dict:
    aa={p.name for p in a.iterdir() if p.is_file() and p.suffix in ('.json','.csv')}
    bb={p.name for p in b.iterdir() if p.is_file() and p.suffix in ('.json','.csv')}
    if aa!=bb:raise ValueError(f'result inventory differs: {sorted(aa^bb)}')
    if not aa:raise ValueError('empty result inventory')
    for name in sorted(aa):
        left=(a/name).read_text();right=(b/name).read_text()
        equal=(normalized(json.loads(left))==normalized(json.loads(right))) if name.endswith('.json') else left==right
        if not equal:raise ValueError('semantic result differs: '+name)
    return {'files_compared':len(aa),'semantic_content_equal':True,'timing_and_rss_excluded':True,'errors':0}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('reference',type=Path);p.add_argument('replay',type=Path);a=p.parse_args()
    try:print(json.dumps(compare(a.reference,a.replay),sort_keys=True))
    except (OSError,ValueError) as e:p.exit(1,str(e)+'\n')
