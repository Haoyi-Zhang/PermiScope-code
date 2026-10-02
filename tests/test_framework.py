from __future__ import annotations
import ast,copy,json,tempfile,unittest
from pathlib import Path

from pcpe.framework_cases import (
    field_case, context_case, hierarchy_case, revision_pair,
    profile_for_seed, revision_signature, structural_signature,
)
from pcpe.source_model import parse_source
from pcpe.lowering import lower,Variant
from pcpe.source_checker import reference_lower,validate_source_evidence
from pcpe.evidence import build_evidence
from pcpe.source_oracle import permission_oracle,opaque_sites
from pcpe.source_revision import transport_complete
from pcpe.model import parse_program
from pcpe.producer import extract
from pcpe.public_slice import validate_public_slice
from pcpe.java_slice import extract_permission_calls
from pcpe.framework_faults import CASES,mutate
from pcpe.weighted_checker import validate_weighted

ROOT=Path(__file__).resolve().parents[1]

class FrameworkTests(unittest.TestCase):
    def test_producer_consumer_lowerings_agree(self):
        for maker in (field_case,context_case,hierarchy_case):
            source=maker(1)
            for variant in (Variant(),Variant(include_opaque=True),Variant(fields='insensitive'),Variant(context='insensitive'),Variant(dispatch='cha')):
                with self.subTest(maker=maker.__name__,variant=variant):
                    self.assertEqual(lower(source,variant),reference_lower(source,variant.document()))
    def test_field_oracle(self):
        self.assertEqual(permission_oracle(field_case(1))[0],{('F1_API','PERM_A')})
        self.assertEqual(permission_oracle(field_case(1,changed=True))[0],{('F1_API','PERM_B')})
    def test_context_oracle(self):
        self.assertEqual(permission_oracle(context_case(1))[0],{('C1_API','PERM_A')})
        self.assertEqual(permission_oracle(context_case(1,changed=True))[0],{('C1_API','PERM_B')})
    def test_hierarchy_oracle(self):
        self.assertEqual(permission_oracle(hierarchy_case(1))[0],{('H1_API','PERM_A')})
        self.assertEqual(permission_oracle(hierarchy_case(1,changed=True))[0],{('H1_API','PERM_B')})
    def test_evidence_accepted(self):
        for source in (field_case(0),context_case(0),hierarchy_case(0)):
            evidence,_=build_evidence(source);self.assertTrue(validate_source_evidence(source,evidence).accepted)
    def test_two_site_unresolved_witness(self):
        evidence,_=build_evidence(field_case(0))
        row=next(x for x in evidence['classification'] if x['status']=='unresolved')
        self.assertEqual(row['minimum_opaque_uses'],2)
        self.assertEqual(len(row['witness_opaque_sites']),2)
        self.assertEqual(len(set(row['witness_opaque_sites'])),2)
    def test_two_site_inclusion_minimal_core(self):
        source=field_case(0);evidence,_=build_evidence(source)
        row=next(x for x in evidence['classification'] if x['status']=='unresolved')
        self.assertEqual(len(row['inclusion_minimal_opaque_sites']),2)
        self.assertEqual(len(set(row['inclusion_minimal_opaque_sites'])),2)
        self.assertTrue(validate_source_evidence(source,evidence).accepted)

    def test_inclusion_minimal_core_mutation_rejected(self):
        source=field_case(0);evidence,_=build_evidence(source)
        row=next(x for x in evidence['classification'] if x['status']=='unresolved')
        row['inclusion_minimal_opaque_sites']=row['inclusion_minimal_opaque_sites'][:-1]
        self.assertEqual(validate_source_evidence(source,evidence).reason,'classification-mismatch')

    def test_impossible_without_opaque(self):
        evidence,_=build_evidence(field_case(1))
        row=next(x for x in evidence['classification'] if x['query'].endswith(':p2'))
        self.assertEqual(row['status'],'impossible')
    def test_opaque_completion_direct_chain(self):
        source=field_case(0);sites=opaque_sites(source)
        self.assertEqual(len(sites),2)
        lower,_=permission_oracle(source,set())
        one,_=permission_oracle(source,{sites[0]})
        upper,_=permission_oracle(source,set(sites))
        self.assertEqual(lower,{('F0_API','PERM_A')})
        self.assertEqual(one,lower)
        self.assertEqual(upper,{('F0_API','PERM_A'),('F0_API','PERM_C')})

    def test_completion_endpoint_envelope(self):
        for source in (field_case(0),context_case(0),hierarchy_case(0)):
            sites=opaque_sites(source);models=[]
            for mask in range(1<<len(sites)):
                enabled={sites[i] for i in range(len(sites)) if mask&(1<<i)}
                models.append(permission_oracle(source,enabled)[0])
            self.assertEqual(set.intersection(*(set(x) for x in models)),models[0])
            self.assertEqual(set.union(*(set(x) for x in models)),models[-1])
            self.assertTrue(all(models[0]<=x<=models[-1] for x in models))

    def test_completion_monotonicity(self):
        source=field_case(0);sites=opaque_sites(source)
        empty,_=permission_oracle(source,set())
        first,_=permission_oracle(source,{sites[0]})
        both,_=permission_oracle(source,set(sites))
        self.assertTrue(empty<=first<=both)

    def test_unknown_opaque_site_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown opaque site'):
            permission_oracle(field_case(0),{'not-a-source-site'})
    def test_field_insensitive_false_positive(self):
        source=field_case(1);compiled=lower(source,Variant(fields='insensitive'));cert,_=extract(parse_program(compiled['program']))
        names={compiled['program']['atoms'][n['atom']] for n in cert['nodes']}
        self.assertIn('P:e0:p1',names)
    def test_context_insensitive_false_positive(self):
        source=context_case(1);compiled=lower(source,Variant(context='insensitive'));cert,_=extract(parse_program(compiled['program']))
        names={compiled['program']['atoms'][n['atom']] for n in cert['nodes']}
        self.assertIn('P:e0:p1',names)
    def test_cha_false_positive(self):
        source=hierarchy_case(1);compiled=lower(source,Variant(dispatch='cha'));cert,_=extract(parse_program(compiled['program']))
        names={compiled['program']['atoms'][n['atom']] for n in cert['nodes']}
        self.assertIn('P:e0:p0',names);self.assertIn('P:e0:p1',names)
    def test_semantics_preserving_transport_mixes_exact_and_completed_reuse(self):
        # Case 0 is a reachable refactoring: semantics are preserved but the
        # old closure is not complete for the new named intermediate facts.
        _,old,new,pres=revision_pair(0);self.assertTrue(pres)
        old_e,_=build_evidence(old);compiled=lower(new,Variant());_,stats=transport_complete(old_e['lower'],compiled)
        self.assertFalse(stats['conservative_exact']);self.assertGreater(stats['completed_nodes'],0)
        self.assertGreater(stats['reused_nodes'],0)
        # Case 2 adds only unreachable source; the old complete certificate is
        # still complete after source coverage and closure are rechecked.
        _,old,new,pres=revision_pair(2);self.assertTrue(pres)
        old_e,_=build_evidence(old);compiled=lower(new,Variant());_,stats=transport_complete(old_e['lower'],compiled)
        self.assertTrue(stats['conservative_exact']);self.assertEqual(stats['completed_nodes'],0)
    def test_semantics_changing_transport_completes(self):
        _,old,new,pres=revision_pair(1);self.assertFalse(pres)
        old_e,_=build_evidence(old);compiled=lower(new,Variant());_,stats=transport_complete(old_e['lower'],compiled)
        self.assertFalse(stats['conservative_exact']);self.assertGreater(stats['completed_nodes'],0)
    def test_rule_omission_detected_at_coverage_layer(self):
        source=field_case(1);evidence,_=build_evidence(source);evidence['lower']['ir']['rules'].pop()
        self.assertEqual(validate_source_evidence(source,evidence).reason,'lower-ir-mismatch')
    def test_new_source_construct_changes_expected_inventory(self):
        old=field_case(1);new=field_case(1,preserve=True);old_e,_=build_evidence(old)
        self.assertFalse(validate_source_evidence(new,old_e).accepted)
    def test_weighted_distance_too_low_rejected(self):
        source=field_case(0);evidence,_=build_evidence(source);upper=evidence['upper'];q=upper['program']['queries'][-1]
        upper['minimum']['distances'][q]=0
        weights=[r['weight'] for r in upper['ir']['rules']]
        self.assertFalse(validate_weighted(upper['program'],weights,upper['minimum']).accepted)
    def test_public_slice_inventory(self):
        paths=sorted((ROOT/'inputs'/'public-slices').glob('*.json'));self.assertEqual(len(paths),12)
        for p in paths:
            self.assertTrue(validate_public_slice(json.loads(p.read_text())).accepted,p.name)
    def test_public_slice_line_tamper(self):
        p=next((ROOT/'inputs'/'public-slices').glob('*.json'));d=json.loads(p.read_text());d['excerpt']=d['excerpt'].replace(d['anchor']['literal'],'OTHER',1)
        self.assertFalse(validate_public_slice(d).accepted)
    def test_public_slice_lexical_projection(self):
        for path in sorted((ROOT/'inputs'/'public-slices').glob('*.json')):
            record=json.loads(path.read_text());calls=extract_permission_calls(record['excerpt'])
            self.assertIn((record['anchor']['primitive'],record['anchor']['literal'],record['anchor']['permission']),
                          {(x.primitive,x.literal,x.permission) for x in calls})

    def test_public_slice_primitive_tamper(self):
        path=next((ROOT/'inputs'/'public-slices').glob('*.json'));record=json.loads(path.read_text())
        record['anchor']['primitive']='notTheCall'
        self.assertEqual(validate_public_slice(record).reason,'anchor-cardinality')
    def test_fault_fixture_inventory(self):
        specs=sorted((ROOT/'inputs'/'framework-faults').glob('fault-*.json'));self.assertEqual(len(specs),24);self.assertEqual(len(CASES),24)
    def test_fault_fixture_reasons(self):
        source=field_case(0);evidence,_=build_evidence(source)
        for path,case in zip(sorted((ROOT/'inputs'/'framework-faults').glob('fault-*.json')),CASES):
            spec=json.loads(path.read_text());bad_s,bad_e=mutate(case,source,evidence);v=validate_source_evidence(bad_s,bad_e)
            self.assertFalse(v.accepted);self.assertEqual(v.reason,spec['expected_reason'])
    def test_source_checker_does_not_import_lowerer_or_producers(self):
        tree=ast.parse((ROOT/'pcpe/source_checker.py').read_text())
        modules={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        self.assertNotIn('lowering',modules);self.assertNotIn('producer',modules);self.assertNotIn('weighted',modules)
    def test_duplicate_source_occurrence_rejected(self):
        source=field_case(1);api=next(c for c in source['classes'] if c['name'].endswith('_Service'))['methods'][0]
        api['body'][1]['id']=api['body'][0]['id']
        with self.assertRaises(ValueError):parse_source(source)
    def test_service_redirection_type_checked(self):
        source=hierarchy_case(1);source['services'][0]['implementation_class']='H1_ImplA'
        self.assertEqual(permission_oracle(source)[0],{('H1_API','PERM_A')})
    def test_full_generated_prefix(self):
        for i in range(12):
            _,old,new,_=revision_pair(i);parse_source(old);parse_source(new)
            evidence,_=build_evidence(new);self.assertTrue(validate_source_evidence(new,evidence).accepted)

    def test_generated_profiles_and_identifier_erased_pairs_are_unique(self):
        profiles={tuple(profile_for_seed(i).document().values()) for i in range(100)}
        self.assertEqual(len(profiles),100)
        signatures={revision_signature(i) for i in range(300)}
        self.assertEqual(len(signatures),300)
        new_shapes={structural_signature(revision_pair(i)[2]) for i in range(300)}
        self.assertEqual(len(new_shapes),300)

    def test_opaque_depths_cover_one_two_and_three_sites(self):
        self.assertEqual({profile_for_seed(i).opaque_depth for i in range(100)},{0,1,2,3})
        for seed in (0,5,10):
            source=field_case(seed)
            self.assertEqual(len(opaque_sites(source)),profile_for_seed(seed).opaque_depth)

if __name__=='__main__':unittest.main()
