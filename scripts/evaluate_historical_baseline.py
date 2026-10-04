"""Audit reproducibility of the historical occupation-risk model artifact.

This script intentionally does not retrain or overwrite production artifacts.
It reports whether the stored artifact contains enough information to reproduce
the historical cross-validation metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODEL_PATH = BASE_DIR / "ml_models" / "model.pkl"
DEFAULT_OUTPUT = BASE_DIR / "reports" / "data_quality" / "historical_baseline_reproducibility.json"

SOURCE_NAMES = (
    "automation_risk.csv",
    "resume_corpus.csv",
    "coursera_catalog.csv",
    "onet_skils.csv",
    "onet_interests.csv",
    "onet_interest_keywords.csv",
)


def dataset_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_artifact(path: Path) -> dict[str, Any]:
    artifact = joblib.load(path)
    if not isinstance(artifact, dict):
        raise TypeError(f"Expected a dictionary model artifact, got {type(artifact).__name__}")
    return artifact


def build_report(model_path: Path = MODEL_PATH) -> dict[str, Any]:
    source_paths = [DATA_DIR / name for name in SOURCE_NAMES]
    missing_sources = [str(path.relative_to(BASE_DIR)) for path in source_paths if not path.exists()]
    artifact = load_artifact(model_path)
    metadata = artifact.get("metadata", {})
    stored_hash = metadata.get("dataset_hash", artifact.get("dataset_hash"))
    current_hash = None if missing_sources else dataset_hash(source_paths)

    automation_rows = None
    automation_path = DATA_DIR / "automation_risk.csv"
    if automation_path.exists():
        automation_rows = int(pd.read_csv(automation_path).shape[0])

    has_out_of_fold_predictions = "out_of_fold_predictions" in artifact
    has_split_manifest = "evaluation_split_manifest" in artifact
    exact_reproduction_possible = bool(
        has_out_of_fold_predictions and has_split_manifest and not missing_sources and stored_hash == current_hash
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(model_path.relative_to(BASE_DIR)),
        "model_version": metadata.get("model_version", artifact.get("model_version")),
        "training_timestamp": metadata.get("training_timestamp", artifact.get("training_timestamp")),
        "stored_dataset_hash": stored_hash,
        "current_dataset_hash": current_hash,
        "dataset_hash_matches": stored_hash == current_hash if current_hash else None,
        "source_files": list(SOURCE_NAMES),
        "missing_source_files": missing_sources,
        "automation_risk_row_count": automation_rows,
        "selected_alpha": metadata.get("selected_alpha", artifact.get("selected_alpha")),
        "has_out_of_fold_predictions": has_out_of_fold_predictions,
        "has_evaluation_split_manifest": has_split_manifest,
        "exact_historical_cv_reproduction_possible": exact_reproduction_possible,
        "status": (
            "reproducible_from_artifact"
            if exact_reproduction_possible
            else "historical_baseline_not_exactly_reproducible_from_artifact"
        ),
        "reason": (
            "The stored model does not retain out-of-fold predictions and the evaluation split manifest. "
            "Recomputing MAE, RMSE, and R2 would require retraining, so no historical baseline metric is fabricated."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()