"""Contract behavior tests; all edge-case mutations use in-memory fixtures."""
import ast
import copy
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import automation_exposure_integration as module


def fixture(status="TOP_CANDIDATE", mappings=None, values=None, eligible=None,
            metadata=None, drop_fields=()):
    contract = module.read_json(ROOT / module.BASE / "step7b1/exposure_integration_methodology_contract_v1.json")
    mappings = mappings if mappings is not None else [("A", "1", "EQUIVALENT")]
    values = values if values is not None else {"1": "0.25", "2": "0.75"}
    eligible = eligible if eligible is not None else ["A"]
    inference = [dict(profile_group_id="p", inference_status=status, eligible_candidate_count=str(len(eligible)),
                      top_onet_soc_code=eligible[0] if eligible else "DIAGNOSTIC",
                      top_onet_occupation_title=f"Modern {eligible[0]}" if eligible else "Diagnostic")]
    candidates = [dict(profile_group_id="p", candidate_rank=str(rank), candidate_eligible="TRUE",
        onet_soc_code=soc, onet_occupation_title=f"Modern {soc}", evidence_score=str(10-rank),
        evidence_provenance="Recorded audit evidence", eligibility_provenance="Eligible gate")
        for rank, soc in enumerate(eligible,1)]
    candidates.append(dict(profile_group_id="p",candidate_rank="99",candidate_eligible="FALSE",
                           onet_soc_code="REJECTED",onet_occupation_title="Rejected",evidence_score="100"))
    for row in candidates:
        if row["candidate_eligible"] == "TRUE":
            row.update((metadata or {}).get(row["onet_soc_code"], {}))
            for field in drop_fields:
                row.pop(field, None)
    crosswalk = [dict(mapping_status="FROZEN",modern_onet_soc_code=soc,modern_onet_title=f"Modern {soc}",
        automation_record_id=sid,automation_occupation=f"Source {sid}",relationship_type=rel,
        evidence_source="{}",adjudication_reason="Recorded scope limitation",crosswalk_version="v1.0")
        for soc,sid,rel in mappings]
    sources=[dict(record_id=sid,occupation=f"Source {sid}",automation_probability=value) for sid,value in values.items()]
    provenance=[dict(automation_record_id=sid,automation_occupation=f"Source {sid}",
        wocke_taxonomy_status="LABEL_CORRESPONDENCE_ONLY",notes="Local lineage unverified") for sid in values]
    return module.ExposureEngine(contract,inference,candidates,crosswalk,sources,provenance,
        dict(frozen_engine="fixture",freeze_version="occupation-inference-v1.0"))


class ExposureTests(unittest.TestCase):
    def test_top_mapped(self):
        r=fixture().evaluate_profile("p")
        self.assertEqual(r["coverage_state"],"TOP_MAPPED")
        self.assertEqual(r["candidates"][0]["source_records"][0]["historical_exposure_value"],0.25)

    def test_top_unmapped_no_fallback(self):
        r=fixture(mappings=[]).evaluate_profile("p")
        self.assertEqual(r["coverage_state"],"TOP_UNMAPPED")
        self.assertEqual(r["candidates"][0]["unavailable_reason"],"UNAVAILABLE_NO_DEFENSIBLE_FROZEN_MAPPING")
        self.assertIsNone(r["profile_exposure_summary"])

    def test_multiple_all_mapped(self):
        r=fixture("MULTIPLE_CANDIDATES",[("A","1","EQUIVALENT"),("B","2","EQUIVALENT")],eligible=["A","B"]).evaluate_profile("p")
        self.assertEqual(r["coverage_state"],"MULTIPLE_ALL_MAPPED")
        self.assertEqual(r["coverage_label"],"2/2")

    def test_multiple_partial_preserves_denominator_and_unmapped(self):
        r=fixture("MULTIPLE_CANDIDATES",eligible=["A","B","C"]).evaluate_profile("p")
        self.assertEqual(r["coverage_state"],"MULTIPLE_PARTIAL")
        self.assertEqual(r["coverage_label"],"1/3")
        self.assertEqual(r["unavailable_candidate_count"],2)
        self.assertEqual({c["modern_soc"] for c in r["candidates"]},{"A","B","C"})

    def test_multiple_none_mapped(self):
        r=fixture("MULTIPLE_CANDIDATES",mappings=[],eligible=["A","B"]).evaluate_profile("p")
        self.assertEqual(r["coverage_state"],"MULTIPLE_NONE_MAPPED")
        self.assertEqual(r["coverage_label"],"0/2")

    def test_insufficient_blocks_lookup_even_with_eligible_diagnostics(self):
        engine=fixture("INSUFFICIENT_EVIDENCE",eligible=["A","B"])
        with patch.object(engine,"evaluate_candidate",side_effect=AssertionError("lookup forbidden")):
            r=engine.evaluate_profile("p")
        self.assertEqual(r["coverage_state"],"INSUFFICIENT")
        self.assertEqual(r["candidates"],[])
        self.assertEqual(r["complete_eligible_candidate_count"],2)
        self.assertIsNone(r["coverage_denominator"])
        self.assertEqual(r["unavailable_reason"],"LOOKUP_NOT_PERFORMED_INSUFFICIENT_INFERENCE")

    def test_zero_preserved(self):
        r=fixture(values={"1":"0"}).evaluate_profile("p")
        s=r["candidates"][0]["source_records"][0]
        self.assertEqual(r["coverage_state"],"TOP_MAPPED")
        self.assertEqual(s["historical_exposure_value"],0.0)
        self.assertEqual(s["historical_exposure_raw"],"0")

    def test_missing_and_invalid_values_have_no_numeric_fallback(self):
        for raw in ("", "NaN", "inf", "-0.1", "1.1", "invalid"):
            with self.subTest(raw=raw):
                r=fixture(values={"1":raw}).evaluate_profile("p")
                c=r["candidates"][0];s=c["source_records"][0]
                self.assertEqual(r["coverage_state"],"TOP_UNMAPPED")
                self.assertEqual(c["unavailable_reason"],"UNAVAILABLE_SOURCE_EXPOSURE_VALUE")
                self.assertIsNone(s["historical_exposure_value"])

    def test_broader_semantics_source_attribution(self):
        s=fixture(mappings=[("A","1","SOURCE_BROADER_THAN_ONET")]).evaluate_profile("p")["candidates"][0]["source_records"][0]
        self.assertEqual(s["semantic_label"],"Historical source-category reference")
        self.assertEqual(s["applicability"],"CONTEXTUAL_BROADER_SOURCE")
        self.assertEqual(s["historical_source_id"],"1")
        self.assertIn("contextual",s["relationship_interpretation"].lower())

    def test_overlap_semantics(self):
        s=fixture(mappings=[("A","1","OVERLAP")]).evaluate_profile("p")["candidates"][0]["source_records"][0]
        self.assertEqual(s["applicability"],"CONTEXTUAL_PARTIAL_OVERLAP")
        self.assertEqual(s["semantic_label"],"Historical source-category reference")

    def test_shared_source_identity(self):
        r=fixture("MULTIPLE_CANDIDATES",[("A","1","EQUIVALENT"),("B","1","OVERLAP")],eligible=["A","B"]).evaluate_profile("p")
        source=[c["source_records"][0] for c in r["candidates"]]
        self.assertEqual([s["historical_source_id"] for s in source],["1","1"])
        self.assertEqual(source[0]["shared_with_modern_socs"],["B"])
        self.assertIsNone(r["profile_exposure_summary"])

    def test_multiple_sources_not_collapsed_or_averaged(self):
        r=fixture(mappings=[("A","1","EQUIVALENT"),("A","2","OVERLAP")]).evaluate_profile("p")
        candidate=r["candidates"][0]
        self.assertTrue(candidate["source_ambiguity"])
        self.assertEqual([s["historical_exposure_value"] for s in candidate["source_records"]],[0.25,0.75])
        _,rows,trace=module.flatten([r])
        self.assertEqual(len(rows),1)
        self.assertEqual(len(trace),2)
        self.assertIsNone(rows[0]["historical_exposure_value"])
        self.assertIsNone(rows[0]["historical_source_id"])

    def test_partial_source_values_preserved(self):
        r=fixture(mappings=[("A","1","EQUIVALENT"),("A","2","OVERLAP")],values={"1":"0.25","2":""}).evaluate_profile("p")
        self.assertEqual(r["coverage_state"],"TOP_MAPPED")
        self.assertEqual(len(r["candidates"][0]["source_records"]),2)
        self.assertEqual(r["candidates"][0]["source_records"][1]["unavailable_reason"],"UNAVAILABLE_SOURCE_EXPOSURE_VALUE")

    def test_multiple_summary_always_null(self):
        for mappings in ([],[("A","1","EQUIVALENT")],[("A","1","EQUIVALENT"),("B","2","OVERLAP")]):
            r=fixture("MULTIPLE_CANDIDATES",mappings=mappings,eligible=["A","B"]).evaluate_profile("p")
            self.assertIsNone(r["profile_exposure_summary"])

    def test_no_rank_one_shortcut_or_mapped_only_filter(self):
        r=fixture("MULTIPLE_CANDIDATES",mappings=[("B","1","EQUIVALENT")],eligible=["A","B"]).evaluate_profile("p")
        self.assertEqual([c["modern_soc"] for c in r["candidates"]],["A","B"])
        self.assertFalse(r["candidates"][0]["mapping_available"])
        self.assertTrue(r["candidates"][1]["mapping_available"])

    def test_no_model_legacy_or_skill_imports(self):
        tree=ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imports=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.update(a.name.split('.')[0] for a in node.names)
            elif isinstance(node,ast.ImportFrom):imports.add(node.module.split('.')[0])
        self.assertLessEqual(imports,{"__future__","argparse","ast","csv","hashlib","json","math","platform","collections","pathlib"})
        self.assertEqual(fixture(mappings=[]).evaluate_profile("p")["coverage_state"],"TOP_UNMAPPED")

    def test_invalid_source_identity_fails_explicitly(self):
        with self.assertRaises(module.ArtifactValidationError):
            fixture(mappings=[("A","missing","EQUIVALENT")])

    def test_earlier_version_frozen_edges_included(self):
        engine=fixture()
        self.assertEqual(engine.crosswalk[0]["crosswalk_version"],"v1.0")
        self.assertEqual(engine.evaluate_profile("p")["coverage_state"],"TOP_MAPPED")

    def test_repeated_runs_identical(self):
        engine=fixture("MULTIPLE_CANDIDATES",eligible=["A","B"])
        first=module.flatten(engine.evaluate_corpus())
        second=module.flatten(engine.evaluate_corpus())
        self.assertEqual(json.dumps(first,sort_keys=True),json.dumps(second,sort_keys=True))

    def test_pinned_artifact_hash_failure(self):
        with patch.object(module,"sha256",return_value="wrong"):
            with self.assertRaises(module.ArtifactValidationError):module.load_engine(ROOT)

    def test_full_corpus_matches_frozen_reference_per_profile(self):
        engine=module.load_engine(ROOT)
        results=engine.evaluate_corpus()
        profiles,candidates,trace=module.flatten(results)
        summary=module.summarize(results,candidates,trace)
        self.assertEqual(summary["state_counts"],dict(TOP_MAPPED=23,TOP_UNMAPPED=12,
            MULTIPLE_ALL_MAPPED=11,MULTIPLE_PARTIAL=82,MULTIPLE_NONE_MAPPED=53,INSUFFICIENT=163))
        self.assertEqual(len(profiles),344)
        self.assertEqual(len(candidates),542)
        self.assertEqual(summary["distinct_active_lookup_SOCs"],170)
        self.assertEqual(summary["distinct_mapped_modern_SOCs"],27)
        byid={r["profile_input_id"]:r for r in results}
        reference=module.read_csv(ROOT/module.BASE/"step7a7/profile_exposure_coverage_audit_v4.csv")
        for row in reference:
            result=byid[row["profile_group_id"]]
            if result["coverage_state"]!="INSUFFICIENT":
                self.assertEqual({c["modern_soc"] for c in result["candidates"]},set(json.loads(row["eligible_soc_codes"])))
                self.assertEqual(result["mapped_candidate_count"],int(row["frozen_crosswalk_soc_count"]))
        self.assertEqual(results,engine.evaluate_corpus())

    def test_duplicate_conflicting_ranks_rejected(self):
        with self.assertRaises(module.ArtifactValidationError):
            fixture("MULTIPLE_CANDIDATES",eligible=["A","B"],metadata={"B":{"candidate_rank":"1"}})

    def test_negative_rank_rejected(self):
        with self.assertRaises(module.ArtifactValidationError):fixture(metadata={"A":{"candidate_rank":"-1"}})

    def test_zero_rank_outside_one_based_domain(self):
        with self.assertRaises(module.ArtifactValidationError):fixture(metadata={"A":{"candidate_rank":"0"}})

    def test_nan_evidence_rejected(self):
        with self.assertRaises(module.ArtifactValidationError):fixture(metadata={"A":{"evidence_score":"NaN"}})

    def test_positive_infinity_evidence_rejected(self):
        with self.assertRaises(module.ArtifactValidationError):fixture(metadata={"A":{"evidence_score":"+Infinity"}})

    def test_negative_infinity_evidence_rejected(self):
        with self.assertRaises(module.ArtifactValidationError):fixture(metadata={"A":{"evidence_score":"-Infinity"}})

    def test_nullable_rank_preserved(self):
        for raw in (None,"","null"):
            r=fixture(metadata={"A":{"candidate_rank":raw}}).evaluate_profile("p")
            self.assertIsNone(r["candidates"][0]["candidate_rank"])

    def test_absent_metadata_preserved_null(self):
        r=fixture(drop_fields=("candidate_rank","evidence_score")).evaluate_profile("p")
        self.assertIsNone(r["candidates"][0]["candidate_rank"])
        self.assertIsNone(r["candidates"][0]["evidence_score"])

    def test_nullable_evidence_score_preserved(self):
        for raw in (None,"","null"):
            r=fixture(metadata={"A":{"evidence_score":raw}}).evaluate_profile("p")
            self.assertIsNone(r["candidates"][0]["evidence_score"])

    def test_evidence_zero_preserved(self):
        r=fixture(metadata={"A":{"evidence_score":"0"}}).evaluate_profile("p")
        self.assertEqual(r["candidates"][0]["evidence_score"],0.0)

    def test_no_invented_evidence_range(self):
        for raw in ("-1000","1000000"):
            r=fixture(metadata={"A":{"evidence_score":raw}}).evaluate_profile("p")
            self.assertEqual(r["candidates"][0]["evidence_score"],float(raw))

    def test_malformed_non_null_rank_rejected(self):
        for raw in ("bad","1.5",1.5,True):
            with self.subTest(raw=raw),self.assertRaises(module.ArtifactValidationError):
                fixture(metadata={"A":{"candidate_rank":raw}})

    def test_malformed_non_null_evidence_rejected(self):
        with self.assertRaises(module.ArtifactValidationError):fixture(metadata={"A":{"evidence_score":"bad"}})

    def test_top_multiple_eligible_socs_rejected(self):
        with self.assertRaises(module.ArtifactValidationError) as error:fixture(eligible=["A","B"])
        self.assertEqual(error.exception.check_id,"TOP_ELIGIBLE_SET_INVARIANT")

    def test_nullable_rank_uses_authoritative_row_order(self):
        r=fixture("MULTIPLE_CANDIDATES",eligible=["A","B"],
                  metadata={"A":{"candidate_rank":None},"B":{"candidate_rank":"1"}}).evaluate_profile("p")
        self.assertEqual([c["modern_soc"] for c in r["candidates"]],["A","B"])
        self.assertEqual([c["candidate_rank"] for c in r["candidates"]],[None,1])
        self.assertEqual(r,fixture("MULTIPLE_CANDIDATES",eligible=["A","B"],
                  metadata={"A":{"candidate_rank":None},"B":{"candidate_rank":"1"}}).evaluate_profile("p"))

    def assert_failure(self,response):
        self.assertEqual(response["validation_status"],"ERROR")
        self.assertEqual(response["failure_reason"],"ARTIFACT_VALIDATION_FAILURE")
        self.assertTrue(response["validation_errors"])
        self.assertIn("check_id",response["validation_errors"][0])
        self.assertIn("error_type",response["validation_errors"][0])
        self.assertIsNone(response["exposure_state"])
        self.assertIsNone(response["coverage_state"])
        self.assertIsNone(response["exposure"])
        self.assertIsNone(response["profile_exposure_summary"])

    def test_malformed_csv_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"fixture.csv";path.write_text("wrong\nvalue\n",encoding="utf-8")
            self.assert_failure(module.validation_boundary(module.read_csv,path,("profile_group_id",)))

    def test_malformed_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"fixture.json";path.write_text("{broken",encoding="utf-8")
            self.assert_failure(module.validation_boundary(module.read_json,path))

    def test_structured_boundary_expected_error_types(self):
        for error in (ValueError("invalid"),KeyError("missing"),OSError("unreadable")):
            def operation():raise error
            self.assert_failure(module.validation_boundary(operation,context={"operation":"fixture"}))

    def test_validation_failure_has_no_fallback(self):
        with patch.object(module.ExposureEngine,"evaluate_candidate",side_effect=AssertionError("fallback forbidden")) as lookup:
            self.assert_failure(module.validation_boundary(fixture,eligible=["A","B"]))
            lookup.assert_not_called()

    def test_cli_uses_same_failure_envelope(self):
        stderr=io.StringIO()
        with patch.object(sys,"argv",["engine"]),patch.object(module,"build",side_effect=KeyError("missing")),contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as error:module.main()
        self.assertEqual(error.exception.code,1)
        self.assert_failure(json.loads(stderr.getvalue()))

    def test_unexpected_programmer_error_propagates(self):
        def operation():raise RuntimeError("programmer fault")
        with self.assertRaises(RuntimeError):module.validation_boundary(operation)

    def test_assurance_counters_are_derived(self):
        r=fixture("INSUFFICIENT_EVIDENCE").evaluate_profile("p")
        modified=copy.deepcopy(r)
        modified["candidates"]=[fixture().evaluate_profile("p")["candidates"][0]]
        modified["profile_exposure_summary"]=0
        _,candidates,trace=module.flatten([modified])
        summary=module.summarize([modified],candidates,trace)
        self.assertEqual(summary["insufficient_lookup_count"],1)
        self.assertEqual(summary["profile_numeric_summary_non_null_count"],1)


if __name__=="__main__":
    unittest.main()
