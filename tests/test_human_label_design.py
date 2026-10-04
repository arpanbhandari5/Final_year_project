"""Synthetic checks for human-track sampling helpers. Does not touch production labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "data_pipeline"))

from human_dataset_common import (  # noqa: E402
    ALLOWED_CONFIDENCE,
    ALLOWED_SCORES,
    FORBIDDEN_REVIEWER_IDS,
    REVIEWER_SLOT_IDS,
    ROUND1_IDENTITY_LOCK,
    ROUND1_REVIEWER1,
    ROUND1_REVIEWER2,
    ROUND1_SAMPLE,
    ROUND1_THIRD,
    blank_human_score_columns,
    classify_score_cell,
    confidence_is_allowed,
    count_filled_scores,
    identity_fingerprint,
    occupation_grouped_splits,
)
from validate_human_round1_readiness import check_sample, check_sheet  # noqa: E402


def test_occupation_splits_disjoint():
    mapping, counts = occupation_grouped_splits([f"occ-{i}" for i in range(20)], seed=1)
    by = {}
    for occ, split in mapping.items():
        by.setdefault(split, set()).add(occ)
    assert not (by["train"] & by["validation"])
    assert not (by["train"] & by["test"])
    assert not (by["validation"] & by["test"])
    assert sum(counts.values()) == 20


def test_blank_scores_not_zero():
    frame = pd.DataFrame({"task_id": ["1"], "occupation_code": ["11-1011.00"], "task_text": ["Do a task."]})
    out = blank_human_score_columns(frame)
    assert str(out.loc[0, "reviewer_1_score"]).strip() == ""
    assert str(out.loc[0, "third_reviewer_score"]).strip() == ""
    assert str(out.loc[0, "adjudicated_exposure_score"]).strip() == ""
    assert str(out.loc[0, "adjudicated_exposure_score"]) != "0.00"
    assert out.loc[0, "not_human_ground_truth"] == "true"


def test_score_status_and_confidence_constraints():
    assert classify_score_cell("") == "blank"
    assert classify_score_cell("0.00") == "valid_score"
    assert classify_score_cell("0.25") == "valid_score"
    assert classify_score_cell("0.50") == "valid_score"
    assert classify_score_cell("0.75") == "valid_score"
    assert classify_score_cell("1.00") == "valid_score"
    assert classify_score_cell("0.3") == "invalid_score"
    assert classify_score_cell("", "not_scorable") == "not_scorable"
    assert classify_score_cell("", "unresolved") == "unresolved"
    assert ALLOWED_SCORES == (0.00, 0.25, 0.50, 0.75, 1.00)
    assert ALLOWED_CONFIDENCE == ("high", "medium", "low")
    assert confidence_is_allowed("")
    assert confidence_is_allowed("high")
    assert not confidence_is_allowed("High")
    assert not confidence_is_allowed("1")
    assert "AI_1" in FORBIDDEN_REVIEWER_IDS


def test_third_reviewer_score_distinct_from_adjudicated():
    sample = pd.read_csv(ROUND1_SAMPLE, dtype=str, keep_default_na=False)
    assert "third_reviewer_score" in sample.columns
    assert "adjudicated_exposure_score" in sample.columns
    assert list(sample.columns).index("third_reviewer_score") != list(sample.columns).index(
        "adjudicated_exposure_score"
    )
    assert count_filled_scores(sample["third_reviewer_score"]) == 0
    assert count_filled_scores(sample["adjudicated_exposure_score"]) == 0


def test_round1_readiness_worksheets():
    lock = json.loads(ROUND1_IDENTITY_LOCK.read_text(encoding="utf-8"))
    reports = [check_sheet(slot, lock) for slot in ("1", "2", "3")]
    assert REVIEWER_SLOT_IDS == {
        "1": "HUMAN_REVIEWER_A",
        "2": "HUMAN_REVIEWER_B",
        "3": "HUMAN_REVIEWER_C",
    }
    for report in reports:
        assert report["errors"] == []
        assert report["filled_reviewer_scores"] == 0
        assert report["filled_confidence"] == 0
    sample_report = check_sample(lock)
    assert sample_report["errors"] == []
    assert sample_report["filled_adjudicated"] == 0
    r1 = pd.read_csv(ROUND1_REVIEWER1, dtype=str, keep_default_na=False)
    r2 = pd.read_csv(ROUND1_REVIEWER2, dtype=str, keep_default_na=False)
    r3 = pd.read_csv(ROUND1_THIRD, dtype=str, keep_default_na=False)
    assert set(r1["reviewer_id"]) == {"HUMAN_REVIEWER_A"}
    assert set(r2["reviewer_id"]) == {"HUMAN_REVIEWER_B"}
    assert set(r3["reviewer_id"]) == {"HUMAN_REVIEWER_C"}
    assert identity_fingerprint(r1) == lock["reviewer1_identity_sha256"]
    assert identity_fingerprint(r2) == lock["reviewer2_identity_sha256"]
    assert identity_fingerprint(r3) == lock["third_reviewer_identity_sha256"]
    assert len(r1) == 300
    assert len(r2) == 300
    assert len(r3) == 60
    human_scores = sum(count_filled_scores(frame["reviewer_score"]) for frame in (r1, r2, r3))
    assert human_scores == 0
