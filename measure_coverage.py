"""Same-input coverage-ledger aggregation timings, separate from lowering."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

from pcpe.framework_cases import revision_pair
from pcpe.lowering import Variant, lower, make_coverage
from pcpe.source_model import parse_source


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise SystemExit('Output exists; use a distinct measurement directory.')
    test_path=Path(__file__).resolve().parent/'tests/test_coverage_counts.py'
    spec=importlib.util.spec_from_file_location('coverage_scan_baseline',test_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline=module.scan_coverage
    affinity=None
    if os.name=='nt':
        import ctypes
        handle=ctypes.windll.kernel32.GetCurrentProcess()
        original=ctypes.c_size_t()
        available=ctypes.c_size_t()
        if ctypes.windll.kernel32.GetProcessAffinityMask(handle,ctypes.byref(original),ctypes.byref(available)):
            selected=original.value & -original.value
            if ctypes.windll.kernel32.SetProcessAffinityMask(handle,ctypes.c_size_t(selected)):
                affinity=dict(original=original.value,selected=selected)
    records=[]
    for index in (0,49,99,199,299):
        _,_,document,_=revision_pair(index)
        source=parse_source(document)
        for opaque in (False,True):
            compiled=lower(document,Variant(include_opaque=opaque))
            facts,rules=compiled['ir']['facts'],compiled['ir']['rules']
            expected=compiled['coverage']
            for fn in (baseline,make_coverage):
                if fn(source,facts,rules)!=expected:
                    raise RuntimeError('Coverage disagreement before timing.')
                for _ in range(20):
                    fn(source,facts,rules)
            pairs=[]
            for pair in range(11):
                times={}
                order=(('scan',baseline),('indexed',make_coverage))
                if pair%2:
                    order=tuple(reversed(order))
                for name,fn in order:
                    started=time.perf_counter_ns()
                    for _ in range(64):
                        result=fn(source,facts,rules)
                    times[name]=(time.perf_counter_ns()-started)/64
                    if result!=expected:
                        raise RuntimeError('Coverage disagreement after timing.')
                pairs.append(dict(order=[name for name,_ in order],nanoseconds=times,
                                  scan_over_indexed=times['scan']/times['indexed']))
            records.append(dict(revision=index,include_opaque=opaque,
                statements=compiled['coverage']['totals']['statements'],
                entries=compiled['coverage']['totals']['entries'],facts=len(facts),rules=len(rules),
                pairs=pairs,median_ratio=statistics.median(row['scan_over_indexed'] for row in pairs)))
    if affinity is not None:
        ctypes.windll.kernel32.SetProcessAffinityMask(handle,ctypes.c_size_t(affinity['original']))
    summary=dict(scope='Coverage aggregation only, with parsed source and canonical facts/rules precomputed. No full-lowering or end-to-end campaign timing.',
        environment=dict(platform=platform.platform(),python=sys.version,processor=platform.processor(),affinity=affinity),
        protocol=dict(revisions=[0,49,99,199,299],endpoints=[False,True],warmup=20,pairs=11,iterations=64,workers=1),
        cases=records,ratio_range=[min(row['median_ratio'] for row in records),max(row['median_ratio'] for row in records)])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(cases=len(records),ratio_range=summary['ratio_range'],scope=summary['scope']),indent=2))


if __name__=='__main__':
    main()
