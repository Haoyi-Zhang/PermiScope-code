#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from pcpe.framework_cases import field_case
from pcpe.evidence import build_evidence
from pcpe.framework_faults import CASES,mutate
from pcpe.source_checker import validate_source_evidence
root=Path(__file__).resolve().parent
out=root/'inputs'/'framework-faults';out.mkdir(parents=True,exist_ok=True)
source=field_case(0);evidence,_=build_evidence(source)
for i,case in enumerate(CASES,1):
    bad_s,bad_e=mutate(case,source,evidence);v=validate_source_evidence(bad_s,bad_e)
    if v.accepted:
        raise RuntimeError(f'fault mutation was accepted: {case}')
    record={'case':f'fault-{i:02d}','mutation':case,'expected_reason':v.reason}
    (out/f'fault-{i:02d}.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(len(CASES))
