"""Benign executable regressions for dynamic self dispatch and opaque evolution."""
import unittest

from pcpe.owned_subset import translate_owned
from run_owned_receiver_comparison import compare, concrete_owned, FIXTURES


class OwnedReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.documents, cls.evidence = compare()

    def test_concrete_direct_horn_agreement_and_alias_traces(self):
        self.assertEqual(self.report['concrete_completions'], 6)
        self.assertEqual(self.report['mismatches'], 0)
        for row in self.report['completions']:
            self.assertTrue(row['agreement'])
            self.assertTrue(all(row['heap_aliases'].values()))
            self.assertEqual(len(row['relay_calls']), 2)
            self.assertTrue(all(r['returned_same_object'] for r in row['relay_calls']))

    def test_self_calls_are_virtual_even_inside_opaque_candidates(self):
        for source in self.documents.values():
            for cls in source['classes']:
                for method in cls['methods']:
                    for statement in method['body']:
                        for operation in [statement, *statement.get('candidates', [])]:
                            self.assertNotEqual(operation['op'], 'direct')

    def test_static_self_negative_control_is_not_hidden_by_certificates(self):
        self.assertEqual(self.report['static_self_mismatches'], 6)
        for row in self.report['negative_controls']:
            self.assertTrue(row['self_consistent_wrong_source_accepted'])
            self.assertFalse(row['correct_source_accepts_wrong_evidence'])
            self.assertEqual(row['correct_source_rejection'], 'lower-ir-mismatch')

    def test_opaque_revision_changes_completion_not_permission_endpoints(self):
        old = self.report['opaque_explanations']['old']
        new = self.report['opaque_explanations']['new']
        self.assertEqual((old['status'], new['status']), ('unresolved', 'unresolved'))
        self.assertEqual((old['minimum_opaque_uses'], new['minimum_opaque_uses']), (1, 2))
        self.assertEqual(old['inclusion_minimal_opaque_sites'], ['dispatch.outer'])
        self.assertEqual(new['inclusion_minimal_opaque_sites'], ['dispatch.inner', 'dispatch.outer'])
        before = concrete_owned('old', {'dispatch.outer'})[0]
        after = concrete_owned('new', {'dispatch.outer'})[0]
        self.assertEqual(before - after, {('API', 'P_C')})
        for endpoint in ('lower', 'upper'):
            self.assertTrue(self.report['endpoint_transports'][endpoint]['revised_source_accepted'])

    def test_field_and_context_controls_retain_real_false_positives(self):
        for row in self.report['lower_endpoint_ablations']:
            expected = [] if row['variant'] == 'full' else [('API', 'P_B')]
            self.assertEqual(row['false_positives'], expected)
            self.assertEqual(row['false_negatives'], [])

    def test_inherited_self_call_and_terminal_return(self):
        text = (FIXTURES / 'old.py').read_text(encoding='utf-8')
        inherited = text.replace('loaded.enforce()', 'self.forward(loaded)')
        inherited = inherited.replace('class Service:',
            'class ServiceBase:\n    def forward(self, value: Guard) -> None:\n        value.enforce()\n\n\nclass Service(ServiceBase):')
        source = translate_owned(inherited, 'inherited-owned.py')
        service = next(c for c in source['classes'] if c['name'] == 'Service')
        calls = [s for s in service['methods'][-1]['body'] if s['op'] == 'invoke']
        self.assertTrue(any(s['selector'] == 'forward' and s['recv'] == 'this' for s in calls))

    def test_fixed_execution_paths_and_choice_inventory(self):
        with self.assertRaises(ValueError):
            concrete_owned('arbitrary', set())
        with self.assertRaises(RuntimeError):
            concrete_owned('new', {'unknown'})


if __name__ == '__main__':
    unittest.main()
