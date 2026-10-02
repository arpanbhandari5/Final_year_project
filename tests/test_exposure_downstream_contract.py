"""Focused Step 7B.3 freeze and downstream representation checks."""
import csv
import importlib.util
import io
import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import automation_exposure_integration as source
from test_automation_exposure_integration import fixture

FROZEN_PATH = ROOT / "scripts/frozen/automation_exposure_integration_v1_0.py"
spec = importlib.util.spec_from_file_location("frozen_exposure_v1_0", FROZEN_PATH)
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)
FOLDER = ROOT / "data/automation_exposure_integration/step7b3"


def serialized_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if
                         v is None or isinstance(v, (dict, list, bool)) else v for k, v in row.items()})
    return stream.getvalue().encode("utf-8")


class DownstreamContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = source.read_json(FOLDER / "exposure_downstream_contract_v1.json")
        cls.engine = frozen.load_engine(ROOT)
        cls.results = cls.engine.evaluate_corpus()
        cls.profiles, cls.candidates, cls.trace = frozen.flatten(cls.results)

    def test_frozen_engine_exact_copy_and_functionally_identical(self):
        self.assertEqual(FROZEN_PATH.read_bytes(), Path(source.__file__).read_bytes())
        self.assertEqual(self.results, source.load_engine(ROOT).evaluate_corpus())

    def test_six_states_unchanged(self):
        summary = frozen.summarize(self.results, self.candidates, self.trace)
        self.assertEqual(summary, source.read_json(ROOT / source.BASE / "step7b2/historical_exposure_state_summary_v1.json"))
        self.assertEqual(set(self.contract["primary_states"]), set(source.STATES))
        self.assertEqual(len(self.contract["display_state_rules"]), 6)

    def test_top_mapped_provenance_survives(self):
        result = next(r for r in self.results if r["coverage_state"] == "TOP_MAPPED")
        candidate = result["candidates"][0]
        record = candidate["source_records"][0]
        combined = dict(result, **candidate)
        combined.update(record)
        for name in self.contract["required_TOP_mapped_fields"]:
            self.assertIn(name, combined)
            self.assertIsNotNone(combined[name])

    def test_top_unmapped_no_fallback(self):
        for result in self.results:
            if result["coverage_state"] == "TOP_UNMAPPED":
                self.assertIsNone(result["profile_exposure_summary"])
                self.assertFalse(result["candidates"][0]["mapping_available"])
        self.assertFalse(self.contract["legacy_risk_score_fallback_allowed"])

    def test_multiple_cannot_collapse_to_profile_number(self):
        self.assertFalse(self.contract["profile_numeric_summary_allowed"])
        for result in self.results:
            if result["coverage_state"].startswith("MULTIPLE"):
                self.assertIsNone(result["profile_exposure_summary"])
                self.assertEqual(len(result["candidates"]), result["complete_eligible_candidate_count"])
        self.assertTrue(all(r["profile_numeric_summary_allowed"] == "FALSE"
                            for r in self.contract["display_state_rules"]))

    def test_partial_denominator_preserved(self):
        for result in self.results:
            if result["coverage_state"] == "MULTIPLE_PARTIAL":
                self.assertEqual(result["coverage_denominator"], len(result["candidates"]))
                self.assertGreater(result["coverage_denominator"], result["mapped_candidate_count"])
        self.assertTrue(self.contract["shared_source_policy"]["eligible_denominator_unchanged"])

    def test_shared_source_groups_reconstruct_without_independent_confirmation(self):
        result = fixture("MULTIPLE_CANDIDATES", [("A", "1", "EQUIVALENT"),
                         ("B", "1", "OVERLAP")], eligible=["A", "B"]).evaluate_profile("p")
        groups = defaultdict(list)
        for candidate in result["candidates"]:
            for record in candidate["source_records"]:
                groups[(result["profile_input_id"], record["historical_source_id"])].append(candidate["modern_soc"])
        self.assertEqual(dict(groups), {("p", "1"): ["A", "B"]})
        self.assertEqual(self.contract["shared_source_policy"]["group_key"], ["profile_id", "historical_source_id"])
        self.assertFalse(self.contract["shared_source_policy"]["modern_SOC_count_is_independent_measurement_count"])
        fields = {r["field_name"] for r in self.contract["shared_source_group_fields"]}
        self.assertTrue({"modern_socs", "relationship_edges", "source_trace_references"} <= fields)

    def test_broader_source_limitation_survives(self):
        records = [r for r in self.trace if r["relationship_type"] == "SOURCE_BROADER_THAN_ONET"]
        self.assertEqual(len(records), 53)
        self.assertTrue(all(r["relationship_limitation"] and
                            r["semantic_label"] == "Historical source-category reference" for r in records))
        semantics = next(r for r in self.contract["relationship_semantics"] if r["relationship_type"] == "SOURCE_BROADER_THAN_ONET")
        self.assertEqual(semantics["exact_modern_soc_measurement_claim_allowed"], "FALSE")

    def test_overlap_limitation_survives(self):
        records = [r for r in self.trace if r["relationship_type"] == "OVERLAP"]
        self.assertEqual(len(records), 7)
        self.assertTrue(all(r["relationship_limitation"] and r["applicability"] == "CONTEXTUAL_PARTIAL_OVERLAP" for r in records))

    def test_insufficient_no_lookup(self):
        pid = next(pid for pid, r in self.engine.inference.items() if r["inference_status"] == "INSUFFICIENT_EVIDENCE")
        with patch.object(self.engine, "evaluate_candidate", side_effect=AssertionError("lookup forbidden")):
            result = self.engine.evaluate_profile(pid)
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["coverage_state"], "INSUFFICIENT")
        self.assertIsNone(result["profile_exposure_summary"])

    def test_failure_contract_remains_fail_closed(self):
        def fail():
            raise frozen.ArtifactValidationError("fixture validation failure")
        response = frozen.validation_boundary(fail)
        self.assertEqual(response["validation_status"], "ERROR")
        self.assertEqual(response["failure_reason"], "ARTIFACT_VALIDATION_FAILURE")
        self.assertTrue(response["validation_errors"])
        for key in ("coverage_state", "exposure_state", "profile_exposure_summary", "exposure"):
            self.assertIsNone(response[key])
            self.assertIsNone(self.contract["failure_envelope"][key])

    def test_personal_risk_terms_prohibited_not_allowed_display_labels(self):
        for row in self.contract["terminology_rules"]:
            if row["usage_scope"] == "PROHIBITED_APPLICATION_INTERPRETATION":
                self.assertEqual(row["application_display_allowed"], "FALSE")
        allowed = [r["term"] for r in self.contract["terminology_rules"] if r["application_display_allowed"] == "TRUE"]
        for phrase in ("your probability of losing your job", "your AI replacement probability",
                       "your personal job-loss risk", "probability AI will replace you"):
            self.assertNotIn(phrase, allowed)

    def test_deterministic_replay_matches_published_bytes(self):
        self.assertEqual(self.results, self.engine.evaluate_corpus())
        for name, rows in [("profile_historical_exposure_results_v1.csv", self.profiles),
                           ("candidate_historical_exposure_results_v1.csv", self.candidates),
                           ("historical_exposure_source_trace_v1.csv", self.trace)]:
            self.assertEqual(serialized_csv(rows), (ROOT / source.BASE / "step7b2" / name).read_bytes())

    def test_contract_csvs_match_machine_readable_json(self):
        for filename, key in [("exposure_display_state_contract_v1.csv", "display_state_rules"),
                              ("exposure_shared_source_contract_v1.csv", "shared_source_group_fields"),
                              ("exposure_terminology_contract_v1.csv", "terminology_rules"),
                              ("exposure_downstream_provenance_contract_v1.csv", "provenance_fields"),
                              ("exposure_failure_contract_v1.csv", "failure_contract")]:
            self.assertEqual(source.read_csv(FOLDER / filename), self.contract[key])


if __name__ == "__main__":
    unittest.main()
