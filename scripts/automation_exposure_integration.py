"""Deterministic, source-attributed historical exposure lookup (Step 7B.2).

Run with Python -B. This module has no application or model dependencies.
CSV nulls are the literal JSON token null; nested values use JSON.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import platform
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "historical-exposure-integration-v1.0"
BASE = Path("data/automation_exposure_integration")
FROZEN = Path("data/cv_occupation_mapping/frozen_v1_0")
STATES = ("TOP_MAPPED", "TOP_UNMAPPED", "MULTIPLE_ALL_MAPPED", "MULTIPLE_PARTIAL",
          "MULTIPLE_NONE_MAPPED", "INSUFFICIENT")


class ArtifactValidationError(ValueError):
    """Fail closed, without a success state or a numeric fallback."""
    reason_code = "ARTIFACT_VALIDATION_FAILURE"

    def __init__(self, message, check_id="ARTIFACT_VALIDATION", context=None):
        super().__init__(message)
        self.check_id = check_id
        self.context = context


def require(condition, message, check_id="ARTIFACT_VALIDATION", context=None):
    if not condition:
        raise ArtifactValidationError(message, check_id, context)


def nullable_metadata(raw, field, context=None):
    """Absent/None/empty/JSON null are null; supplied numeric zero is not null.

    Rank uses the upstream one-based candidate ordering (positive integer).
    Evidence is an engineering score with no contract-defined numeric range.
    """
    if raw is None or (isinstance(raw, str) and raw.strip() in ("", "null")):
        return None
    try:
        if field == "candidate_rank":
            # Do not truncate decimals, accept bools or silently renumber ranks.
            if isinstance(raw, bool) or isinstance(raw, float):
                raise ValueError("rank must be an integer")
            value = int(raw)
            require(value >= 1, "Candidate rank must be a positive integer",
                    "CANDIDATE_RANK_DOMAIN", context)
        else:
            if isinstance(raw, bool):
                raise ValueError("score must be numeric")
            value = float(raw)
            require(math.isfinite(value), "Evidence score must be finite",
                    "CANDIDATE_EVIDENCE_FINITE", context)
        return value
    except (ValueError, TypeError) as error:
        if isinstance(error, ArtifactValidationError):
            raise
        raise ArtifactValidationError(f"Malformed {field}: {error}",
                                      "CANDIDATE_METADATA_PARSE", context) from error


def failure_response(error, context=None):
    """One contract-shaped error envelope, with no successful state or value."""
    detail = dict(check_id=getattr(error, "check_id", "EXTERNAL_ARTIFACT_VALIDATION"),
                  error_code="ARTIFACT_VALIDATION_FAILURE", error_type=type(error).__name__,
                  message=str(error), context=getattr(error, "context", None) or context)
    return dict(validation_status="ERROR", failure_reason="ARTIFACT_VALIDATION_FAILURE",
                validation_errors=[detail], coverage_state=None, exposure_state=None,
                profile_exposure_summary=None, exposure=None)


def validation_boundary(operation, *args, context=None, **kwargs):
    """External callable API: expected artifact failures become structured errors.

    Internal load/evaluate helpers may raise. Unexpected errors such as
    RuntimeError/AssertionError propagate; they never become successful output.
    """
    try:
        return operation(*args, **kwargs)
    except (ArtifactValidationError, OSError, ValueError, KeyError, TypeError, csv.Error) as error:
        return failure_response(error, context)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path, required=()):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)),
                f"Invalid header: {path}")
        require(set(required) <= set(reader.fieldnames), f"Missing columns: {path}")
        rows = list(reader)
        require(all(None not in row and all(v is not None for v in row.values()) for row in rows),
                f"Malformed CSV rows: {path}")
        return rows


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def unique_index(rows, key):
    result = {}
    for row in rows:
        require(row.get(key) and row[key] not in result, f"Duplicate/missing {key}")
        result[row[key]] = row
    return result


def parse_source_value(raw):
    """Zero is valid; empty, nonfinite and out-of-range values are unavailable."""
    try:
        value = float(raw)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) and 0 <= value <= 1 else None


def load_contract(root):
    folder = root / BASE / "step7b1"
    contract = read_json(folder / "exposure_integration_methodology_contract_v1.json")
    manifest = read_json(folder / "step7b1_methodology_freeze_manifest.json")
    for path, digest in manifest["output_sha256"].items():
        require(sha256(root / path) == digest, f"Contract hash mismatch: {path}")
    names = ["exposure_integration_state_contract_v1.csv", "exposure_relationship_semantics_v1.csv",
             "exposure_unavailability_reason_codes_v1.csv", "exposure_provenance_contract_v1.csv"]
    tables = {name: read_csv(folder / name) for name in names}
    require(contract["status"] == "FROZEN" and tuple(contract["primary_states"]) == STATES,
            "Unsupported methodology states")
    require(tables[names[0]] == contract["state_rules"], "State contract inconsistency")
    for name, key in [(names[1], "relationship_semantics"), (names[2], "unavailability_reasons"),
                      (names[3], "provenance_fields")]:
        normalized = [{k: str(v) for k, v in row.items()} for row in contract[key]]
        require(tables[name] == normalized, f"Contract table inconsistency: {name}")
    require(all(row["rf_fallback_allowed"] == "FALSE" and
                row["profile_level_numeric_summary_allowed"] == "FALSE"
                for row in contract["state_rules"]), "Unsupported fallback/aggregation contract")
    return contract


def input_paths():
    return ([BASE / "step7b1" / name for name in [
        "exposure_integration_methodology_contract_v1.json", "exposure_integration_state_contract_v1.csv",
        "exposure_relationship_semantics_v1.csv", "exposure_unavailability_reason_codes_v1.csv",
        "exposure_provenance_contract_v1.csv", "step7b1_methodology_freeze_manifest.json"]]
        + [FROZEN / name for name in ["cv_occupation_inference_frozen_v1_0.csv",
        "cv_occupation_candidate_audit_frozen_v1_0.csv", "occupation_inference_downstream_contract.csv",
        "occupation_inference_freeze_manifest.json"]]
        + [Path("data") / name for name in ["automation_onet_crosswalk_v4.csv",
        "automation_probability_labels.csv", "source_taxonomy_provenance.csv"]]
        + [BASE / "step7a7" / name for name in ["profile_exposure_coverage_audit_v4.csv",
        "soc_exposure_path_audit_v4.csv", "unique_soc_exposure_coverage_v4.csv",
        "exposure_coverage_summary_v4.json", "crosswalk_v4_freeze_manifest.json",
        "crosswalk_expansion_stopping_rule_v1.json", "crosswalk_phase_final_summary.json",
        "final_targeted_unresolved_register.csv"]])


class ExposureEngine:
    """Validated lookup data and a side-effect-free per-profile evaluation API.

    Direct construction supports isolated synthetic tests. Production callers use
    load_engine, which pins authoritative artifact hashes and schemas.
    """
    def __init__(self, contract, inference, candidates, crosswalk, sources, provenance,
                 inference_manifest, hashes=None):
        self.contract = contract
        self.inference = unique_index(inference, "profile_group_id")
        self.sources = unique_index(sources, "record_id")
        self.provenance = unique_index(provenance, "automation_record_id")
        self.inference_manifest = inference_manifest
        self.hashes = hashes or {}
        self.semantics = unique_index(contract["relationship_semantics"], "relationship_type")
        self.rules = unique_index(contract["state_rules"], "primary_state")
        self.candidates = defaultdict(list)
        for row in candidates:
            require(row["profile_group_id"] in self.inference, "Orphan candidate profile")
            require(row["candidate_eligible"] in ("TRUE", "FALSE"), "Invalid eligibility flag")
            if row["candidate_eligible"] == "TRUE":
                self.candidates[row["profile_group_id"]].append(row)
        self.edges = defaultdict(list)
        self.shared = defaultdict(set)
        self.source_rows = {row["record_id"]: number for number, row in enumerate(sources, 2)}
        self.crosswalk = crosswalk
        seen = set()
        for number, row in enumerate(crosswalk, 2):
            require(row["mapping_status"] in ("FROZEN", "UNRESOLVED", "HELD_OUT", "RESIDUAL_UNMAPPED"),
                    "Unsupported crosswalk status")
            if row["mapping_status"] != "FROZEN":
                continue
            soc, sid = row["modern_onet_soc_code"], row["automation_record_id"]
            require(soc and row["modern_onet_title"] and (soc, sid) not in seen, "Invalid/duplicate frozen edge")
            seen.add((soc, sid))
            require(sid in self.sources and sid in self.provenance, "Frozen source identity missing")
            require(row["automation_occupation"] == self.sources[sid]["occupation"] ==
                    self.provenance[sid]["automation_occupation"], "Source title mismatch")
            require(row["relationship_type"] in self.semantics, "Unsupported frozen relationship")
            evidence = json.loads(row["evidence_source"])
            if "adjudication_status" in evidence:
                require(evidence["adjudication_status"] == "FROZEN", "Conflicting adjudication status")
            if "decision" in evidence:
                require(evidence["decision"].startswith("ACCEPT"), "Conflicting frozen decision")
            self.edges[soc].append((number, row))
            self.shared[sid].add(soc)
        for pid, result in self.inference.items():
            require(result["inference_status"] in ("TOP_CANDIDATE", "MULTIPLE_CANDIDATES", "INSUFFICIENT_EVIDENCE"),
                    "Invalid inference state")
            rows = self.candidates[pid]
            rank_owners = {}
            require(len({r["onet_soc_code"] for r in rows}) == len(rows), "Duplicate eligible SOC")
            require(len(rows) == int(result["eligible_candidate_count"]), "Eligible count mismatch")
            for row in rows:
                require(row["onet_soc_code"] and row["onet_occupation_title"], "Missing candidate identity")
                context = dict(profile_id=pid, modern_soc=row["onet_soc_code"])
                rank = nullable_metadata(row.get("candidate_rank"), "candidate_rank", context)
                nullable_metadata(row.get("evidence_score"), "evidence_score", context)
                if rank is not None:
                    require(rank not in rank_owners, "Conflicting eligible candidate ranks",
                            "ELIGIBLE_RANK_UNIQUENESS", context)
                    rank_owners[rank] = row["onet_soc_code"]
                for _, edge in self.edges.get(row["onet_soc_code"], []):
                    require(row["onet_occupation_title"] == edge["modern_onet_title"], "Modern title mismatch")
            if result["inference_status"] == "TOP_CANDIDATE":
                require(len(rows) == 1, "TOP requires exactly one eligible SOC",
                        "TOP_ELIGIBLE_SET_INVARIANT", dict(profile_id=pid))
                selected = [r for r in rows if r["onet_soc_code"] == result["top_onet_soc_code"]]
                require(len(selected) == 1 and selected[0]["onet_occupation_title"] ==
                        result["top_onet_occupation_title"], "TOP selected identity mismatch")
            if result["inference_status"] == "MULTIPLE_CANDIDATES":
                require(rows, "MULTIPLE has no eligible SOCs")

    def evaluate_candidate(self, audit):
        soc = audit["onet_soc_code"]
        source_records = []
        for row_number, edge in self.edges.get(soc, []):
            sid = edge["automation_record_id"]
            source, provenance = self.sources[sid], self.provenance[sid]
            value = parse_source_value(source["automation_probability"])
            rel = edge["relationship_type"]
            semantics = self.semantics[rel]
            source_records.append(dict(
                historical_source_id=sid, historical_source_title=source["occupation"],
                relationship_type=rel, relationship_interpretation=semantics["operational_interpretation"],
                relationship_limitation=dict(adjudication_reason=edge["adjudication_reason"],
                    evidence_source=json.loads(edge["evidence_source"]), historical_provenance=provenance),
                applicability=self.contract["interpretation_rules"]["relationship_applicability"][rel],
                historical_exposure_value=value,
                historical_exposure_raw=source["automation_probability"] if value is not None else None,
                value_available=value is not None, value_scale="0..1 unchanged local source scalar",
                semantic_label=semantics["preferred_display_term"],
                source_dataset=None,
                source_dataset_version="Wocke V1 reference; DOI 10.17632/czbvhmzwm3.1" if
                    "10.17632/czbvhmzwm3.1" in provenance.get("notes", "") else None,
                source_dataset_date=None,
                lineage_verification_status=provenance["wocke_taxonomy_status"],
                historical_reference_system=provenance.get("historical_system") or None,
                historical_reference_code=provenance.get("historical_code") or None,
                label_verification_status=provenance.get("source_verification_status") or None,
                crosswalk_row_number=row_number, crosswalk_row_introduction_version=edge["crosswalk_version"],
                source_csv_row_number=self.source_rows[sid],
                source_value_file_sha256=self.hashes.get("data/automation_probability_labels.csv"),
                crosswalk_evidence=dict(evidence_source=edge["evidence_source"],
                    adjudication_reason=edge["adjudication_reason"]), source_provenance=provenance,
                shared_with_modern_socs=sorted(self.shared[sid] - {soc}),
                unavailable_reason=None if value is not None else "UNAVAILABLE_SOURCE_EXPOSURE_VALUE"))
        available = any(s["value_available"] for s in source_records)
        reason = None if available else ("UNAVAILABLE_SOURCE_EXPOSURE_VALUE" if source_records else
                                        "UNAVAILABLE_NO_DEFENSIBLE_FROZEN_MAPPING")
        return dict(modern_soc=soc, modern_title=audit["onet_occupation_title"],
            modern_taxonomy="O*NET-SOC", modern_taxonomy_version=None,
            candidate_rank=nullable_metadata(audit.get("candidate_rank"), "candidate_rank"),
            evidence_score=nullable_metadata(audit.get("evidence_score"), "evidence_score"),
            evidence_support=dict(audit), evidence_provenance=dict(
                evidence_provenance=audit.get("evidence_provenance") or None,
                eligibility_provenance=audit.get("eligibility_provenance") or None),
            mapping_available=available, lookup_performed=True, unavailable_reason=reason,
            source_records=source_records, source_ambiguity=len(source_records) > 1,
            source_record_count=len(source_records))

    def evaluate_profile(self, profile_id):
        require(profile_id in self.inference, "Unknown profile")
        original = self.inference[profile_id]
        status = original["inference_status"]
        audit = self.candidates[profile_id]
        if status == "INSUFFICIENT_EVIDENCE":
            evaluated = []  # Gate before any candidate/source lookup.
            state, denominator = "INSUFFICIENT", None
        else:
            selected = audit if status == "MULTIPLE_CANDIDATES" else [
                r for r in audit if r["onet_soc_code"] == original["top_onet_soc_code"]]
            # If any rank is absent, retain authoritative row order as audit
            # ordering only. Never synthesize a replacement or semantic rank.
            ranks = [nullable_metadata(r.get("candidate_rank"), "candidate_rank") for r in selected]
            if all(rank is not None for rank in ranks):
                selected = sorted(selected, key=lambda r: nullable_metadata(r.get("candidate_rank"), "candidate_rank"))
            evaluated = [self.evaluate_candidate(row) for row in selected]
            mapped = sum(row["mapping_available"] for row in evaluated)
            denominator = len(evaluated)
            state = ("TOP_MAPPED" if mapped else "TOP_UNMAPPED") if status == "TOP_CANDIDATE" else (
                "MULTIPLE_ALL_MAPPED" if mapped == denominator else "MULTIPLE_PARTIAL" if mapped else
                "MULTIPLE_NONE_MAPPED")
        mapped = sum(row["mapping_available"] for row in evaluated)
        reason = "LOOKUP_NOT_PERFORMED_INSUFFICIENT_INFERENCE" if state == "INSUFFICIENT" else None
        if evaluated and not mapped:
            codes = {row["unavailable_reason"] for row in evaluated}
            reason = next(iter(codes)) if len(codes) == 1 else None
        result = dict(profile_input_id=profile_id, analysis_context_id=f"frozen:{profile_id}",
            inference_engine=self.inference_manifest["frozen_engine"],
            inference_version=self.inference_manifest["freeze_version"],
            original_frozen_inference_status=status, selection_origin="FROZEN_INFERENCE",
            complete_eligible_candidate_count=len(audit), evaluated_candidate_count=len(evaluated),
            mapped_candidate_count=mapped, unavailable_candidate_count=len(evaluated) - mapped,
            coverage_numerator=mapped, coverage_denominator=denominator,
            coverage_label=f"{mapped}/{denominator}" if denominator is not None else None,
            coverage_state=state, clarification_recommended=self.rules[state]["clarification_recommended"] == "TRUE",
            profile_exposure_summary=None, unavailable_reason=reason, validation_errors=[],
            crosswalk_version=self.contract["crosswalk_container_version"],
            crosswalk_sha256=self.hashes.get("data/automation_onet_crosswalk_v4.csv"),
            interpretation_policy_version=self.contract["contract_version"], candidates=evaluated,
            system_provenance=dict(artifact_paths_and_hashes=self.hashes, validation_status="PASS",
                source_age_and_geography_limitations=self.contract["known_limitations"]),
            future_confirmation={name: None for name in self.contract["manual_confirmation"]["fields"]})
        self.validate_result(result)
        return result

    def validate_result(self, result):
        pid = result["profile_input_id"]
        require(result["coverage_state"] in STATES and result["profile_exposure_summary"] is None,
                "Invalid result state/summary")
        candidates = result["candidates"]
        status = result["original_frozen_inference_status"]
        if status == "INSUFFICIENT_EVIDENCE":
            require(not candidates and result["coverage_denominator"] is None, "INSUFFICIENT lookup")
        elif status == "MULTIPLE_CANDIDATES":
            require({c["modern_soc"] for c in candidates} ==
                    {r["onet_soc_code"] for r in self.candidates[pid]}, "Dropped eligible SOC")
        require(result["mapped_candidate_count"] == sum(c["mapping_available"] for c in candidates),
                "Mapped count mismatch")
        for c in candidates:
            require(len(c["source_records"]) == len(self.edges.get(c["modern_soc"], [])), "Collapsed source records")
            for source in c["source_records"]:
                raw = self.sources[source["historical_source_id"]]["automation_probability"]
                require(source["historical_exposure_value"] == parse_source_value(raw), "Transformed value")
                require(source["semantic_label"] == self.semantics[source["relationship_type"]]["preferred_display_term"],
                        "Relationship interpretation mismatch")

    def evaluate_corpus(self):
        return [self.evaluate_profile(pid) for pid in sorted(self.inference)]


def load_engine(root):
    root = Path(root)
    hashes = {p.as_posix(): sha256(root / p) for p in input_paths()}
    contract = load_contract(root)
    for path, digest in contract["authoritative_artifact_sha256"].items():
        require(sha256(root / path) == digest, f"Authoritative hash mismatch: {path}")
    inference_manifest = read_json(root / FROZEN / "occupation_inference_freeze_manifest.json")
    read_csv(root / FROZEN / "occupation_inference_downstream_contract.csv", ("rule_id", "downstream_handling"))
    inference = read_csv(root / FROZEN / "cv_occupation_inference_frozen_v1_0.csv",
                         ("profile_group_id", "inference_status", "eligible_candidate_count", "top_onet_soc_code"))
    candidates = read_csv(root / FROZEN / "cv_occupation_candidate_audit_frozen_v1_0.csv",
                          ("profile_group_id", "candidate_eligible", "onet_soc_code"))
    crosswalk = read_csv(root / "data/automation_onet_crosswalk_v4.csv",
                         ("mapping_status", "relationship_type", "modern_onet_soc_code", "evidence_source"))
    sources = read_csv(root / "data/automation_probability_labels.csv", ("record_id", "occupation", "automation_probability"))
    provenance = read_csv(root / "data/source_taxonomy_provenance.csv",
                          ("automation_record_id", "automation_occupation", "wocke_taxonomy_status"))
    expected = contract["baseline_coverage_validation"]
    require(len(crosswalk) == expected["crosswalk_rows"], "Crosswalk row count mismatch")
    require(Counter(r["inference_status"] for r in inference) == expected["inference_counts"], "Inference counts mismatch")
    return ExposureEngine(contract, inference, candidates, crosswalk, sources, provenance, inference_manifest, hashes)


def flatten(results):
    profiles, candidates, trace = [], [], []
    for result in results:
        profile = {k: v for k, v in result.items() if k != "candidates"}
        profile.update(profile_id=result["profile_input_id"], inference_status=result["original_frozen_inference_status"],
            exposure_state=result["coverage_state"], eligible_candidate_count=result["complete_eligible_candidate_count"],
            profile_numeric_exposure_summary=None, inference_engine_version=result["inference_version"])
        profiles.append(profile)
        for candidate in result["candidates"]:
            row = dict(profile_id=result["profile_input_id"], inference_status=result["original_frozen_inference_status"], **candidate)
            # Exactly one candidate row; source_records JSON preserves every source.
            single = candidate["source_records"][0] if len(candidate["source_records"]) == 1 else None
            for key in ("relationship_type", "relationship_interpretation", "relationship_limitation",
                        "historical_source_id", "historical_source_title", "historical_exposure_value"):
                row[key] = single[key] if single else None
            row["historical_exposure_semantic_label"] = single["semantic_label"] if single else None
            candidates.append(row)
            for source in candidate["source_records"]:
                trace.append(dict(profile_id=result["profile_input_id"], modern_soc=candidate["modern_soc"],
                    modern_title=candidate["modern_title"], crosswalk_version=result["crosswalk_version"],
                    crosswalk_sha256=result["crosswalk_sha256"], **source))
    return profiles, candidates, trace


def summarize(results, candidates, trace):
    states = Counter(r["coverage_state"] for r in results)
    reasons = Counter(c["unavailable_reason"] for c in candidates if c["unavailable_reason"])
    reasons.update(r["unavailable_reason"] for r in results if r["coverage_state"] == "INSUFFICIENT")
    source_pairs = {(s["modern_soc"], s["historical_source_id"]) for s in trace}
    source_socs = defaultdict(set)
    for soc, sid in source_pairs:
        source_socs[sid].add(soc)
    return dict(total_profiles=len(results),state_counts={s: states[s] for s in STATES},
        evaluated_eligible_candidate_count=len(candidates),
        all_profiles_eligible_audit_candidate_count=sum(r["complete_eligible_candidate_count"] for r in results),
        mapped_candidate_count=sum(c["mapping_available"] for c in candidates),
        unavailable_candidate_count=sum(not c["mapping_available"] for c in candidates),
        distinct_active_lookup_SOCs=len({c["modern_soc"] for c in candidates}),
        distinct_mapped_modern_SOCs=len({c["modern_soc"] for c in candidates if c["mapping_available"]}),
        distinct_historical_sources_reached=len(source_socs),
        relationship_type_counts_candidate_source_rows=dict(Counter(s["relationship_type"] for s in trace)),
        relationship_type_counts_distinct_active_edges=dict(Counter(
            next(s["relationship_type"] for s in trace if (s["modern_soc"], s["historical_source_id"]) == pair)
            for pair in sorted(source_pairs))),
        unavailability_reason_counts=reasons, unavailability_count_unit="Candidate reasons plus profile INSUFFICIENT reasons; no double-counted TOP profile reason.",
        shared_source_count=sum(len(v)>1 for v in source_socs.values()),
        shared_sources={sid: sorted(socs) for sid, socs in sorted(source_socs.items()) if len(socs)>1},
        source_ambiguity_candidate_count=sum(c["source_ambiguity"] for c in candidates),
        source_ambiguity_distinct_SOC_count=len({c["modern_soc"] for c in candidates if c["source_ambiguity"]}),
        insufficient_lookup_count=sum(c.get("lookup_performed", False) for r in results
            if r["original_frozen_inference_status"] == "INSUFFICIENT_EVIDENCE" for c in r["candidates"]),
        profile_numeric_summary_non_null_count=sum(r["profile_exposure_summary"] is not None for r in results),
        accuracy_claim=False, personal_risk_metric=False, deterministic_lookup_only=True)


def write_csv(path, rows):
    require(rows, f"No rows for {path}")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if
                value is None or isinstance(value, (dict, list, bool)) else value for key, value in row.items()})


def write_json(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        stream.write("\n")


def build(root):
    root = Path(root)
    before = {p.as_posix(): sha256(root / p) for p in input_paths()}
    engine = load_engine(root)
    results = engine.evaluate_corpus()
    require(results == engine.evaluate_corpus(), "Nondeterministic evaluation")
    profiles, candidates, trace = flatten(results)
    summary = summarize(results, candidates, trace)
    audits = []
    tree = ast.parse((root / "scripts/automation_exposure_integration.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module.split(".")[0])
    permitted_imports = {"__future__", "argparse", "ast", "csv", "hashlib", "json", "math",
                         "platform", "collections", "pathlib"}
    forbidden_dependencies = imports - permitted_imports
    def check(key, expected, actual, notes=""):
        audits.append(dict(check_id=key, expected=expected, actual=actual,
                           status="PASS" if expected == actual else "FAIL", notes=notes))
        require(expected == actual, f"{key}: expected {expected}, got {actual}")
    for key, value in [("PROFILE_COUNT_344",len(profiles)), ("STATE_TOTAL_344",sum(summary["state_counts"].values()))]:
        check(key,344,value)
    for name,count in [("TOP",35),("MULTIPLE",146),("INSUFFICIENT",163)]:
        check(f"{name}_COUNT_{count}",count,sum(r["original_frozen_inference_status"].startswith(name) for r in results))
    for key in ["INSUFFICIENT_LOOKUP_COUNT_ZERO", "MULTIPLE_PROFILE_SUMMARY_NON_NULL_COUNT_ZERO",
                "MULTIPLE_RANK1_SELECTION_COUNT_ZERO", "NON_STDLIB_DEPENDENCY_IMPORT_COUNT_ZERO",
                "SOURCE_VALUE_TRANSFORMATION_COUNT_ZERO", "UNMAPPED_NUMERIC_FALLBACK_COUNT_ZERO",
                "INVALID_SOURCE_NUMERIC_FALLBACK_COUNT_ZERO"]:
        if key.startswith("INSUFFICIENT"):
            actual = summary["insufficient_lookup_count"]
        elif "SUMMARY" in key:
            actual = summary["profile_numeric_summary_non_null_count"]
        elif "RANK1" in key:
            actual = sum(len(r["candidates"]) != len(engine.candidates[r["profile_input_id"]])
                         for r in results if r["coverage_state"].startswith("MULTIPLE"))
        elif "TRANSFORMATION" in key:
            actual = sum(s["historical_exposure_value"] != parse_source_value(
                engine.sources[s["historical_source_id"]]["automation_probability"]) for s in trace)
        elif "UNMAPPED" in key:
            actual = sum(c["historical_exposure_value"] is not None for c in candidates if not c["mapping_available"])
        elif "INVALID" in key:
            actual = sum(s["historical_exposure_value"] is not None for s in trace if not s["value_available"])
        else:
            actual = len(forbidden_dependencies)
        check(key,0,actual,"Static AST import allowlist only; not a universal runtime-reference detector. Model/application dependencies are forbidden." if "DEPENDENCY_IMPORT" in key else "")
    check("V4_ROW_COUNT_323",323,len(engine.crosswalk))
    reference = read_csv(root / BASE / "step7a7/profile_exposure_coverage_audit_v4.csv")
    mapping = {"FULL_EXPOSURE_PATH": {"TOP_MAPPED","MULTIPLE_ALL_MAPPED"},
        "PARTIAL_EXPOSURE_PATH":{"MULTIPLE_PARTIAL"},"NO_FROZEN_CROSSWALK":{"TOP_UNMAPPED","MULTIPLE_NONE_MAPPED"},
        "NOT_APPLICABLE_INFERENCE_INSUFFICIENT":{"INSUFFICIENT"}}
    byid = {r["profile_input_id"]:r for r in results}
    check("COVERAGE_REPRODUCTION",True,all(byid[r["profile_group_id"]]["coverage_state"] in mapping[r["coverage_status"]] for r in reference))
    priorpaths = read_csv(root / BASE / "step7a7/soc_exposure_path_audit_v4.csv")
    current = {(s["profile_id"],s["modern_soc"],s["historical_source_id"],s["historical_exposure_raw"]) for s in trace}
    previous = {(r["profile_group_id"],r["onet_soc_code"],r["source_record_id"],r["automation_probability"])
                for r in priorpaths if r["source_record_id"]}
    check("EXACT_SOURCE_PATH_REPRODUCTION",previous,current)
    # Replace potentially verbose set diagnostics with stable count semantics.
    audits[-1].update(expected=len(previous),actual=len(current))
    read_csv(root / BASE / "step7a7/unique_soc_exposure_coverage_v4.csv")
    read_json(root / BASE / "step7a7/exposure_coverage_summary_v4.json")
    read_json(root / BASE / "step7a7/crosswalk_v4_freeze_manifest.json")
    read_json(root / BASE / "step7a7/crosswalk_expansion_stopping_rule_v1.json")
    for name,actual in [("SHARED_SOURCE_IDENTITY_PRESERVED",all(s["shared_with_modern_socs"] == sorted(engine.shared[s["historical_source_id"]]-{s["modern_soc"]}) for s in trace)),
        ("MULTI_SOURCE_SOC_NOT_SILENTLY_COLLAPSED",all(c["source_record_count"]==len(engine.edges.get(c["modern_soc"],[])) for c in candidates)),
        ("RELATIONSHIP_SEMANTICS_PRESENT",all(s["semantic_label"]==engine.semantics[s["relationship_type"]]["preferred_display_term"] for s in trace)),
        ("STATIC_LEGACY_RISK_DEPENDENCY_ABSENT",not forbidden_dependencies),
        ("STATIC_SKILL_GAP_DEPENDENCY_ABSENT",not forbidden_dependencies)]:
        check(name,True,actual,"Static import allowlist assurance; computational isolation also exercised by regression tests." if name.startswith("STATIC_") else "")
    after = {p:sha256(root / p) for p in before}
    check("INPUT_HASH_INTEGRITY",before,after)
    audits[-1].update(expected="UNCHANGED",actual="UNCHANGED")
    destination = root / BASE / "step7b2"
    require(not destination.exists(), "Output directory already exists; refusing overwrite")
    destination.mkdir()
    files = {"profile_historical_exposure_results_v1.csv":profiles,
        "candidate_historical_exposure_results_v1.csv":candidates,
        "historical_exposure_source_trace_v1.csv":trace,
        "historical_exposure_validation_audit_v1.csv":audits}
    for name,rows in files.items():write_csv(destination/name,rows)
    write_json(destination/"historical_exposure_state_summary_v1.json",summary)
    for name,rows in files.items():require(len(read_csv(destination/name))==len(rows),"Output reread count mismatch")
    read_json(destination/"historical_exposure_state_summary_v1.json")
    require(before=={p:sha256(root/p) for p in before},"Inputs changed during output generation")
    manifest = dict(task="STEP_7B_2",version=VERSION,engine_path="scripts/automation_exposure_integration.py",
        engine_sha256=sha256(root/"scripts/automation_exposure_integration.py"),
        test_path="tests/test_automation_exposure_integration.py",
        test_sha256=sha256(root/"tests/test_automation_exposure_integration.py"),
        tests_command="python -B -m unittest discover -s tests -p test_automation_exposure_integration.py -v",
        tests_execution="Run separately before build; build does not execute tests or invent a test run result.",
        input_sha256_before=before,input_sha256_after=after,
        step7b1_contract_hashes={p:h for p,h in before.items() if "step7b1/" in p},
        output_sha256={p.name:sha256(p) for p in sorted(destination.iterdir())},
        output_hash_scope="Five companion outputs; self-hash omitted to avoid circular digest.",
        runtime=dict(python=platform.python_version(),dependencies="Python standard library only"),
        output_row_counts={name:len(rows) for name,rows in files.items()},summary=summary,
        candidate_schema="One row per evaluated eligible SOC; nested source_records JSON retains all source edges. Convenience source scalar columns are null when multiple sources. Source trace has one row per frozen candidate-source path.",
        csv_null_encoding="Literal JSON null; booleans and nested objects/arrays serialized as JSON.",
        known_limitations=engine.contract["known_limitations"],deterministic_lookup_only=True,
        ML_or_RF_used=False,aggregation=False,personal_job_loss_probability=False,skill_gap_scoring=False,
        flask_integration=False,legacy_risk_used=False,coverage_reproduction="PASS",input_integrity="PASS",
        readiness="READY_FOR_STEP_7B_2_INDEPENDENT_AUDIT")
    write_json(destination/"step7b2_build_manifest.json",manifest)
    read_json(destination/"step7b2_build_manifest.json")
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    response = validation_boundary(build, args.root, context=dict(operation="build", root=str(args.root)))
    if response.get("validation_status") == "ERROR":
        parser.exit(1, json.dumps(response, sort_keys=True) + "\n")
    print(json.dumps(response,indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
