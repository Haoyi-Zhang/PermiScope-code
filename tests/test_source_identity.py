"""Bounded regression checks for source identity and semantic transport."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from pcpe.source_model import member_key, parse_source
from pcpe.lowering import lower, Variant
from pcpe.source_checker import reference_lower, validate_source_evidence, _reference_minimal_sites
from pcpe.evidence import build_evidence
from pcpe.source_oracle import permission_oracle
from pcpe.source_identity import SemanticCatalog
from pcpe.source_revision import transport_complete
from pcpe.framework_cases import field_case, structural_signature
from pcpe.checker import validate


def small(permission="PERM_ALPHA"):
    return {"language":"bfil-1", "permissions":[permission],
            "classes":[{"name":"Svc","super":None,"fields":[],
                        "methods":[{"name":"run","params":[],"returns":None,"locals":[],
                                    "body":[{"id":"check","op":"check","permission":permission}]}]}],
            "services":[{"name":"service","declared_class":"Svc","implementation_class":"Svc"}],
            "entries":[{"name":"API","service":"service","selector":"run","arg_classes":[]}]}


def permission_pairs(item, certificate):
    catalog=item["ir"]["catalog"];atoms=item["program"]["atoms"]
    result=set()
    for node in certificate["nodes"]:
        parts=atoms[node["atom"]].split(":")
        if parts[0]=="P":
            result.add((catalog["entries"][int(parts[1][1:])],
                        catalog["permissions"][int(parts[2][1:])]))
    return result


class SourceIdentityTests(unittest.TestCase):
    def test_retained_scale_certificates_are_accepted_on_distinct_inputs(self):
        root=Path(__file__).resolve().parents[1]/"results"/"observed"
        for size in (128,1280,12800):
            for seeded in (0,1):
                stem=f"scale-{size}-{seeded}"
                program=json.loads((root/(stem+"-input.json")).read_text(encoding="utf-8"))
                certificate=json.loads((root/(stem+"-certificate.json")).read_text(encoding="utf-8"))
                self.assertTrue(validate(program,certificate).accepted)
                self.assertEqual(len(program["facts"]),seeded)
                self.assertEqual(len(certificate["nodes"]),size if seeded else 0)
                self.assertTrue(all(rule["body"] for rule in program["rules"]))

    def test_dotted_declarations_and_fields_remain_distinct_and_covered(self):
        source=small("PERM_ALPHA")
        source["permissions"].append("PERM_BETA")
        source["classes"]=[];source["services"]=[];source["entries"]=[]
        for owner,method,field,permission,entry in (
                ("A.B","run","slot","PERM_ALPHA","first"),
                ("A","B.run","B.slot","PERM_BETA","second")):
            reference={"owner":owner,"member":field}
            source["classes"].append({"name":owner,"super":None,
                "fields":[{"name":field,"type":owner}],
                "methods":[{"name":method,"params":[],"returns":None,
                    "locals":[{"name":"loaded","type":owner}],
                    "body":[{"id":entry+"_store","op":"store","base":"this","field":reference,"src":"this"},
                            {"id":entry+"_load","op":"load","base":"this","field":reference,"dst":"loaded"},
                            {"id":entry+"_check","op":"check","permission":permission}]}]})
            source["services"].append({"name":entry,"declared_class":owner,"implementation_class":owner})
            source["entries"].append({"name":entry,"service":entry,"selector":method,"arg_classes":[]})
        parsed=parse_source(source)
        self.assertEqual(len(parsed.method_map),2);self.assertEqual(len(parsed.field_map),2)
        self.assertNotEqual(member_key("A.B","run"),member_key("A","B.run"))
        evidence,_=build_evidence(source)
        self.assertTrue(validate_source_evidence(source,evidence).accepted)
        self.assertEqual(evidence["lower"]["coverage"]["totals"]["statements"],6)
        self.assertEqual(permission_pairs(evidence["lower"],evidence["lower"]["certificate"]),
                         {("first","PERM_ALPHA"),("second","PERM_BETA")})
        self.assertEqual(permission_oracle(source)[0],{("first","PERM_ALPHA"),("second","PERM_BETA")})
        self.assertEqual(lower(source),reference_lower(source,Variant().document()))
        structural_signature(source)  # identifier erasure also preserves both declarations

    def test_no_declaration_is_hidden_from_validation(self):
        source=small()
        original=source["classes"][0];original["name"]="A.B"
        original["methods"][0]["body"][0]["permission"]="UNDECLARED"
        other=copy.deepcopy(original);other["name"]="A";other["methods"][0]["name"]="B.run"
        other["methods"][0]["body"]=[{"id":"valid_check","op":"check","permission":"PERM_ALPHA"}]
        source["classes"].append(other)
        source["services"][0].update(declared_class="A",implementation_class="A")
        source["entries"][0]["selector"]="B.run"
        with self.assertRaisesRegex(ValueError,"unknown permission"):
            parse_source(source)

    def test_ambiguous_legacy_reference_requires_owner_member(self):
        source=small()
        original=source["classes"][0];original["name"]="A.B"
        other=copy.deepcopy(original);other["name"]="A";other["methods"][0]["name"]="B.run"
        other["methods"][0]["body"]=[{"id":"call","op":"direct","dst":None,"target":"A.B.run","args":[]}]
        source["classes"].append(other)
        source["services"][0].update(declared_class="A",implementation_class="A")
        source["entries"][0]["selector"]="B.run"
        with self.assertRaisesRegex(ValueError,"ambiguous target reference"):
            parse_source(source)
        other["methods"][0]["body"][0]["target"]={"owner":"A","member":"B.run"}
        self.assertTrue(validate_source_evidence(source,build_evidence(source)[0]).accepted)

    def transport(self, old, new):
        old_e,_=build_evidence(old);compiled=lower(new)
        cert,stats=transport_complete(old_e["lower"],compiled)
        self.assertTrue(validate(compiled["program"],cert).accepted)
        self.assertEqual(permission_pairs(compiled,cert),permission_oracle(new)[0])
        return stats

    def test_same_p0_different_permission_is_not_reuse(self):
        stats=self.transport(small("PERM_ALPHA"),small("PERM_BETA"))
        self.assertEqual(stats["reused_nodes"],2)
        self.assertEqual(stats["completed_nodes"],1)
        self.assertFalse(stats["conservative_exact"])

    def test_earlier_permission_insertion_reuses_remapped_permission(self):
        old=small();new=copy.deepcopy(old);new["permissions"].insert(0,"AAA")
        stats=self.transport(old,new)
        self.assertEqual(stats["reused_nodes"],3);self.assertEqual(stats["completed_nodes"],0)

    def test_entry_rename_cannot_reuse_e0(self):
        old=small();new=copy.deepcopy(old);new["entries"][0]["name"]="RENAMED"
        self.assertEqual(self.transport(old,new)["reused_nodes"],0)

    def test_method_rename_cannot_reuse_m0(self):
        old=small();new=copy.deepcopy(old)
        new["classes"][0]["methods"][0]["name"]="renamed"
        new["entries"][0]["selector"]="renamed"
        self.assertEqual(self.transport(old,new)["reused_nodes"],0)

    def test_opaque_tokens_remap_after_earlier_unreachable_allocation(self):
        old=field_case(0);new=copy.deepcopy(old)
        new["classes"].append({"name":"AAA","super":None,"fields":[],
            "methods":[{"name":"run","params":[],"returns":None,
                "locals":[{"name":"x","type":"AAA"}],
                "body":[{"id":"AAA_new","op":"new","dst":"x","class":"AAA"},
                        {"id":"AAA_call","op":"direct","dst":None,
                         "target":{"owner":"AAA","member":"run"},"args":[]}]}]})
        old_e,_=build_evidence(old);compiled=lower(new,Variant(include_opaque=True))
        cert,stats=transport_complete(old_e["upper"],compiled)
        self.assertTrue(validate(compiled["program"],cert).accepted)
        self.assertEqual(stats["reused_nodes"],len(old_e["upper"]["certificate"]["nodes"]))
        self.assertEqual(stats["completed_nodes"],0)
        self.assertEqual(permission_pairs(compiled,cert),
                         permission_oracle(new,{"F0_opaque_0","F0_opaque_1"})[0])

    def test_declaration_and_inventory_order_do_not_affect_reuse(self):
        old=field_case(0);new=copy.deepcopy(old)
        new["classes"].reverse();new["permissions"].reverse()
        for cls in new["classes"]:
            cls["methods"].reverse();cls["fields"].reverse()
        stats=self.transport(old,new)
        self.assertEqual(stats["reused_nodes"],stats["new_certificate_nodes"])

    def test_earlier_unreachable_method_field_entry_and_local_do_not_rebind(self):
        old=field_case(1);new=copy.deepcopy(old)
        service=next(cls for cls in new["classes"] if cls["name"].endswith("_Service"))
        service["fields"].append({"name":"AAA","type":service["name"]})
        api=next(method for method in service["methods"] if method["name"]=="api")
        api["locals"].append({"name":"AAA","type":service["name"]})
        new["classes"].append({"name":"AAA","super":None,"fields":[],
            "methods":[{"name":"run","params":[],"returns":None,"locals":[],
                        "body":[{"id":"AAA_call","op":"direct","dst":None,
                                 "target":{"owner":"AAA","member":"run"},"args":[]}]}]})
        new["services"].append({"name":"AAA","declared_class":"AAA","implementation_class":"AAA"})
        new["entries"].append({"name":"AAA","service":"AAA","selector":"run","arg_classes":[]})
        old_e,_=build_evidence(old)
        stats=self.transport(old,new)
        self.assertEqual(stats["reused_nodes"],len(old_e["lower"]["certificate"]["nodes"]))

    def test_allocation_class_change_does_not_reuse_points_to_identity(self):
        old=field_case(1);new=copy.deepcopy(old)
        service=next(cls for cls in new["classes"] if cls["name"].endswith("_Service"))
        next(stmt for stmt in service["methods"][0]["body"] if stmt["id"]=="F1_new_a")["class"]="F1_GuardB"
        old_ir=lower(old)["ir"];new_ir=lower(new)["ir"]
        old_cat=SemanticCatalog(old_ir);new_cat=SemanticCatalog(new_ir)
        matching=next(f for f in old_ir["rules"] if f["source"]=="F1_new_a")
        changed=next(f for f in new_ir["rules"] if f["source"]=="F1_new_a")
        self.assertNotEqual(old_cat.rule(matching),new_cat.rule(changed))
        self.transport(old,new)

    def test_reference_core_closure_count_includes_audit(self):
        evidence,_=build_evidence(field_case(0));upper=evidence["upper"]
        sites=sorted({r["source"] for r in upper["ir"]["rules"] if r["certainty"]=="opaque-trigger"})
        query=next(row["query"] for row in evidence["classification"] if row["status"]=="unresolved")
        qi=upper["program"]["atoms"].index(query)
        from pcpe import source_checker
        with patch.object(source_checker,"_reference_closure",wraps=source_checker._reference_closure) as calls:
            core=_reference_minimal_sites(upper,qi,sites)
            self.assertEqual(calls.call_count,len(sites)+len(core)+2)

    def test_exact_atom_set_with_bad_reason_or_order_is_rejected(self):
        program={"atoms":["a","q"],"facts":[0],
                 "rules":[{"head":1,"body":[0]}],"queries":[1]}
        good={"nodes":[{"atom":0,"rule":-1},{"atom":1,"rule":0}],"reported":[1]}
        self.assertTrue(validate(program,good).accepted)
        wrong=copy.deepcopy(good);wrong["nodes"][1]["rule"]=-1
        self.assertEqual(validate(program,wrong).reason,"unjustified-leaf")
        wrong=copy.deepcopy(good);wrong["nodes"].reverse()
        self.assertEqual(validate(program,wrong).reason,"unsupported-premise")


if __name__=="__main__":
    unittest.main()
