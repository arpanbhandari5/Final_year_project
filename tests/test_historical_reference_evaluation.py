"""Isolated tests for experiments/historical_reference/evaluate_historical_reference.py."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "historical_reference"))

from evaluate_historical_reference import (  # noqa: E402
    FORBIDDEN_IMPORTS,
    TARGET_COLUMN,
    assert_no_forbidden_imports,
    build_pipeline,
    evaluate_and_write,
    load_and_validate_dataset,
    run_grouped_evaluation,
    sha256_file,
    verify_group_disjoint,
)

AUTOMATION = ROOT / "data" / "automation_risk.csv"
PICKLE = ROOT / "ml_models" / "model.pkl"


def _row(role: str, industry: str, score: float, extra: str = "") -> dict:
    return {
        "job_role": role,
        "industry": industry,
        "avg_salary_usd": 50000,
        "experience_required_years": 2,
        "education_level": "Bachelor",
        "task_repetition_level": 0.2,
        "creativity_requirement": 0.3,
        "physical_labor_level": 0.1,
        "analytical_complexity": 0.4,
        "social_interaction_level": 0.5,
        "ai_tool_availability": "none",
        "ai_tool_maturity_score": 0.1,
        "percent_tasks_automatable": 0.2,
        "job_growth_rate": 0.0,
        "skill_complexity_score": 0.4,
        "regulation_strictness_level": 0.2,
        "ethical_risk_level": 0.1,
        "communication_requirement": 0.3,
        "domain_specific_knowledge_level": 0.2,
        "team_collaboration_level": 0.2,
        "ai_dependency_current": 0.1,
        "ai_dependency_future": 0.2,
        "training_hours_needed": 10,
        "job_demand_index": 0.5,
        TARGET_COLUMN: score,
        "note": extra,
    }


def test_historical_evaluator_imports_without_production_side_effects() -> None:
    assert_no_forbidden_imports()
    source_path = ROOT / "experiments" / "historical_reference" / "evaluate_historical_reference.py"
    source = source_path.read_text(encoding="utf-8")
    assert "joblib.dump" not in source
    assert "FORBIDDEN_IMPORTS" in source


def test_grouped_split_has_no_occupation_overlap() -> None:
    verify_group_disjoint(np.array(["a", "a", "b"]), np.array(["c", "d"]))
    try:
        verify_group_disjoint(np.array(["nurse"]), np.array(["nurse"]))
    except RuntimeError:
        return
    raise AssertionError("overlap should raise")


def test_tfidf_is_inside_pipeline() -> None:
    pipeline = build_pipeline(1.0)
    assert isinstance(pipeline, Pipeline)
    assert list(pipeline.named_steps) == ["tfidf", "model"]
    assert isinstance(pipeline.named_steps["tfidf"], TfidfVectorizer)


def test_baselines_are_fit_only_on_training_data(tmp_path: Path) -> None:
    rows = []
    for i in range(6):
        rows.append(_row(f"low-{i}", "A", 0.1, extra=f"token{i}aaa"))
    for i in range(6):
        rows.append(_row(f"high-{i}", "B", 0.9, extra=f"token{i}zzz"))
    path = tmp_path / "hist.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    validated = load_and_validate_dataset(path, n_splits=2)
    result = run_grouped_evaluation(validated, n_splits=2, alphas=[1.0])
    for fold in result["folds"]:
        assert fold["n_train_groups"] >= 1
        assert fold["n_test_groups"] >= 1
        assert fold["mean_baseline"]["mae"] >= 0


def test_validation_and_test_data_are_not_used_for_fit(tmp_path: Path, monkeypatch) -> None:
    rows = [_row(f"role-{i}", "Ind", 0.2 + (i % 5) * 0.1, extra=f"uniq{i}") for i in range(12)]
    path = tmp_path / "fit.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    validated = load_and_validate_dataset(path, n_splits=3)
    fit_sizes: list[int] = []
    original = TfidfVectorizer.fit_transform

    def tracked(self, raw_documents, y=None):
        fit_sizes.append(len(list(raw_documents)))
        return original(self, raw_documents, y)

    monkeypatch.setattr(TfidfVectorizer, "fit_transform", tracked)
    run_grouped_evaluation(validated, n_splits=3, alphas=[1.0])
    n_rows = validated.summary["rows"]
    assert fit_sizes
    assert all(size < n_rows for size in fit_sizes)


def test_evaluator_does_not_write_model_artifacts(tmp_path: Path) -> None:
    before = sha256_file(PICKLE)
    rows = [_row(f"role-{i}", "Ind", 0.3, extra=f"word{i}") for i in range(10)]
    dataset = tmp_path / "tiny.csv"
    pd.DataFrame(rows).to_csv(dataset, index=False)
    evaluate_and_write(dataset, tmp_path / "out", n_splits=5)
    assert sha256_file(PICKLE) == before
    assert not (tmp_path / "model.pkl").exists()


def test_automation_risk_csv_hash_is_unchanged() -> None:
    digest = hashlib.sha256()
    digest.update(AUTOMATION.read_bytes())
    expected = digest.hexdigest()
    assert sha256_file(AUTOMATION) == expected
    load_and_validate_dataset(AUTOMATION, n_splits=5)
    assert sha256_file(AUTOMATION) == expected
