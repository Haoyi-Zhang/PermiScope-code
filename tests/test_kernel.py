from __future__ import annotations
import ast,copy,json,tempfile,unittest
from pathlib import Path
from pcpe.model import parse_program
from pcpe.producer import extract
from pcpe.checker import validate
from pcpe.oracle import exact_model
from pcpe.core import activation_core
from pcpe.revision import transport
from pcpe.check import load
ROOT=Path(__file__).resolve().parents[1]

class KernelTests(unittest.TestCase):
    def setUp(self):
        self.p={'atoms':['a','b','q'],'facts':[0],
          'rules':[{'head':1,'body':[0]},{'head':2,'body':[1]}],'queries':[2]}
        self.c,_=extract(parse_program(self.p))
    def test_fixture_inventory(self):
        paths=sorted((ROOT/'inputs').glob('case[0-9][0-9].json'));self.assertEqual(len(paths),24)
        for path in paths:
            with self.subTest(case=path.stem):
                d=json.loads(path.read_text());v=validate(d['program'],d['certificate'])
                self.assertEqual(v.accepted,d['expected']['accepted']);self.assertEqual(v.reason,d['expected']['reason'])
    def test_good_and_oracle(self):
        self.assertTrue(validate(self.p,self.c).accepted)
        self.assertEqual(exact_model(self.p)[0],frozenset([0,1,2]))
    def test_rule_reordering(self):
        q=copy.deepcopy(self.p);q['rules'].reverse()
        moved,v=transport(self.p,q,self.c);self.assertTrue(v.accepted)
        self.assertTrue(validate(q,moved).accepted)
    def test_new_consequence(self):
        old=copy.deepcopy(self.p);old['rules']=old['rules'][:1];old['queries']=[1,2]
        c,_=extract(parse_program(old));moved,v=transport(old,self.p,c)
        self.assertFalse(v.accepted);self.assertTrue(validate(self.p,moved,closure=False).accepted)
    def test_transport_can_miss_equal_semantics(self):
        old=copy.deepcopy(self.p);old['rules'].append({'head':2,'body':[0]})
        c,_=extract(parse_program(old));chosen=next(x['rule'] for x in c['nodes'] if x['atom']==2)
        new=copy.deepcopy(old);new['rules'].pop(chosen)
        self.assertEqual(exact_model(old)[0],exact_model(new)[0]);self.assertFalse(transport(old,new,c)[1].accepted)
    def test_renamed_atom_fails_closed(self):
        q=copy.deepcopy(self.p);q['atoms'][0]='renamed'
        self.assertEqual(transport(self.p,q,self.c)[1].reason,'atom-identity-changed')
    def test_bad_transport_input(self):
        self.assertFalse(transport(self.p,[],self.c)[1].accepted)
    def test_empty_program(self):
        p={'atoms':['a'],'facts':[],'rules':[],'queries':[0]}
        c,_=extract(parse_program(p));self.assertEqual(c['nodes'],[]);self.assertTrue(validate(p,c).accepted)
    def test_empty_body_is_not_initial_leaf(self):
        p={'atoms':['a'],'facts':[],'rules':[{'head':0,'body':[]}],'queries':[0]}
        c,_=extract(parse_program(p));self.assertEqual(c['nodes'][0]['rule'],0);self.assertTrue(validate(p,c).accepted)
    def test_boolean_ids_rejected(self):
        p=copy.deepcopy(self.p);p['facts']=[False]
        self.assertFalse(validate(p,self.c).accepted)
        with self.assertRaises(ValueError):parse_program(p)
    def test_body_width_bound(self):
        p={'atoms':[str(i) for i in range(18)],'facts':[],
           'rules':[{'head':17,'body':list(range(17))}],'queries':[]}
        self.assertFalse(validate(p,{'nodes':[],'reported':[]}).accepted)
        with self.assertRaises(ValueError):parse_program(p)
    def test_duplicate_atoms_rejected(self):
        p=copy.deepcopy(self.p);p['atoms'][1]='a';self.assertFalse(validate(p,self.c).accepted)
    def test_checker_module_separation(self):
        tree=ast.parse((ROOT/'pcpe/checker.py').read_text())
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertTrue(all(x in ('__future__','dataclasses','typing') for x in imports))
    def test_oracle_bound(self):
        p={'atoms':[str(i) for i in range(11)],'facts':[],'rules':[],'queries':[]}
        with self.assertRaises(ValueError):exact_model(p)
    def test_json_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.json';p.write_text('{"atoms":[],"atoms":["a"]}')
            with self.assertRaises(ValueError):load(p)
    def test_json_nonfinite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.json';p.write_text('{"x":NaN}')
            with self.assertRaises(ValueError):load(p)
    def test_schema_unknown_field(self):
        p=copy.deepcopy(self.p);p['trust']=True;self.assertFalse(validate(p,self.c).accepted)
    def test_incomparable_cores(self):
        p={'atoms':['u','v','q'],'facts':[],
           'rules':[{'head':2,'body':[0]},{'head':2,'body':[1]}],'queries':[2]}
        self.assertEqual(activation_core(p,[0,1],2,[0,1])[0],[1])
        self.assertEqual(activation_core(p,[0,1],2,[1,0])[0],[0])
    def test_core_order_invalid(self):
        with self.assertRaises(ValueError):activation_core(self.p,[1],2,[2])
    def test_core_boolean_order_rejected(self):
        with self.assertRaises(ValueError):activation_core(self.p,[1],2,[True])
    def test_json_size_bound(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'large.json';p.write_bytes(b' '* (16*1024**2+1))
            with self.assertRaises(ValueError):load(p)
    def test_json_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'invalid.json';p.write_bytes(b'\xff')
            with self.assertRaises(ValueError):load(p)
    def test_core_optional_must_be_noninitial(self):
        with self.assertRaises(ValueError):activation_core(self.p,[0],2,[0])
    def test_core_none_and_empty(self):
        p={'atoms':['q','u'],'facts':[],'rules':[],'queries':[0]}
        self.assertIsNone(activation_core(p,[1],0,[1])[0]);p['facts']=[0]
        self.assertEqual(activation_core(p,[1],0,[1])[0],[])

if __name__=='__main__':unittest.main()
