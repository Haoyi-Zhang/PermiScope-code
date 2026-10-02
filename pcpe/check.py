"""Read two bounded JSON files and perform the complete, never witness-only check."""
from __future__ import annotations
import argparse,json,stat,os
from pathlib import Path
from .checker import validate

def load(path:Path):
    def pairs(items):
        obj={}
        for k,v in items:
            if k in obj:raise ValueError('duplicate JSON key: '+k)
            obj[k]=v
        return obj
    limit=16*1024**2
    with path.open('rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('JSON input must be a regular file')
        raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('JSON input exceeds 16 MiB')
    def invalid(s):raise ValueError('non-finite JSON number: '+s)
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('program',type=Path);p.add_argument('certificate',type=Path);a=p.parse_args()
    try:v=validate(load(a.program),load(a.certificate))
    except (OSError,ValueError,RecursionError) as e:p.exit(2,str(e)+'\n')
    print(json.dumps({'accepted':v.accepted,'reason':v.reason,'steps':v.steps}))
    raise SystemExit(0 if v.accepted else 1)
if __name__=='__main__':main()
