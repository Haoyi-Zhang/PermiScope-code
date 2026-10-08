"""Exact coverage rows across source families and analysis variants."""
from __future__ import annotations
import unittest

from pcpe.framework_cases import revision_pair
from pcpe.lowering import Variant, lower
from pcpe.source_checker import reference_lower
from pcpe.source_model import parse_source


def scan_coverage(source, facts, rules):
    statements = []
    for method in sorted(source.method_map.values(), key=lambda item: item.key):
        for stmt in method.body:
            related = [rule for rule in rules if rule['source'] == stmt['id']]
            statements.append(dict(id=stmt['id'], method=method.key, op=stmt['op'],
                facts=0, rules=len(related),
                opaque_triggers=sum(rule['certainty'] == 'opaque-trigger' for rule in related),
                opaque_effects=sum(rule['certainty'] == 'opaque-effect' for rule in related)))
    entries = []
    for entry in sorted(source.entries, key=lambda item: item.name):
        key = 'entry:' + entry.name
        entries.append(dict(id=key, facts=sum(fact['source'] == key for fact in facts),
                            rules=0))
    return dict(language='bfil-coverage-1', entries=entries, statements=statements,
                totals=dict(facts=len(facts), rules=len(rules),
                            statements=len(statements), entries=len(entries)))


class CoverageCountTests(unittest.TestCase):
    def check_source(self, document, variant):
        compiled = lower(document, variant)
        reference = reference_lower(document, variant.document())
        self.assertEqual(compiled, reference)
        expected = scan_coverage(parse_source(document), compiled['ir']['facts'], compiled['ir']['rules'])
        self.assertEqual(compiled['coverage'], expected)
        rows = expected['entries'] + expected['statements']
        self.assertEqual(sum(row['facts'] for row in rows), len(compiled['ir']['facts']))
        self.assertEqual(sum(row['rules'] for row in rows), len(compiled['ir']['rules']))

    def test_frozen_revision_endpoints(self):
        variants = (Variant(), Variant(include_opaque=True), Variant(fields='insensitive'),
                    Variant(context='insensitive'), Variant(dispatch='cha'))
        for index in range(300):
            _, old, new, _ = revision_pair(index)
            for endpoint in (old, new):
                for variant in variants:
                    with self.subTest(index=index, endpoint='new' if endpoint is new else 'old', variant=variant):
                        self.check_source(endpoint, variant)

    def test_zero_statement_rows(self):
        _, source, _, _ = revision_pair(0)
        for cls in source['classes']:
            for method in cls['methods']:
                method['body'] = []
        self.check_source(source, Variant())
        self.check_source(source, Variant(include_opaque=True))

    def test_statement_id_can_equal_entry_label(self):
        source = dict(language='bfil-1', permissions=['PERM_A'],
            classes=[dict(name='Svc', super=None, fields=[], methods=[dict(
                name='run', params=[], returns=None, locals=[], body=[dict(
                    id='entry:API', op='check', permission='PERM_A')])])],
            services=[dict(name='service', declared_class='Svc', implementation_class='Svc')],
            entries=[dict(name='API', service='service', selector='run', arg_classes=[])])
        for variant in (Variant(), Variant(include_opaque=True), Variant(fields='insensitive'),
                        Variant(context='insensitive'), Variant(dispatch='cha')):
            with self.subTest(variant=variant):
                self.check_source(source, variant)
                coverage = lower(source, variant)['coverage']
                self.assertEqual(coverage['totals']['rules'], 1)
                self.assertEqual(coverage['entries'][0]['rules'], 0)
                self.assertEqual(coverage['statements'][0]['rules'], 1)


if __name__ == '__main__':
    unittest.main()
