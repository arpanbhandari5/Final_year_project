#!/usr/bin/env python3
"""Validate Round-1 worksheet readiness. Does not fill scores or train models."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_human_task_exposure_gate import TRAINABLE, main as gate_main
from human_dataset_common import (
    ALLOWED_CONFIDENCE,
    ALLOWED_SCORES,
    FORBIDDEN_REVIEWER_IDS,
    REVIEWER_SLOT_IDS,
    ROUND1_IDENTITY_LOCK,
    ROUND1_REVIEWER1,
    ROUND1_REVIEWER2,
    ROUND1_SAMPLE,
    ROUND1_THIRD,
    WORKSHEET_IDENTITY_FIELDS,
    classify_score_cell,
    confidence_is_allowed,
    count_filled_scores,
    identity_fingerprint,
    is_blank_cell,
)

SHEETS = {
    "1": ROUND1_REVIEWER1,
    "2": ROUND1_REVIEWER2,
    "3": ROUND1_THIRD,
}


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def check_sheet(slot: str, lock: dict) -> dict:
    path = SHEETS[slot]
    frame = load_csv(path)
    expected_id = REVIEWER_SLOT_IDS[slot]
    errors = []
    ids = set(frame["reviewer_id"].astype(str).str.strip())
    if ids != {expected_id}:
        errors.append(f"{path.name} reviewer_id set {sorted(ids)} != {{{expected_id}}}")
    if ids & FORBIDDEN_REVIEWER_IDS:
        errors.append(f"{path.name} uses a forbidden reviewer_id")
    if "soc_code" not in frame.columns:
        errors.append(f"{path.name} missing soc_code")
    for field in WORKSHEET_IDENTITY_FIELDS:
        if field not in frame.columns:
            errors.append(f"{path.name} missing identity field {field}")
    lock_key = {"1": "reviewer1", "2": "reviewer2", "3": "third_reviewer"}[slot]
    expected_order = lock[f"{lock_key}_task_id_order"]
    actual_order = frame["task_id"].astype(str).tolist()
    if actual_order != expected_order:
        errors.append(f"{path.name} task_id order does not match identity lock")
    if identity_fingerprint(frame) != lock[f"{lock_key}_identity_sha256"]:
        errors.append(f"{path.name} identity fingerprint does not match lock")
    if frame["task_id"].duplicated().any():
        errors.append(f"{path.name} has duplicate task_id")
    n_score = count_filled_scores(frame["reviewer_score"])
    n_conf = count_filled_scores(frame["reviewer_confidence"])
    statuses = [
        classify_score_cell(score, notes)
        for score, notes in zip(frame["reviewer_score"], frame["reviewer_notes"])
    ]
    if any(not confidence_is_allowed(value) for value in frame["reviewer_confidence"]):
        errors.append(f"{path.name} has confidence outside {ALLOWED_CONFIDENCE} (blank still allowed)")
    return {
        "file": path.name,
        "rows": int(len(frame)),
        "reviewer_id": expected_id,
        "filled_reviewer_scores": n_score,
        "filled_confidence": n_conf,
        "score_status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
        "errors": errors,
    }


def check_sample(lock: dict) -> dict:
    sample = load_csv(ROUND1_SAMPLE)
    errors = []
    if sample["task_id"].astype(str).tolist() != lock["sample_task_id_order"]:
        errors.append("sample task_id order does not match identity lock")
    if identity_fingerprint(sample) != lock["sample_identity_sha256"]:
        errors.append("sample identity fingerprint does not match lock")
    for field in ("reviewer_1_score", "reviewer_2_score", "third_reviewer_score", "adjudicated_exposure_score"):
        if field not in sample.columns:
            errors.append(f"sample missing {field}")
            continue
        filled = count_filled_scores(sample[field])
        if filled != 0:
            errors.append(f"sample {field} filled={filled}")
    if "third_reviewer_score" in sample.columns and "adjudicated_exposure_score" in sample.columns:
        if list(sample.columns).count("third_reviewer_score") != 1:
            errors.append("third_reviewer_score is not a distinct column")
        if "third_reviewer_score" not in sample.columns or "adjudicated_exposure_score" not in sample.columns:
            errors.append("missing third_reviewer_score or adjudicated_exposure_score")
    return {
        "filled_reviewer_1": count_filled_scores(sample.get("reviewer_1_score", pd.Series(dtype=str))),
        "filled_reviewer_2": count_filled_scores(sample.get("reviewer_2_score", pd.Series(dtype=str))),
        "filled_third_reviewer_score": count_filled_scores(
            sample.get("third_reviewer_score", pd.Series(dtype=str))
        ),
        "filled_adjudicated": count_filled_scores(
            sample.get("adjudicated_exposure_score", pd.Series(dtype=str))
        ),
        "distinct_score_fields": True,
        "errors": errors,
    }


def main() -> int:
    lock = json.loads(ROUND1_IDENTITY_LOCK.read_text(encoding="utf-8"))
    sheet_reports = [check_sheet(slot, lock) for slot in ("1", "2", "3")]
    sample_report = check_sample(lock)
    gate_code = gate_main()
    errors = [item for report in sheet_reports for item in report["errors"]]
    errors.extend(sample_report["errors"])
    human_scores = sum(report["filled_reviewer_scores"] for report in sheet_reports)
    report = {
        "allowed_scores": list(ALLOWED_SCORES),
        "allowed_confidence": list(ALLOWED_CONFIDENCE),
        "human_reviewer_scores": human_scores,
        "adjudicated_human_scores": sample_report["filled_adjudicated"],
        "gate_exit_code": gate_code,
        "gate_refuses_training": gate_code == 2,
        "trainable_exists": TRAINABLE.exists(),
        "sheets": sheet_reports,
        "sample": sample_report,
        "errors": errors,
        "ready_for_reviewers": not errors and human_scores == 0 and sample_report["filled_adjudicated"] == 0,
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
