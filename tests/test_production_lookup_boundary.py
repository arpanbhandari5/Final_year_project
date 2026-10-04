"""Production lookup must not use weak-supervision data or the research classifier."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from experiments.task_exposure.research_task_classifier import predict_research_task_exposure
from task_exposure_assessor import (
    FORBIDDEN_WEAK_SUPERVISION_FILES,
    UNRESOLVED_REASON,
    approved_crosswalk_count,
    confirm_occupation,
    lookup_verified_task_exposure,
    resolve_occupation,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_SOURCES = (
    ROOT / "task_exposure_assessor.py",
    ROOT / "risk_assessor.py",
    ROOT / "app.py",
)
FRONTEND_SOURCES = (
    ROOT / "templates" / "index.html",
    ROOT / "static" / "script.js",
)


def test_production_sources_do_not_load_weak_supervision() -> None:
    for path in PRODUCTION_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert "project_data/task_exposure_labels/task_exposure_training.csv" not in text
        assert "predict_research_task_exposure" not in text
        assert "evaluate_public_gpts_benchmark" not in text
        assert "LogisticRegression" not in text
        if path.name != "task_exposure_assessor.py":
            for forbidden in FORBIDDEN_WEAK_SUPERVISION_FILES:
                assert forbidden not in text


def test_research_classifier_is_explicitly_experimental() -> None:
    payload = predict_research_task_exposure("Develop software applications")
    assert payload["status"] == "experimental"
    assert payload["source_type"] == "tfidf_classifier_prediction"
    assert payload["prediction_is_published_label"] is False
    assert payload["prediction"] is None


def test_independent_distribution_matches_lookup() -> None:
    code = "11-1011.00"
    frame = pd.read_csv(
        ROOT / "experiments" / "task_exposure" / "data" / "public_benchmark" / "public_gpts_are_gpts_benchmark.csv",
        dtype=str,
        usecols=["occupation_code", "human_labels"],
    )
    labels = frame.loc[frame["occupation_code"] == code, "human_labels"].str.strip().str.upper()
    labelled = [item for item in labels if item in {"E0", "E1", "E2"}]
    expected = {cls: labelled.count(cls) / len(labelled) for cls in ("E0", "E1", "E2")}
    match = resolve_occupation(occupation_code=code)
    exposure = lookup_verified_task_exposure(match)
    assert match["status"] == "confirmed"
    assert exposure["status"] == "verified"
    assert exposure["source_type"] == "published_benchmark_lookup"
    for cls in ("E0", "E1", "E2"):
        assert abs(exposure["distribution"][cls] - expected[cls]) < 1e-12
    assert exposure["labelled_task_count"] == len(labelled)
    assert exposure["normalization_denominator"] == len(labelled)


def test_approved_crosswalk_table_is_empty() -> None:
    assert approved_crosswalk_count() == 0


def test_approved_crosswalk_mechanism(monkeypatch) -> None:
    def fake_crosswalk():
        return [
            {
                "alias": "fixture software engineer",
                "canonical_occupation_code": "15-1252.00",
                "canonical_title": "Software Developers",
                "mapping_source": "test_fixture",
                "mapping_method": "reviewed_crosswalk",
                "review_status": "approved",
            }
        ]

    monkeypatch.setattr("task_exposure_assessor.load_approved_crosswalk", fake_crosswalk)
    match = resolve_occupation(top_roles=[{"job_role": "fixture software engineer", "similarity": 0.8}])
    assert match["status"] == "candidate"
    assert match["matcher_source"] == "approved_crosswalk"
    assert match["candidate_code"] == "15-1252.00"
    assert lookup_verified_task_exposure(match)["status"] != "verified"
    confirmed = confirm_occupation(
        verified_occupation_code="15-1252.00",
        confirmation_method="user_confirmation",
        candidate=match,
    )
    exposure = lookup_verified_task_exposure(confirmed)
    assert exposure["status"] == "verified"
    assert exposure["match_method"] == "approved_crosswalk"


def test_unresolved_software_engineer_without_invented_alias() -> None:
    match = resolve_occupation(top_roles=[{"job_role": "Software Engineer", "similarity": 0.9}])
    if match["status"] == "candidate":
        assert match["matcher_source"] in {"exact_title", "cluster_soc", "approved_crosswalk"}
        assert lookup_verified_task_exposure(match)["status"] != "verified"
        return
    assert match["status"] == "unresolved"
    assert match["reason"] == UNRESOLVED_REASON
    exposure = lookup_verified_task_exposure(match)
    assert exposure["distribution"] is None
    assert exposure["tasks"] == []


def test_frontend_uses_historical_reference_headings() -> None:
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "script.js").read_text(encoding="utf-8")
    combined = index + "\n" + script
    assert "Historical occupation reference" in combined
    assert "Suggested occupation" in script
    assert "Candidate occupation" in script or "Candidate match" in script
    assert "Matched occupation" not in script
    assert "You will lose your job" not in combined
    assert "chance of losing your job" not in combined.lower()
    assert 'kpi__label">Automation risk' not in index
    assert "automation risk" not in script.lower()


def test_ollama_narrative_uses_text_content() -> None:
    script = (ROOT / "static" / "script.js").read_text(encoding="utf-8")
    assert "narrative.textContent" in script
    assert "dangerouslySetInnerHTML" not in script
    assert "v-html" not in script
