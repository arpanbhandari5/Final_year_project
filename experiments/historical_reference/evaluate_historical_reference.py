"""Leakage-aware evaluator for data/automation_risk.csv.

Research-only. Does not import evaluation.py, train_model.py, risk_assessor.py,
or app.py. Does not write pickles or modify source datasets.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

EVALUATOR_VERSION = "1.0.0"
DEFAULT_N_SPLITS = 5
ALPHA_CANDIDATES = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
TFIDF_CONFIGURATION = {
    "ngram_range": (1, 2),
    "min_df": 1,
    "sublinear_tf": True,
    "max_features": 7000,
    "stop_words": "english",
}
TARGET_COLUMN = "automation_risk_score"
GROUP_COLUMN = "job_role"
FORBIDDEN_IMPORTS = frozenset({"evaluation", "train_model", "risk_assessor", "app", "storage"})
LIMITATION_TEXT = (
    "This is a corrected, leakage-aware re-evaluation of the historical "
    "occupation-level automation_risk_score. It is not a personal job-loss, "
    "unemployment, or replacement probability."
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = REPO_ROOT / "data" / "automation_risk.csv"
DEFAULT_REPORT_DIR = REPO_ROOT / "experiments" / "historical_reference" / "reports"
PROTECTED_PICKLE = REPO_ROOT / "ml_models" / "model.pkl"


class DatasetValidationError(ValueError):
    """Raised when the historical CSV cannot be evaluated as specified."""


@dataclass
class ValidatedDataset:
    frame: pd.DataFrame
    texts: list[str]
    targets: np.ndarray
    groups: np.ndarray
    summary: dict[str, Any]


def _json_ready(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def assert_no_forbidden_imports(source_path: Path | None = None) -> None:
    path = source_path or Path(__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    blocked = names & FORBIDDEN_IMPORTS
    if blocked:
        raise RuntimeError(f"Historical evaluator imported production modules: {sorted(blocked)}")


def build_job_text(row: pd.Series) -> str:
    pieces = [
        str(row.get("job_role", "")),
        str(row.get("industry", "")),
        str(row.get("education_level", "")),
        f"experience {row.get('experience_required_years', '')}",
        f"salary {row.get('avg_salary_usd', '')}",
        f"repetition {row.get('task_repetition_level', '')}",
        f"creativity {row.get('creativity_requirement', '')}",
        f"physical {row.get('physical_labor_level', '')}",
        f"analysis {row.get('analytical_complexity', '')}",
        f"social {row.get('social_interaction_level', '')}",
        f"skills {row.get('skill_complexity_score', '')}",
        f"communication {row.get('communication_requirement', '')}",
        f"domain {row.get('domain_specific_knowledge_level', '')}",
        f"team {row.get('team_collaboration_level', '')}",
    ]
    return " ".join(" ".join(pieces).split()).lower()


def build_pipeline(alpha: float) -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=TFIDF_CONFIGURATION["ngram_range"],
                    min_df=TFIDF_CONFIGURATION["min_df"],
                    sublinear_tf=TFIDF_CONFIGURATION["sublinear_tf"],
                    max_features=TFIDF_CONFIGURATION["max_features"],
                    stop_words=TFIDF_CONFIGURATION["stop_words"],
                ),
            ),
            ("model", Ridge(alpha=alpha, fit_intercept=True)),
        ]
    )


def verify_group_disjoint(train_groups: np.ndarray, test_groups: np.ndarray) -> None:
    overlap = set(train_groups) & set(test_groups)
    if overlap:
        raise RuntimeError(f"Occupation/group leakage across folds: {sorted(overlap)[:12]}")


def load_and_validate_dataset(path: Path, *, n_splits: int = DEFAULT_N_SPLITS) -> ValidatedDataset:
    if not path.is_file():
        raise DatasetValidationError(f"Dataset does not exist: {path}")
    frame = pd.read_csv(path)
    columns = list(frame.columns)
    if TARGET_COLUMN not in columns:
        raise DatasetValidationError(
            f"Target {TARGET_COLUMN!r} not found. Columns: {columns}"
        )
    if GROUP_COLUMN not in columns:
        raise DatasetValidationError(
            f"Grouping column {GROUP_COLUMN!r} not found. Columns: {columns}"
        )
    targets = pd.to_numeric(frame[TARGET_COLUMN], errors="raise").astype(float).clip(0.0, 1.0).to_numpy()
    groups = frame[GROUP_COLUMN].map(lambda value: str(value or "").strip().lower()).to_numpy()
    if (groups == "").any():
        raise DatasetValidationError("Blank grouping keys are not allowed.")
    n_groups = int(len(set(groups)))
    if n_groups < n_splits:
        raise DatasetValidationError(
            f"Need at least {n_splits} unique {GROUP_COLUMN} values; found {n_groups}."
        )
    texts = [build_job_text(row) for _, row in frame.iterrows()]
    summary = {
        "path": str(path),
        "sha256": sha256_file(path),
        "rows": int(len(frame)),
        "columns": columns,
        "target": TARGET_COLUMN,
        "group": GROUP_COLUMN,
        "unique_groups": n_groups,
        "target_min": float(np.min(targets)),
        "target_max": float(np.max(targets)),
        "target_mean": float(np.mean(targets)),
        "n_splits": int(n_splits),
        "dataset_identity": "historical_automation_risk_csv",
        "not_frey_osborne_618": True,
        "not_gpts_are_gpts": True,
        "not_personal_job_loss": True,
    }
    return ValidatedDataset(frame=frame, texts=texts, targets=targets, groups=groups, summary=summary)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(root_mean_squared_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)),
    }


def select_alpha_grouped(
    texts: list[str],
    targets: np.ndarray,
    groups: np.ndarray,
    alphas: list[float],
) -> float:
    unique = list(dict.fromkeys(groups.tolist()))
    inner_splits = min(3, len(unique))
    if inner_splits < 2:
        return float(alphas[0])
    splitter = GroupKFold(n_splits=inner_splits, shuffle=False)
    best_alpha = float(alphas[0])
    best_mae = float("inf")
    for alpha in alphas:
        maes: list[float] = []
        pipeline = build_pipeline(alpha)
        for train_idx, val_idx in splitter.split(texts, targets, groups):
            verify_group_disjoint(groups[train_idx], groups[val_idx])
            model = clone(pipeline)
            model.fit([texts[i] for i in train_idx], targets[train_idx])
            pred = np.clip(model.predict([texts[i] for i in val_idx]), 0.0, 1.0)
            maes.append(float(mean_absolute_error(targets[val_idx], pred)))
        mean_mae = float(np.mean(maes))
        if mean_mae < best_mae:
            best_mae = mean_mae
            best_alpha = float(alpha)
    return best_alpha


def run_grouped_evaluation(
    validated: ValidatedDataset,
    *,
    n_splits: int = DEFAULT_N_SPLITS,
    alphas: list[float] | None = None,
) -> dict[str, Any]:
    assert_no_forbidden_imports()
    alphas = alphas or ALPHA_CANDIDATES
    texts = validated.texts
    y = validated.targets
    groups = validated.groups
    splitter = GroupKFold(n_splits=n_splits, shuffle=False)
    fold_rows: list[dict[str, Any]] = []
    oof_true: list[float] = []
    oof_ridge: list[float] = []
    oof_mean: list[float] = []
    oof_median: list[float] = []
    selected_alphas: list[float] = []

    for fold, (train_idx, test_idx) in enumerate(splitter.split(texts, y, groups), start=1):
        verify_group_disjoint(groups[train_idx], groups[test_idx])
        train_texts = [texts[i] for i in train_idx]
        test_texts = [texts[i] for i in test_idx]
        y_train = y[train_idx]
        y_test = y[test_idx]
        alpha = select_alpha_grouped(train_texts, y_train, groups[train_idx], alphas)
        selected_alphas.append(alpha)
        pipeline = build_pipeline(alpha)
        if not isinstance(pipeline.named_steps.get("tfidf"), TfidfVectorizer):
            raise RuntimeError("TF-IDF must be a Pipeline step.")
        pipeline.fit(train_texts, y_train)
        ridge_pred = np.clip(pipeline.predict(test_texts), 0.0, 1.0)
        mean_pred = np.full(len(test_idx), float(np.mean(y_train)))
        median_pred = np.full(len(test_idx), float(np.median(y_train)))
        ridge_metrics = _metrics(y_test, ridge_pred)
        mean_metrics = _metrics(y_test, mean_pred)
        median_metrics = _metrics(y_test, median_pred)
        fold_rows.append(
            {
                "fold": fold,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
                "n_train_groups": int(len(set(groups[train_idx]))),
                "n_test_groups": int(len(set(groups[test_idx]))),
                "selected_alpha": alpha,
                "ridge": ridge_metrics,
                "mean_baseline": mean_metrics,
                "median_baseline": median_metrics,
            }
        )
        oof_true.extend(y_test.tolist())
        oof_ridge.extend(ridge_pred.tolist())
        oof_mean.extend(mean_pred.tolist())
        oof_median.extend(median_pred.tolist())

    actual = np.asarray(oof_true, dtype=float)
    pooled = {
        "ridge": _metrics(actual, np.asarray(oof_ridge)),
        "mean_baseline": _metrics(actual, np.asarray(oof_mean)),
        "median_baseline": _metrics(actual, np.asarray(oof_median)),
    }
    def _fold_mean(model_key: str, metric: str) -> float:
        return float(np.mean([row[model_key][metric] for row in fold_rows]))

    return {
        "evaluator_version": EVALUATOR_VERSION,
        "protocol": "corrected_leakage_aware_re-evaluation",
        "exact_old_metric_reproducible": False,
        "exact_old_metric_reason": (
            "evaluation.py still imports missing train_model.build_risk_pipeline; "
            "ml_models/model.pkl has no out-of-fold predictions or split manifest "
            "(reports/data_quality/historical_baseline_reproducibility.json)."
        ),
        "limitation": LIMITATION_TEXT,
        "dataset": validated.summary,
        "tfidf_inside_pipeline": True,
        "group_kfold": True,
        "n_splits": n_splits,
        "alpha_candidates": alphas,
        "selected_alphas": selected_alphas,
        "folds": fold_rows,
        "pooled_out_of_fold": pooled,
        "mean_fold": {
            "ridge": {metric: _fold_mean("ridge", metric) for metric in ("mae", "rmse", "r2")},
            "mean_baseline": {metric: _fold_mean("mean_baseline", metric) for metric in ("mae", "rmse", "r2")},
            "median_baseline": {
                metric: _fold_mean("median_baseline", metric) for metric in ("mae", "rmse", "r2")
            },
        },
        "wrote_pickle": False,
        "modified_source_dataset": False,
    }


def write_reports(payload: dict[str, Any], report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "historical_automation_risk_grouped_cv.json"
    md_path = report_dir / "historical_automation_risk_grouped_cv.md"
    json_path.write_text(json.dumps(_json_ready(payload), indent=2), encoding="utf-8")
    pooled = payload["pooled_out_of_fold"]
    mean_fold = payload["mean_fold"]
    lines = [
        "# Historical automation-risk grouped CV (isolated)",
        "",
        "Corrected, leakage-aware re-evaluation. **Not** a direct improvement claim over the original production model.",
        "",
        LIMITATION_TEXT,
        "",
        "## Exact old metric reproducible",
        "",
        "NO.",
        "",
        payload["exact_old_metric_reason"],
        "",
        f"- Dataset: `{payload['dataset']['path']}`",
        f"- SHA-256: `{payload['dataset']['sha256']}`",
        f"- Rows: {payload['dataset']['rows']}",
        f"- Unique {GROUP_COLUMN}: {payload['dataset']['unique_groups']}",
        f"- Target: `{TARGET_COLUMN}`",
        f"- Grouping: `{GROUP_COLUMN}` + GroupKFold({payload['n_splits']})",
        "- TF-IDF fitted inside sklearn Pipeline on training folds only.",
        "",
        "This dataset is **not** the 618-row Frey–Osborne historical occupation table and **not** the GPTs-are-GPTs benchmark.",
        "",
        "## Pooled out-of-fold metrics",
        "",
        "| Model | MAE | RMSE | Pooled out-of-fold R² |",
        "|---|---|---|---|",
        f"| Training-fold mean baseline | {pooled['mean_baseline']['mae']:.4f} | {pooled['mean_baseline']['rmse']:.4f} | {pooled['mean_baseline']['r2']:.4f} |",
        f"| Training-fold median baseline | {pooled['median_baseline']['mae']:.4f} | {pooled['median_baseline']['rmse']:.4f} | {pooled['median_baseline']['r2']:.4f} |",
        f"| TF-IDF + Ridge (Pipeline) | {pooled['ridge']['mae']:.4f} | {pooled['ridge']['rmse']:.4f} | {pooled['ridge']['r2']:.4f} |",
        "",
        "## Mean fold metrics",
        "",
        "| Model | Mean fold MAE | Mean fold RMSE | Mean fold R² |",
        "|---|---|---|---|",
        f"| Training-fold mean baseline | {mean_fold['mean_baseline']['mae']:.4f} | {mean_fold['mean_baseline']['rmse']:.4f} | {mean_fold['mean_baseline']['r2']:.4f} |",
        f"| Training-fold median baseline | {mean_fold['median_baseline']['mae']:.4f} | {mean_fold['median_baseline']['rmse']:.4f} | {mean_fold['median_baseline']['r2']:.4f} |",
        f"| TF-IDF + Ridge (Pipeline) | {mean_fold['ridge']['mae']:.4f} | {mean_fold['ridge']['rmse']:.4f} | {mean_fold['ridge']['r2']:.4f} |",
        "",
        "Do not treat pooled R² and mean fold R² as conflicting values; they answer different aggregations.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def evaluate_and_write(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    report_dir: Path = DEFAULT_REPORT_DIR,
    n_splits: int = DEFAULT_N_SPLITS,
) -> dict[str, Any]:
    pickle_before = sha256_file(PROTECTED_PICKLE)
    csv_before = sha256_file(dataset_path)
    validated = load_and_validate_dataset(dataset_path, n_splits=n_splits)
    payload = run_grouped_evaluation(validated, n_splits=n_splits)
    write_reports(payload, report_dir)
    if sha256_file(dataset_path) != csv_before:
        raise RuntimeError("Dataset hash changed; aborting.")
    if sha256_file(PROTECTED_PICKLE) != pickle_before:
        raise RuntimeError("Production pickle hash changed; aborting.")
    payload["protected_pickle_sha256"] = pickle_before
    payload["dataset_sha256_after"] = csv_before
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated historical automation-risk evaluator")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--n-splits", type=int, default=DEFAULT_N_SPLITS)
    args = parser.parse_args()
    payload = evaluate_and_write(args.dataset, args.report_dir, args.n_splits)
    print(json.dumps(_json_ready({"pooled_out_of_fold": payload["pooled_out_of_fold"], "mean_fold": payload["mean_fold"]}), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
