"""Tests for the isolated GPTs-are-GPTs public-benchmark experiment."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "task_exposure"))

from evaluate_public_gpts_benchmark import (  # noqa: E402
    CLASSES,
    classification_metrics,
    make_logreg,
    make_tfidf,
)
from public_benchmark_common import (  # noqa: E402
    ALLOWED_HUMAN_LABELS,
    DERIVED_CSV,
    GPT_FIELDS,
    RAW_LABELSET,
    TARGET_FIELD,
    TEXT_COLUMN,
    PublicBenchmarkError,
    load_raw_labelset,
    occupation_grouped_splits,
    standardize_source,
    text_features_exclude_targets,
    validate_human_labels,
    verify_group_disjoint,
)


def test_source_schema_and_human_labels():
    raw = load_raw_labelset(RAW_LABELSET)
    for column in (
        "O*NET-SOC Code",
        "Task ID",
        "Task",
        "human_labels",
        "human_exposure_agg",
        *GPT_FIELDS,
    ):
        assert column in raw.columns
    frame = standardize_source(raw)
    info = validate_human_labels(frame)
    assert info["invalid_labels"] == []
    assert set(info["observed_labels"]).issubset(set(ALLOWED_HUMAN_LABELS))
    assert info["e3_in_human_labels"] == 0
    assert info["non_empty_human_labels"] == info["rows"] - info["missing_human_labels"]


def test_human_and_gpt_fields_remain_separate():
    raw = load_raw_labelset(RAW_LABELSET)
    frame = standardize_source(raw)
    assert TARGET_FIELD in frame.columns
    for field in GPT_FIELDS:
        assert field in frame.columns
        assert field != TARGET_FIELD
    mismatch = int((frame[TARGET_FIELD] != frame["gpt4_exposure"]).sum())
    assert mismatch > 0


def test_duplicate_and_missing_detection():
    raw = load_raw_labelset(RAW_LABELSET)
    frame = standardize_source(raw)
    occ_task = frame["occupation_code"] + "|" + frame["task_id"]
    assert int(occ_task.duplicated().sum()) == 0
    missing = int((frame[TARGET_FIELD].str.strip() == "").sum())
    assert missing == 0


def test_occupation_grouped_zero_overlap():
    mapping, counts = occupation_grouped_splits([f"occ-{i}" for i in range(40)], seed=7)
    by = {}
    for occ, split in mapping.items():
        by.setdefault(split, set()).add(occ)
    assert by["train"].isdisjoint(by["validation"])
    assert by["train"].isdisjoint(by["test"])
    assert by["validation"].isdisjoint(by["test"])
    assert counts["overlap"]["train_validation"] == []
    assert counts["overlap"]["train_test"] == []
    assert counts["overlap"]["validation_test"] == []
    verify_group_disjoint(np.array(list(by["train"])), np.array(list(by["test"])))


def test_verify_group_disjoint_raises():
    try:
        verify_group_disjoint(np.array(["a", "b"]), np.array(["b", "c"]))
    except PublicBenchmarkError:
        return
    raise AssertionError("overlap must raise")


def test_no_target_leakage_in_feature_contract():
    text_features_exclude_targets([TEXT_COLUMN])
    try:
        text_features_exclude_targets([TEXT_COLUMN, TARGET_FIELD])
    except PublicBenchmarkError:
        return
    raise AssertionError("target column must be rejected")


def test_tfidf_fitted_only_on_train_texts():
    train = ["alpha clerical filing unique_train_token_xyz", "alpha report writing"]
    test = ["heldout_leak_token_zzz should not enter vocabulary"]
    vectorizer = make_tfidf()
    vectorizer.fit(train)
    assert "unique_train_token_xyz" in vectorizer.vocabulary_
    assert "heldout_leak_token_zzz" not in vectorizer.vocabulary_


def test_model_output_classes_and_pipeline():
    texts = np.array(
        [
            "write software documentation",
            "operate welding machinery",
            "build llm powered dashboard",
            "lift physical freight",
            "summarize meeting notes",
            "pour concrete foundation",
        ]
    )
    y = np.array(["E1", "E0", "E2", "E0", "E1", "E0"])
    model = make_logreg(1.0)
    assert isinstance(model, Pipeline)
    model.fit(texts, y)
    pred = model.predict(texts)
    assert set(pred).issubset(set(CLASSES))
    assert set(model.named_steps["clf"].classes_).issubset(set(CLASSES))


def test_metric_calculation():
    y_true = np.array(["E0", "E0", "E1", "E2"])
    y_pred = np.array(["E0", "E1", "E1", "E2"])
    metrics = classification_metrics(y_true, y_pred)
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert metrics["per_class"]["E0"]["support"] == 2
    assert metrics["confusion_matrix"][0][0] == 1
    assert metrics["log_loss"]["status"] == "unavailable"


def test_split_reproducibility():
    occ = [f"11-{i:04d}.00" for i in range(30)]
    a, _ = occupation_grouped_splits(occ, seed=202610031)
    b, _ = occupation_grouped_splits(occ, seed=202610031)
    assert a == b


def test_derived_table_keeps_gpt_columns_out_of_target():
    if not DERIVED_CSV.exists():
        return
    frame = pd.read_csv(DERIVED_CSV, dtype=str, keep_default_na=False)
    assert TARGET_FIELD in frame.columns
    assert set(frame[TARGET_FIELD].unique()).issubset(set(ALLOWED_HUMAN_LABELS))
    for field in GPT_FIELDS:
        assert field in frame.columns
