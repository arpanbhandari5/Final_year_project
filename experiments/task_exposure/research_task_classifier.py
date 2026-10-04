"""Research-only TF-IDF E0/E1/E2 classifier interface.

This module is not imported by app.py, risk_assessor.py, or
task_exposure_assessor.py. Predictions are never published benchmark labels
and are never used as the production E0/E1/E2 source.

Offline occupation-grouped evaluation lives in
``evaluate_public_gpts_benchmark.py`` and
``reports/public_benchmark/model_evaluation.md``.
"""

from __future__ import annotations

from typing import Any

RESEARCH_EVALUATION = {
    "method": (
        "Occupation-held-out train/validation/test split (646/138/139 occupations) "
        "with GroupKFold hyperparameter selection on training occupations only. "
        "Test occupations are completely unseen during training."
    ),
    "artifact": "experiments/task_exposure/reports/public_benchmark/model_evaluation.md",
    "research_population": "GPTs-are-GPTs benchmark, 923 occupations",
    "not_production_performance": True,
    "scores_are_calibrated_probabilities": False,
}


def predict_research_task_exposure(task_text: str) -> dict[str, Any]:
    """Return an experimental prediction envelope without running production lookup.

    No classifier pickle is loaded here because none is authorized as a
    production artifact. Offline training remains in evaluate_public_gpts_benchmark.py.
    """
    _ = task_text
    return {
        "status": "experimental",
        "source_type": "tfidf_classifier_prediction",
        "prediction_is_published_label": False,
        "prediction": None,
        "model_score": None,
        "decision_score": None,
        "evaluation_context": RESEARCH_EVALUATION,
        "message": (
            "Research classifier predictions are not published benchmark labels. "
            "Run experiments/task_exposure/evaluate_public_gpts_benchmark.py for "
            "offline occupation-grouped evaluation."
        ),
    }
