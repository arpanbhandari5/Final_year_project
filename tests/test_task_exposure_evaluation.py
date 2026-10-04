"""Focused tests for the isolated task-exposure evaluator.

Fixtures are temporary/in-memory only. The real training CSV is never rewritten.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "task_exposure"))

from evaluate_task_exposure import (  # noqa: E402
    ALPHA_CANDIDATES,
    TEXT_COLUMN,
    DatasetValidationError,
    build_pipeline,
    evaluate_and_write,
    load_and_validate_dataset,
    run_grouped_evaluation,
    safe_r2,
    select_alpha_grouped,
    verify_group_disjoint,
)


def _write_table(path: Path, rows: list[dict]) -> Path:
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False)
    return path


def _row(task_id, occupation, text, score, **extra):
    row = {
        "task_id": task_id,
        "occupation_code": occupation,
        "task_text": text,
        "adjudicated_exposure_score": score,
        "not_human_ground_truth": True,
        "label_source": "provisional_ai_weak_supervision",
        "resolution_method": "identical_scores",
    }
    row.update(extra)
    return row


def _balanced_rows(n_occupations: int = 10, scores=None) -> list[dict]:
    scores = scores or [0.00, 0.25, 0.50, 0.75, 1.00]
    rows = []
    for i in range(n_occupations):
        occ = f"99-{i:04d}.00"
        score = scores[i % len(scores)]
        rows.append(
            _row(
                f"t{i}",
                occ,
                f"Perform documented clerical task number {i} with unique tokens tok{i}",
                score,
            )
        )
    return rows


def test_required_column_validation(tmp_path: Path):
    path = tmp_path / "missing.csv"
    pd.DataFrame(
        {
            "task_id": ["a"],
            "occupation_code": ["11-0000.00"],
            "task_text": ["Do a task."],
            "not_human_ground_truth": [True],
            "label_source": ["provisional_ai_weak_supervision"],
            "resolution_method": ["identical_scores"],
        }
    ).to_csv(path, index=False)
    with pytest.raises(DatasetValidationError, match="Missing required columns"):
        load_and_validate_dataset(path, n_splits=2)


def test_invalid_target_values_rejected(tmp_path: Path):
    path = _write_table(
        tmp_path / "bad_target.csv",
        [
            _row("1", "11-0000.00", "Alpha task statement here", 0.30),
            _row("2", "13-0000.00", "Beta task statement here", 0.00),
        ],
    )
    with pytest.raises(DatasetValidationError, match="outside the allowed set"):
        load_and_validate_dataset(path, n_splits=2)


def test_duplicate_task_ids_rejected(tmp_path: Path):
    path = _write_table(
        tmp_path / "dup.csv",
        [
            _row("same", "11-0000.00", "Alpha task statement here", 0.00),
            _row("same", "13-0000.00", "Beta task statement here", 0.25),
        ],
    )
    with pytest.raises(DatasetValidationError, match="not unique"):
        load_and_validate_dataset(path, n_splits=2)


def test_empty_task_text_rejected(tmp_path: Path):
    path = _write_table(
        tmp_path / "empty_text.csv",
        [
            _row("1", "11-0000.00", "   ", 0.00),
            _row("2", "13-0000.00", "Beta task statement here", 0.25),
        ],
    )
    with pytest.raises(DatasetValidationError, match="empty or whitespace-only"):
        load_and_validate_dataset(path, n_splits=2)


def test_numeric_target_conversion_raises(tmp_path: Path):
    path = _write_table(
        tmp_path / "non_numeric.csv",
        [
            _row("1", "11-0000.00", "Alpha task statement here", "not-a-number"),
            _row("2", "13-0000.00", "Beta task statement here", "0.00"),
        ],
    )
    with pytest.raises(DatasetValidationError, match="errors='raise'"):
        load_and_validate_dataset(path, n_splits=2)


def test_not_human_ground_truth_must_be_true(tmp_path: Path):
    path = _write_table(
        tmp_path / "human_flag.csv",
        [
            _row("1", "11-0000.00", "Alpha task statement here", 0.00, not_human_ground_truth=False),
            _row("2", "13-0000.00", "Beta task statement here", 0.25),
        ],
    )
    with pytest.raises(DatasetValidationError, match="not_human_ground_truth"):
        load_and_validate_dataset(path, n_splits=2)


def test_r2_constant_target_returns_none_not_zero():
    y_true = np.array([0.50, 0.50, 0.50])
    y_pred = np.array([0.10, 0.20, 0.90])
    value, warning = safe_r2(y_true, y_pred)
    assert value is None
    assert warning is not None
    assert "constant" in warning.lower()
    assert value != 0


def test_outer_and_inner_groups_never_overlap(tmp_path: Path):
    path = _write_table(tmp_path / "ok.csv", _balanced_rows(10))
    validated = load_and_validate_dataset(path, n_splits=5)
    report = run_grouped_evaluation(validated, n_splits=5)
    for fold in report["folds"]:
        assert fold["occupation_intersection"] == []
        train = set(fold["train_occupation_codes"])
        test = set(fold["test_occupation_codes"])
        assert train.isdisjoint(test)
        assert fold["inner_split_count"] >= 2

    texts = validated.frame[TEXT_COLUMN].astype(str).to_numpy()
    y = validated.frame["adjudicated_exposure_score"].to_numpy(dtype=float)
    groups = validated.frame["occupation_code"].astype(str).to_numpy()
    train_idx = [
        i
        for i, occ in enumerate(groups)
        if occ in set(report["folds"][0]["train_occupation_codes"])
    ]
    select_alpha_grouped(
        texts[train_idx],
        y[train_idx],
        groups[train_idx],
        alphas=[1.0, 10.0],
        inner_splits=2,
    )


def test_verify_group_disjoint_raises_on_overlap():
    with pytest.raises(RuntimeError, match="overlap"):
        verify_group_disjoint(
            np.array(["a", "b"]),
            np.array(["b", "c"]),
            context="unit",
        )


def test_tfidf_fitted_only_through_pipeline(tmp_path: Path, monkeypatch):
    path = _write_table(tmp_path / "ok.csv", _balanced_rows(10))
    validated = load_and_validate_dataset(path, n_splits=5)
    pipeline = build_pipeline(1.0)
    assert isinstance(pipeline, Pipeline)
    assert list(pipeline.named_steps) == ["tfidf", "model"]

    fit_sizes: list[int] = []
    original_fit_transform = TfidfVectorizer.fit_transform
    original_fit = TfidfVectorizer.fit

    def _size(X) -> int:
        return int(getattr(X, "shape", [len(X)])[0] if hasattr(X, "shape") else len(X))

    def tracking_fit_transform(self, raw_documents, y=None):
        fit_sizes.append(_size(raw_documents))
        return original_fit_transform(self, raw_documents, y)

    def tracking_fit(self, raw_documents, y=None):
        fit_sizes.append(_size(raw_documents))
        return original_fit(self, raw_documents, y)

    monkeypatch.setattr(TfidfVectorizer, "fit_transform", tracking_fit_transform)
    monkeypatch.setattr(TfidfVectorizer, "fit", tracking_fit)
    run_grouped_evaluation(validated, n_splits=5, alphas=[1.0, 10.0])
    n_rows = validated.summary["dataset_row_count"]
    assert fit_sizes
    assert all(size < n_rows for size in fit_sizes)


def test_mean_and_median_baselines_use_training_fold_only(tmp_path: Path):
    rows = []
    for i in range(6):
        rows.append(
            _row(
                f"low{i}",
                f"10-{i:04d}.00",
                f"Low exposure wording unique {i} alpha",
                0.00,
            )
        )
    for i in range(6):
        rows.append(
            _row(
                f"high{i}",
                f"20-{i:04d}.00",
                f"High exposure wording unique {i} beta",
                1.00,
            )
        )
    path = _write_table(tmp_path / "base.csv", rows)
    validated = load_and_validate_dataset(path, n_splits=2)
    frame = validated.frame
    y = frame["adjudicated_exposure_score"].to_numpy(dtype=float)
    groups = frame["occupation_code"].astype(str).to_numpy()
    report = run_grouped_evaluation(validated, n_splits=2, alphas=[1.0])
    for fold in report["folds"]:
        train_mask = np.isin(groups, fold["train_occupation_codes"])
        expected_mean = float(np.mean(y[train_mask]))
        expected_median = float(np.median(y[train_mask]))
        assert fold["baseline_training_mean"] == pytest.approx(expected_mean)
        assert fold["baseline_training_median"] == pytest.approx(expected_median)


def test_mean_baseline_ignores_held_out_targets(tmp_path: Path):
    rows = []
    for i in range(3):
        rows.append(_row(f"a{i}", "occ-A", f"group a statement {i} word", 0.00))
        rows.append(_row(f"b{i}", "occ-B", f"group b statement {i} word", 0.00))
        rows.append(_row(f"c{i}", "occ-C", f"group c statement {i} word", 1.00))
    path = _write_table(tmp_path / "split.csv", rows)
    validated = load_and_validate_dataset(path, n_splits=3)
    report = run_grouped_evaluation(validated, n_splits=3, alphas=[1.0])
    found_zero_train = False
    for fold in report["folds"]:
        if fold["test_occupation_codes"] == ["occ-C"]:
            found_zero_train = True
            assert fold["baseline_training_mean"] == pytest.approx(0.0)
            assert fold["baseline_training_median"] == pytest.approx(0.0)
            assert fold["metrics"]["global_mean"]["mae"] == pytest.approx(1.0)
            assert fold["metrics"]["global_median"]["mae"] == pytest.approx(1.0)
    assert found_zero_train


def test_report_schema(tmp_path: Path):
    path = _write_table(tmp_path / "ok.csv", _balanced_rows(10))
    report = evaluate_and_write(path, tmp_path / "out", n_splits=5)
    required = {
        "evaluator_version",
        "schema_version",
        "dataset_path",
        "dataset_row_count",
        "number_of_occupation_groups",
        "number_of_folds",
        "alpha_candidates",
        "tfidf_configuration",
        "model_configuration",
        "target_distribution",
        "label_source_counts",
        "resolution_method_counts",
        "validation_summary",
        "folds",
        "pooled_oof_metrics",
        "prediction_range",
        "warnings",
        "limitations",
    }
    assert required.issubset(report)
    assert report["alpha_candidates"] == ALPHA_CANDIDATES
    fold_required = {
        "fold",
        "train_row_count",
        "test_row_count",
        "train_occupation_count",
        "test_occupation_count",
        "train_occupation_codes",
        "test_occupation_codes",
        "occupation_intersection",
        "inner_split_count",
        "selected_alpha",
        "inner_alpha_results",
        "metrics",
    }
    dumped = json.dumps(report["folds"])
    assert "Perform documented clerical" not in dumped
    for fold in report["folds"]:
        assert fold_required.issubset(fold)
    pred = report["prediction_range"]
    assert {"raw_min", "raw_max", "below_zero_count", "above_one_count"} <= set(pred)
    json_path = tmp_path / "out" / "task_exposure_grouped_cv.json"
    md_path = tmp_path / "out" / "task_exposure_grouped_cv.md"
    assert json_path.exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert (
        "The target labels are provisional AI-generated weak supervision and are "
        "not human-validated ground truth, personal job-loss probabilities, or "
        "employment outcomes."
    ) in markdown
    assert "raw_metrics" in report
    assert "clipped_metrics" in report
    assert report["label_source_counts"]["provisional_ai_weak_supervision"] == 10


def test_constant_fold_r2_recorded_as_null(tmp_path: Path):
    rows = []
    for i in range(3):
        rows.append(_row(f"x{i}", "occ-X", f"constant class tokens {i} aaa", 0.50))
        rows.append(_row(f"y{i}", "occ-Y", f"other class tokens {i} bbb", 0.00))
        rows.append(_row(f"z{i}", "occ-Z", f"third class tokens {i} ccc", 1.00))
    path = _write_table(tmp_path / "const.csv", rows)
    validated = load_and_validate_dataset(path, n_splits=3)
    report = run_grouped_evaluation(validated, n_splits=3, alphas=[1.0, 10.0])
    r2_values = [fold["metrics"]["tfidf_ridge_raw"]["r2"] for fold in report["folds"]]
    assert any(value is None for value in r2_values)
    assert 0.0 not in r2_values
    assert any("constant" in w.lower() for w in report["warnings"])
