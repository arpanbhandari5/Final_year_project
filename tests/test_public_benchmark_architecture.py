"""Architecture tests for the 923-occupation research model vs 800 product subset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "task_exposure"))

from product_copy import (  # noqa: E402
    CAREER_ACTION_DISCLAIMER,
    CAREER_ACTIONS,
    CLASSES,
    MODEL_ID,
    OCCUPATION_COPY,
    PRODUCTION_STATUS,
    PROVENANCE_SHORT,
    RESUME_COPY,
    TASK_ANALYSIS_COPY,
)
from public_benchmark_common import (  # noqa: E402
    DERIVED_CSV,
    GPT_FIELDS,
    OCC_MASTER_800,
    REPORT_DIR,
    TARGET_FIELD,
    sha256_file,
)

SPLIT = REPORT_DIR / "split_manifest.json"
IDENTITY = REPORT_DIR / "model_identity.json"


def test_benchmark_row_and_occupation_counts():
    frame = pd.read_csv(DERIVED_CSV, dtype=str, keep_default_na=False)
    assert len(frame) == 19265
    assert frame["occupation_code"].nunique() == 923
    assert set(frame[TARGET_FIELD].unique()) == set(CLASSES)


def test_split_occupations_disjoint_and_sum_to_923():
    payload = json.loads(SPLIT.read_text(encoding="utf-8"))
    train = set(payload["train_occupations_list"])
    val = set(payload["validation_occupations_list"])
    test = set(payload["test_occupations_list"])
    assert len(train) == 646
    assert len(val) == 138
    assert len(test) == 139
    assert len(train | val | test) == 923
    assert train.isdisjoint(val)
    assert train.isdisjoint(test)
    assert val.isdisjoint(test)
    assert payload["train_tasks"] == 13453
    assert payload["validation_tasks"] == 2941
    assert payload["test_tasks"] == 2871
    assert payload["train_validation_overlap"] == []
    assert payload["train_test_overlap"] == []
    assert payload["validation_test_overlap"] == []


def test_human_labels_not_gpt_and_not_five_level():
    frame = pd.read_csv(DERIVED_CSV, dtype=str, keep_default_na=False)
    assert TARGET_FIELD == "human_labels"
    for field in GPT_FIELDS:
        assert field in frame.columns
        assert not frame[TARGET_FIELD].equals(frame[field])
    assert not set(frame[TARGET_FIELD]).intersection({"0.00", "0.25", "0.50", "0.75", "1.00", "0", "1"})


def test_provenance_distinguishes_prayash_review():
    assert "human-derived exposure labels" in PROVENANCE_SHORT
    assert "Prayash created human-validated labels" not in PROVENANCE_SHORT
    identity = json.loads(IDENTITY.read_text(encoding="utf-8"))
    assert identity["model_id"] == MODEL_ID
    assert identity["production_integrated"] is False
    assert identity["product_subset_used_for_training"] is False


def test_800_subset_separate_from_923_model():
    selected = pd.read_csv(OCC_MASTER_800, dtype=str, keep_default_na=False)
    bench = pd.read_csv(DERIVED_CSV, dtype=str, keep_default_na=False)
    assert len(selected) == 800
    assert selected["occupation_code"].nunique() == 800
    bench_occ = set(bench["occupation_code"])
    product_occ = set(selected["occupation_code"])
    assert product_occ.issubset(bench_occ)
    assert len(bench_occ - product_occ) == 123
    identity = json.loads(IDENTITY.read_text(encoding="utf-8"))
    assert identity["training_population"].startswith("923 occupations")
    assert sha256_file(OCC_MASTER_800)


def test_safety_copy_has_no_prohibited_claims():
    blobs = [
        TASK_ANALYSIS_COPY,
        OCCUPATION_COPY,
        RESUME_COPY,
        CAREER_ACTION_DISCLAIMER,
        " ".join(CAREER_ACTIONS),
    ]
    combined = " ".join(blobs).lower()
    for phrase in ("ai-proof job", "safe job", "unsafe job", "chance of unemployment"):
        assert phrase not in combined
    assert "not a prediction of personal job loss" in combined
    assert "does not estimate your personal" in combined
    assert "not predictions derived from an individual's probability of job loss" in combined
    assert PRODUCTION_STATUS == "research-only"
