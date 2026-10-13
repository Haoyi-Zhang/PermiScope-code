#!/usr/bin/env python3
"""Offline receiver-dispatch comparison on two fixed, reviewed owned sources.

Executes only inputs/receiver-semantics/{old,new}.py with recording stubs.
This is neither an execution sandbox nor a general Python translation theorem.
"""
from __future__ import annotations

import argparse
import builtins
import copy
import json
import platform
import sys
from pathlib import Path

from pcpe.checker import validate
from pcpe.evidence import build_evidence
from pcpe.lowering import Variant, lower
from pcpe.model import parse_program
from pcpe.owned_subset import translate_owned
from pcpe.producer import extract
from pcpe.source_checker import validate_source_evidence
from pcpe.source_oracle import opaque_sites, permission_oracle
from pcpe.source_revision import transport_complete

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / 'inputs/receiver-semantics'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def pairs(item, certificate):
    catalog = item['ir']['catalog']
    out = set()
    for node in certificate['nodes']:
        parts = item['program']['atoms'][node['atom']].split(':')
        if parts[0] == 'P':
            out.add((catalog['entries'][int(parts[1][1:])],
                     catalog['permissions'][int(parts[2][1:])]))
    return out


def concrete_owned(version, enabled):
    if version not in ('old', 'new'):
        raise ValueError('only fixed owned receiver fixtures may be executed')
    path = FIXTURES / (version + '.py')
    text = path.read_text(encoding='utf-8')
    document = translate_owned(text, path.name)
    require(set(enabled) <= set(opaque_sites(document)), 'unknown owned choice')
    recorded = set()
    namespace = {'__name__': 'owned_receiver_fixture',
                 '__builtins__': {'__build_class__': builtins.__build_class__},
                 'check': recorded.add, 'enabled': lambda site: site in enabled}
    exec(compile(text, str(path), 'exec'), namespace)
    relay = []
    dispatch = []
    heap = {}

    def profile(frame, event, returned):
        if event != 'return' or frame.f_code.co_filename != str(path):
            return
        local = frame.f_locals
        name = frame.f_code.co_name
        if name == 'relay':
            relay.append(dict(caller_line=frame.f_back.f_lineno,
                              argument_class=type(local['value']).__name__,
                              returned_same_object=returned is local['value']))
        elif name in ('permission', 'extra'):
            dispatch.append(dict(method=frame.f_code.co_qualname,
                                 receiver_class=type(local['self']).__name__))
        elif name == 'run':
            heap.update(alias_same_box=local['alias'] is local['box'],
                        selected_same_a=local['alias'].selected is local['a'],
                        other_same_b=local['box'].other is local['b'])

    previous = sys.getprofile()
    try:
        sys.setprofile(profile)
        namespace['Service']().run()
    finally:
        sys.setprofile(previous)
    require(len(relay) == 2 and len({r['caller_line'] for r in relay}) == 2,
            'two distinct relay call sites')
    require({r['argument_class'] for r in relay} == {'GuardA', 'GuardB'} and
            all(r['returned_same_object'] for r in relay), 'return alias identity')
    require(len(heap) == 3 and all(heap.values()), 'heap alias identity')
    require(all(r['receiver_class'] == 'GuardA' for r in dispatch), 'selected receiver identity')
    return {('API', p) for p in recorded}, dict(relay_calls=relay,
                                               receiver_dispatch=dispatch, heap_aliases=heap)


def completion_pairs(upper, enabled):
    program = copy.deepcopy(upper['program'])
    program['rules'] = [rule for rule, meta in zip(program['rules'], upper['ir']['rules'])
                        if meta['certainty'] != 'opaque-trigger' or meta['source'] in enabled]
    certificate, _ = extract(parse_program(program))
    verdict = validate(program, certificate)
    require(verdict.accepted, 'completion certificate rejected')
    return pairs(dict(ir=upper['ir'], program=program), certificate)


def static_self_control(source):
    """Reinstate the former static-self mistake at the two inherited calls."""
    wrong = copy.deepcopy(source)
    guard = next(c for c in wrong['classes'] if c['name'] == 'Guard')
    enforce = next(m for m in guard['methods'] if m['name'] == 'enforce')
    for statement in enforce['body']:
        for operation in [statement, *statement.get('candidates', [])]:
            if operation['op'] == 'invoke' and operation['recv'] == 'this':
                selector = operation.pop('selector')
                operation.pop('recv')
                operation.update(op='direct', target=dict(owner='Guard', member=selector))
    return wrong


def compare():
    documents = {}
    evidence = {}
    rows = []
    controls = []
    ablations = []
    for version in ('old', 'new'):
        path = FIXTURES / (version + '.py')
        source = translate_owned(path.read_text(encoding='utf-8'), path.name)
        documents[version] = source
        current, _ = build_evidence(source)
        evidence[version] = current
        require(validate_source_evidence(source, current).accepted, 'source evidence rejected')
        wrong = static_self_control(source)
        wrong_e, _ = build_evidence(wrong)
        cross = validate_source_evidence(source, wrong_e)
        controls.append(dict(version=version, self_consistent_wrong_source_accepted=True,
                             correct_source_accepts_wrong_evidence=cross.accepted,
                             correct_source_rejection=cross.reason))
        sites = opaque_sites(source)
        require(sites == (('dispatch.outer',) if version == 'old'
                          else ('dispatch.inner', 'dispatch.outer')), 'fixed choice inventory')
        for mask in range(1 << len(sites)):
            enabled = {sites[i] for i in range(len(sites)) if mask & (1 << i)}
            native, runtime = concrete_owned(version, enabled)
            direct, _ = permission_oracle(source, enabled)
            horn = completion_pairs(current['upper'], enabled)
            legacy = completion_pairs(wrong_e['upper'], enabled)
            expected = {('API', 'P_A')}
            needed = {'dispatch.outer'} if version == 'old' else set(sites)
            if needed <= enabled:
                expected.add(('API', 'P_C'))
            require(native == expected, 'concrete receiver expectation')
            rows.append(dict(version=version, enabled_sites=sorted(enabled),
                             native_permissions=sorted(native), direct_permissions=sorted(direct),
                             horn_permissions=sorted(horn), agreement=native == direct == horn,
                             static_self_permissions=sorted(legacy),
                             static_self_agreement=legacy == native, **runtime))
        gold, _ = concrete_owned(version, set())
        for name, variant in [('full', Variant()), ('field-insensitive', Variant(fields='insensitive')),
                              ('context-insensitive', Variant(context='insensitive'))]:
            item = lower(source, variant)
            certificate, _ = extract(parse_program(item['program']))
            require(validate(item['program'], certificate).accepted, 'variant certificate')
            reported = pairs(item, certificate)
            ablations.append(dict(version=version, variant=name, gold=sorted(gold),
                                  reported=sorted(reported), false_positives=sorted(reported - gold),
                                  false_negatives=sorted(gold - reported)))
    transports = {}
    for endpoint in ('lower', 'upper'):
        target = {k: evidence['new'][endpoint][k] for k in ('ir', 'program', 'coverage')}
        moved, stats = transport_complete(evidence['old'][endpoint], target)
        revised = copy.deepcopy(evidence['new'])
        revised[endpoint]['certificate'] = moved
        verdict = validate_source_evidence(documents['new'], revised)
        require(verdict.accepted, 'full revised source evidence rejected')
        require(pairs(target, moved) == pairs(evidence['new'][endpoint], evidence['new'][endpoint]['certificate']),
                'transport permission projection')
        transports[endpoint] = dict(**stats, revised_source_accepted=verdict.accepted)
    explanations = {}
    for version, item in evidence.items():
        q = 'P:e0:p' + str(item['upper']['ir']['catalog']['permissions'].index('P_C'))
        explanations[version] = next(row for row in item['classification'] if row['query'] == q)
    report = dict(scope='two fixed owned receiver-dispatch sources; permission projections, not a Python theorem',
                  environment=dict(python=sys.version, implementation=platform.python_implementation(),
                                   system=platform.platform(), machine=platform.machine(),
                                   processor_identifier=platform.processor()),
                  concrete_completions=len(rows), mismatches=sum(not r['agreement'] for r in rows),
                  static_self_mismatches=sum(not r['static_self_agreement'] for r in rows),
                  completions=rows, negative_controls=controls, lower_endpoint_ablations=ablations,
                  opaque_explanations=explanations, endpoint_transports=transports)
    return report, documents, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        parser.error('use a new output directory')
    report, documents, evidence = compare()
    out.mkdir(parents=True)
    outputs = [('summary', report)]
    outputs += [(version + '-source', source) for version, source in documents.items()]
    outputs += [(version + '-evidence', item) for version, item in evidence.items()]
    for name, value in outputs:
        with (out / (name + '.json')).open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(report['mismatches'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
