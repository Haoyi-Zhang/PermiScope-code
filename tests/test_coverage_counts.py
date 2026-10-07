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
                            rules=sum(rule['source'] == key for rule in rules)))
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


if __name__ == '__main__':
    unittest.main()
