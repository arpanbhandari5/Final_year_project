"""Isolated leakage-safe evaluator for the task-exposure training table.

This module is experimental. It does not import or modify the production
automation-risk evaluator, trainer, or model artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

EVALUATOR_VERSION = "1.1.0"
SCHEMA_VERSION = "1.1.0"

ALLOWED_TARGET_VALUES = (0.00, 0.25, 0.50, 0.75, 1.00)
TARGET_TOLERANCE = 1e-9
DEFAULT_N_SPLITS = 5
ALPHA_CANDIDATES = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
TFIDF_CONFIGURATION = {
    "ngram_range": [1, 2],
    "min_df": 1,
    "sublinear_tf": True,
    "max_features": 12000,
    "stop_words": "english",
}
MODEL_CONFIGURATION = {"estimator": "Ridge", "fit_intercept": True}
TEXT_COLUMN = "task_text"
REQUIRED_COLUMNS = (
    "task_id",
    "occupation_code",
    TEXT_COLUMN,
    "adjudicated_exposure_score",
    "not_human_ground_truth",
    "label_source",
    "resolution_method",
)
LIMITATION_TEXT = (
    "The target labels are provisional AI-generated weak supervision and are "
    "not human-validated ground truth, personal job-loss probabilities, or "
    "employment outcomes."
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = (
    REPO_ROOT / "project_data" / "task_exposure_labels" / "task_exposure_training.csv"
)
DEFAULT_REPORT_DIR = (
    REPO_ROOT / "experiments" / "task_exposure" / "reports" / "model_evaluation"
)


class DatasetValidationError(ValueError):
    """Raised when the training table fails schema or numeric validation."""


@dataclass
class ValidatedDataset:
    frame: pd.DataFrame
    summary: dict[str, Any]
    warnings: list[str]


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
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return value


def _count_blank(series: pd.Series) -> int:
    return int(series.isna().sum() + (series.astype(str).str.strip() == "").sum())


def parse_not_human_ground_truth(series: pd.Series) -> pd.Series:
    """Interpret CSV flags without coercing invalid values to True."""
    normalized = series.astype(str).str.strip().str.lower()
    true_mask = normalized.isin({"true", "1", "yes"})
    false_mask = normalized.isin({"false", "0", "no", ""})
    nan_mask = series.isna()
    unknown = ~(true_mask | false_mask | nan_mask)
    parsed = pd.Series(pd.NA, index=series.index, dtype="boolean")
    parsed = parsed.mask(true_mask, True)
    parsed = parsed.mask(false_mask | nan_mask, False)
    parsed = parsed.mask(unknown, pd.NA)
    return parsed


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    return {str(key): int(count) for key, count in series.astype(str).value_counts().items()}


def target_matches_allowed(value: float) -> bool:
    return any(abs(value - allowed) <= TARGET_TOLERANCE for allowed in ALLOWED_TARGET_VALUES)


def safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float | None, str | None]:
    """Return R², or None with a warning when y_true is constant."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.size == 0:
        return None, "R2 is undefined because the fold has no observations."
    if np.unique(y_true).size < 2 or float(np.std(y_true)) == 0.0:
        return (
            None,
            "R2 is undefined because y_true is constant in this fold; the "
            "value is recorded as null rather than zero.",
        )
    return float(r2_score(y_true, y_pred)), None


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2, r2_warning = safe_r2(y_true, y_pred)
    if r2_warning:
        warnings.append(r2_warning)
    return {"mae": mae, "rmse": rmse, "r2": r2}, warnings


def verify_group_disjoint(
    train_groups: np.ndarray,
    heldout_groups: np.ndarray,
    *,
    context: str,
) -> list[str]:
    intersection = sorted(set(train_groups) & set(heldout_groups))
    if intersection:
        raise RuntimeError(
            f"{context}: occupation groups overlap between train and held-out "
            f"splits: {intersection}"
        )
    return intersection


def build_pipeline(alpha: float) -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=tuple(TFIDF_CONFIGURATION["ngram_range"]),
                    min_df=TFIDF_CONFIGURATION["min_df"],
                    sublinear_tf=TFIDF_CONFIGURATION["sublinear_tf"],
                    max_features=TFIDF_CONFIGURATION["max_features"],
                    stop_words=TFIDF_CONFIGURATION["stop_words"],
                ),
            ),
            ("model", Ridge(alpha=alpha)),
        ]
    )


def load_and_validate_dataset(
    path: Path,
    *,
    n_splits: int = DEFAULT_N_SPLITS,
) -> ValidatedDataset:
    if not path.exists():
        raise DatasetValidationError(f"Dataset does not exist: {path}")

    frame = pd.read_csv(path)
    warnings: list[str] = []
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing_columns:
        raise DatasetValidationError(
            "Missing required columns: "
            f"{missing_columns}. Found columns: {list(frame.columns)}"
        )

    try:
        frame["adjudicated_exposure_score"] = pd.to_numeric(
            frame["adjudicated_exposure_score"],
            errors="raise",
        )
    except (ValueError, TypeError) as exc:
        raise DatasetValidationError(
            "adjudicated_exposure_score could not be converted with "
            "pd.to_numeric(..., errors='raise'). Invalid values were not "
            f"coerced to NaN or zero. Underlying error: {exc}"
        ) from exc

    target = frame["adjudicated_exposure_score"]
    task_ids = frame["task_id"]
    occupations = frame["occupation_code"]
    statements = frame[TEXT_COLUMN]
    truth_flag = parse_not_human_ground_truth(frame["not_human_ground_truth"])

    missing_target = int(target.isna().sum())
    missing_task_id = _count_blank(task_ids)
    missing_occupation = _count_blank(occupations)
    empty_statements = _count_blank(statements)
    duplicate_task_ids = int(task_ids.duplicated().sum())
    duplicate_task_id_values = (
        task_ids[task_ids.duplicated(keep=False)].astype(str).tolist()
        if duplicate_task_ids
        else []
    )

    invalid_mask = target.notna() & ~target.map(target_matches_allowed)
    invalid_targets = [float(v) for v in target[invalid_mask].tolist()]
    not_true_count = int((~truth_flag.fillna(False)).sum())

    errors: list[str] = []
    if missing_target:
        errors.append(f"adjudicated_exposure_score has {missing_target} missing value(s).")
    if missing_task_id:
        errors.append(f"task_id has {missing_task_id} missing or blank value(s).")
    if missing_occupation:
        errors.append(f"occupation_code has {missing_occupation} missing or blank value(s).")
    if empty_statements:
        errors.append(
            f"{TEXT_COLUMN} has {empty_statements} empty or whitespace-only value(s)."
        )
    if duplicate_task_ids:
        errors.append(
            f"task_id is not unique ({duplicate_task_ids} extra row(s); "
            f"duplicates={sorted(set(duplicate_task_id_values))})."
        )
    if invalid_targets:
        errors.append(
            "adjudicated_exposure_score contains values outside the allowed set "
            f"{list(ALLOWED_TARGET_VALUES)} with tolerance {TARGET_TOLERANCE}: "
            f"{invalid_targets}"
        )
    if not_true_count:
        errors.append(
            "not_human_ground_truth must be True for every row; "
            f"found {not_true_count} row(s) that are not True. "
            "The dataset was not modified."
        )

    unique_occupations = occupations.dropna().astype(str).str.strip()
    unique_occupations = unique_occupations[unique_occupations != ""]
    n_occupations = int(unique_occupations.nunique())
    if n_occupations < n_splits:
        errors.append(
            f"Need at least {n_splits} unique occupation_code groups for "
            f"GroupKFold, found {n_occupations}."
        )

    observed_counts: dict[str, int] = {}
    for allowed in ALLOWED_TARGET_VALUES:
        count = int(sum(abs(float(v) - allowed) <= TARGET_TOLERANCE for v in target.dropna()))
        observed_counts[f"{allowed:.2f}"] = count
    if observed_counts["1.00"] == 0:
        warnings.append(
            "Target value 1.00 is absent. This is a distribution observation, "
            "not a validation failure."
        )

    label_source_counts = value_counts_dict(frame["label_source"])
    resolution_method_counts = value_counts_dict(frame["resolution_method"])

    summary = {
        "dataset_path": str(path),
        "dataset_row_count": int(len(frame)),
        "number_of_occupation_groups": n_occupations,
        "number_of_unique_tasks": int(task_ids.nunique(dropna=True)),
        "text_column_used": TEXT_COLUMN,
        "target_distribution": observed_counts,
        "label_source_counts": label_source_counts,
        "resolution_method_counts": resolution_method_counts,
        "not_human_ground_truth_all_true": not_true_count == 0,
        "missing_value_counts": {
            "adjudicated_exposure_score": missing_target,
            "task_id": missing_task_id,
            "occupation_code": missing_occupation,
            TEXT_COLUMN: empty_statements,
        },
        "duplicate_task_id_count": duplicate_task_ids,
        "invalid_target_values": invalid_targets,
        "terminology": (
            "schema-validated provisional AI weak labels / "
            "deduplicated task-exposure training table"
        ),
    }

    if errors:
        raise DatasetValidationError(
            "Dataset validation failed; the file was not modified. " + " ".join(errors)
        )

    sources = set(frame["label_source"].astype(str))
    if sources and sources <= {"provisional_ai_weak_supervision", "ai_weak_supervision"}:
        warnings.append(
            "All current labels are provisional AI-generated weak supervision. "
            "Schema and pipeline checks do not imply human validation."
        )

    return ValidatedDataset(
        frame=frame,
        summary=summary,
        warnings=warnings,
    )


def select_alpha_grouped(
    texts: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    alphas: list[float],
    inner_splits: int,
) -> tuple[float, list[dict[str, Any]]]:
    if inner_splits < 2:
        raise ValueError(
            f"inner_splits must be >= 2 for grouped alpha search, got {inner_splits}."
        )
    n_groups = int(pd.unique(groups).size)
    if n_groups < inner_splits:
        raise ValueError(
            f"inner GroupKFold needs {inner_splits} occupation groups, found {n_groups}."
        )

    inner_cv = GroupKFold(n_splits=inner_splits, shuffle=False)
    results: list[dict[str, Any]] = []
    for alpha in alphas:
        fold_maes: list[float] = []
        for inner_train_idx, inner_val_idx in inner_cv.split(texts, y, groups):
            verify_group_disjoint(
                groups[inner_train_idx],
                groups[inner_val_idx],
                context=f"inner GroupKFold alpha={alpha}",
            )
            pipeline = build_pipeline(alpha)
            pipeline.fit(texts[inner_train_idx], y[inner_train_idx])
            pred = pipeline.predict(texts[inner_val_idx])
            fold_maes.append(float(mean_absolute_error(y[inner_val_idx], pred)))
        results.append(
            {
                "alpha": float(alpha),
                "mean_inner_mae": float(np.mean(fold_maes)),
                "inner_fold_maes": [float(v) for v in fold_maes],
            }
        )
    best = min(results, key=lambda row: (row["mean_inner_mae"], row["alpha"]))
    return float(best["alpha"]), results


def _mean_std(values: list[float | None], *, ddof: int = 1) -> dict[str, float | None]:
    numeric = [float(v) for v in values if v is not None]
    if not numeric:
        return {"mean": None, "std": None, "n": 0}
    array = np.asarray(numeric, dtype=float)
    std = float(array.std(ddof=ddof)) if len(array) > 1 else 0.0
    return {"mean": float(array.mean()), "std": std, "n": int(len(array))}


def _summarize_method_folds(fold_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mae": _mean_std([m["mae"] for m in fold_metrics]),
        "rmse": _mean_std([m["rmse"] for m in fold_metrics]),
        "r2": _mean_std([m["r2"] for m in fold_metrics]),
    }


def prediction_range_diagnostics(predictions: np.ndarray) -> dict[str, Any]:
    predictions = np.asarray(predictions, dtype=float)
    if predictions.size == 0:
        return {
            "raw_min": None,
            "raw_max": None,
            "below_zero_count": 0,
            "above_one_count": 0,
        }
    return {
        "raw_min": float(np.min(predictions)),
        "raw_max": float(np.max(predictions)),
        "below_zero_count": int(np.sum(predictions < 0.0)),
        "above_one_count": int(np.sum(predictions > 1.0)),
    }


def run_grouped_evaluation(
    validated: ValidatedDataset,
    *,
    n_splits: int = DEFAULT_N_SPLITS,
    alphas: list[float] | None = None,
) -> dict[str, Any]:
    alphas = list(ALPHA_CANDIDATES if alphas is None else alphas)
    frame = validated.frame
    texts = frame[TEXT_COLUMN].astype(str).to_numpy()
    y = frame["adjudicated_exposure_score"].to_numpy(dtype=float)
    groups = frame["occupation_code"].astype(str).to_numpy()

    outer_cv = GroupKFold(n_splits=n_splits, shuffle=False)
    warnings = list(validated.warnings)
    warnings.append(LIMITATION_TEXT)

    folds: list[dict[str, Any]] = []
    oof_true: list[np.ndarray] = []
    oof_mean: list[np.ndarray] = []
    oof_median: list[np.ndarray] = []
    oof_ridge: list[np.ndarray] = []
    oof_ridge_clipped: list[np.ndarray] = []

    for fold_number, (train_idx, test_idx) in enumerate(
        outer_cv.split(texts, y, groups), start=1
    ):
        train_groups = groups[train_idx]
        test_groups = groups[test_idx]
        intersection = verify_group_disjoint(
            train_groups,
            test_groups,
            context=f"outer GroupKFold fold={fold_number}",
        )
        unique_train_groups = np.unique(train_groups)
        unique_test_groups = np.unique(test_groups)
        inner_splits = min(3, int(unique_train_groups.size))
        if inner_splits < 2:
            raise ValueError(
                f"Fold {fold_number}: inner_splits={inner_splits} < 2 "
                f"(unique training occupations={int(unique_train_groups.size)})."
            )

        y_train = y[train_idx]
        y_test = y[test_idx]
        texts_train = texts[train_idx]
        texts_test = texts[test_idx]

        selected_alpha, inner_alpha_results = select_alpha_grouped(
            texts_train,
            y_train,
            train_groups,
            alphas=alphas,
            inner_splits=inner_splits,
        )

        pipeline = build_pipeline(selected_alpha)
        if not isinstance(pipeline, Pipeline):
            raise RuntimeError("TF-IDF + Ridge must be a sklearn Pipeline.")
        fitted = clone(pipeline)
        fitted.fit(texts_train, y_train)
        raw_pred = np.asarray(fitted.predict(texts_test), dtype=float)
        clipped_pred = np.clip(raw_pred, 0.0, 1.0)

        mean_value = float(np.mean(y_train))
        median_value = float(np.median(y_train))
        mean_pred = np.full_like(y_test, mean_value, dtype=float)
        median_pred = np.full_like(y_test, median_value, dtype=float)

        mean_metrics, mean_warnings = regression_metrics(y_test, mean_pred)
        median_metrics, median_warnings = regression_metrics(y_test, median_pred)
        ridge_metrics, ridge_warnings = regression_metrics(y_test, raw_pred)
        clipped_metrics, clipped_warnings = regression_metrics(y_test, clipped_pred)
        for item in (*mean_warnings, *median_warnings, *ridge_warnings, *clipped_warnings):
            warnings.append(f"fold {fold_number}: {item}")

        folds.append(
            {
                "fold": fold_number,
                "train_row_count": int(len(train_idx)),
                "test_row_count": int(len(test_idx)),
                "train_occupation_count": int(unique_train_groups.size),
                "test_occupation_count": int(unique_test_groups.size),
                "train_occupation_codes": sorted(unique_train_groups.tolist()),
                "test_occupation_codes": sorted(unique_test_groups.tolist()),
                "occupation_intersection": intersection,
                "inner_split_count": int(inner_splits),
                "selected_alpha": selected_alpha,
                "inner_alpha_results": inner_alpha_results,
                "baseline_training_mean": mean_value,
                "baseline_training_median": median_value,
                "metrics": {
                    "global_mean": mean_metrics,
                    "global_median": median_metrics,
                    "tfidf_ridge_raw": ridge_metrics,
                    "tfidf_ridge_clipped": clipped_metrics,
                },
            }
        )
        oof_true.append(y_test)
        oof_mean.append(mean_pred)
        oof_median.append(median_pred)
        oof_ridge.append(raw_pred)
        oof_ridge_clipped.append(clipped_pred)

    y_all = np.concatenate(oof_true)
    mean_all = np.concatenate(oof_mean)
    median_all = np.concatenate(oof_median)
    ridge_all = np.concatenate(oof_ridge)
    clipped_all = np.concatenate(oof_ridge_clipped)

    pooled_mean, pooled_mean_w = regression_metrics(y_all, mean_all)
    pooled_median, pooled_median_w = regression_metrics(y_all, median_all)
    pooled_ridge, pooled_ridge_w = regression_metrics(y_all, ridge_all)
    pooled_clipped, pooled_clipped_w = regression_metrics(y_all, clipped_all)
    warnings.extend(pooled_mean_w)
    warnings.extend(pooled_median_w)
    warnings.extend(pooled_ridge_w)
    warnings.extend(pooled_clipped_w)

    method_fold_metrics = {
        "global_mean": [fold["metrics"]["global_mean"] for fold in folds],
        "global_median": [fold["metrics"]["global_median"] for fold in folds],
        "tfidf_ridge_raw": [fold["metrics"]["tfidf_ridge_raw"] for fold in folds],
        "tfidf_ridge_clipped": [fold["metrics"]["tfidf_ridge_clipped"] for fold in folds],
    }
    fold_statistics = {
        name: _summarize_method_folds(values) for name, values in method_fold_metrics.items()
    }

    raw_metrics = {
        "fold_statistics": {
            "global_mean": fold_statistics["global_mean"],
            "global_median": fold_statistics["global_median"],
            "tfidf_ridge": fold_statistics["tfidf_ridge_raw"],
        },
        "pooled_oof": {
            "global_mean": pooled_mean,
            "global_median": pooled_median,
            "tfidf_ridge": pooled_ridge,
        },
    }
    clipped_metrics = {
        "fold_statistics": {"tfidf_ridge": fold_statistics["tfidf_ridge_clipped"]},
        "pooled_oof": {"tfidf_ridge": pooled_clipped},
        "note": (
            "Clipped metrics apply np.clip(predictions, 0.0, 1.0) as a separate "
            "diagnostic. They do not replace raw Ridge results."
        ),
    }

    report = {
        "evaluator_version": EVALUATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "dataset_path": validated.summary["dataset_path"],
        "dataset_row_count": validated.summary["dataset_row_count"],
        "number_of_occupation_groups": validated.summary["number_of_occupation_groups"],
        "number_of_unique_tasks": validated.summary["number_of_unique_tasks"],
        "number_of_folds": n_splits,
        "alpha_candidates": alphas,
        "tfidf_configuration": TFIDF_CONFIGURATION,
        "model_configuration": MODEL_CONFIGURATION,
        "target_distribution": validated.summary["target_distribution"],
        "label_source_counts": validated.summary["label_source_counts"],
        "resolution_method_counts": validated.summary["resolution_method_counts"],
        "validation_summary": validated.summary,
        "folds": folds,
        "fold_statistics": fold_statistics,
        "pooled_oof_metrics": {
            "global_mean": pooled_mean,
            "global_median": pooled_median,
            "tfidf_ridge_raw": pooled_ridge,
            "tfidf_ridge_clipped": pooled_clipped,
        },
        "raw_metrics": raw_metrics,
        "clipped_metrics": clipped_metrics,
        "prediction_range": prediction_range_diagnostics(ridge_all),
        "warnings": warnings,
        "limitations": [
            LIMITATION_TEXT,
            "Schema and grouped-CV pipeline validation do not imply human validation.",
            "Outputs are contextual occupational task-exposure estimates, not "
            "personal job-loss risk, employment probability, or the probability "
            "that a user will lose their job.",
            "Ridge predictions are unconstrained; values outside [0, 1] are "
            "reported rather than silently clipped.",
        ],
        "reproducibility": {
            "group_kfold": {
                "n_splits": n_splits,
                "shuffle": False,
                "random_state": None,
            },
            "inner_alpha_search": "explicit grouped MAE search; outer test unused",
            "sklearn_pipeline": True,
            "fitted_model_persisted": False,
        },
    }
    return _json_ready(report)


def render_markdown(report: dict[str, Any]) -> str:
    dist = report["target_distribution"]
    dist_lines = "\n".join(f"- `{key}`: {value}" for key, value in dist.items())
    source_lines = "\n".join(
        f"- `{key}`: {value}" for key, value in report["label_source_counts"].items()
    )
    resolution_lines = "\n".join(
        f"- `{key}`: {value}" for key, value in report["resolution_method_counts"].items()
    )
    fold_lines = []
    for fold in report["folds"]:
        ridge = fold["metrics"]["tfidf_ridge_raw"]
        mean_m = fold["metrics"]["global_mean"]
        median_m = fold["metrics"]["global_median"]
        fold_lines.append(
            f"### Fold {fold['fold']}\n\n"
            f"- train rows: {fold['train_row_count']}; test rows: {fold['test_row_count']}\n"
            f"- train occupations: {fold['train_occupation_count']}; "
            f"test occupations: {fold['test_occupation_count']}\n"
            f"- occupation intersection: {fold['occupation_intersection']}\n"
            f"- inner splits: {fold['inner_split_count']}; selected alpha: {fold['selected_alpha']}\n"
            f"- global mean MAE/RMSE/R²: {mean_m['mae']:.6f} / {mean_m['rmse']:.6f} / {mean_m['r2']}\n"
            f"- global median MAE/RMSE/R²: {median_m['mae']:.6f} / {median_m['rmse']:.6f} / {median_m['r2']}\n"
            f"- TF-IDF+Ridge (raw) MAE/RMSE/R²: {ridge['mae']:.6f} / {ridge['rmse']:.6f} / {ridge['r2']}\n"
        )

    def _fmt_stat(block: dict[str, Any], metric: str) -> str:
        item = block[metric]
        return f"mean={item['mean']}, std={item['std']} (n={item['n']})"

    stats = report["fold_statistics"]
    pooled = report["pooled_oof_metrics"]
    pred = report["prediction_range"]
    warning_lines = "\n".join(f"- {w}" for w in report["warnings"])
    limitation_lines = "\n".join(f"- {item}" for item in report["limitations"])

    return f"""# Task-exposure grouped cross-validation (experimental)

This report is produced by an isolated experimental evaluator. It is not a
production automation-risk evaluation and does not replace production models.

{LIMITATION_TEXT}

Schema and pipeline checks do not imply human validation. The table is a
schema-validated provisional AI weak-label / deduplicated task-exposure
training table.

## Dataset

- path: `{report['dataset_path']}`
- rows: {report['dataset_row_count']}
- unique occupations: {report['number_of_occupation_groups']}
- unique tasks: {report['number_of_unique_tasks']}
- outer folds: {report['number_of_folds']}
- text column: `{report['validation_summary']['text_column_used']}`
- not_human_ground_truth all True: {report['validation_summary']['not_human_ground_truth_all_true']}

## Target distribution

{dist_lines}

## Label source

{source_lines}

## Resolution method

{resolution_lines}

Absence of the `1.00` class, if observed, is a distribution fact rather than a
validation failure.

## Configuration

- evaluator version: {report['evaluator_version']}
- schema version: {report['schema_version']}
- alpha candidates: {report['alpha_candidates']}
- TF-IDF: {json.dumps(report['tfidf_configuration'])}
- model: {json.dumps(report['model_configuration'])}
- splitter: GroupKFold(n_splits={report['number_of_folds']}, shuffle=False)

## Fold results

{''.join(fold_lines)}

## Fold statistics (mean / std across outer folds)

### Global mean baseline

- MAE: {_fmt_stat(stats['global_mean'], 'mae')}
- RMSE: {_fmt_stat(stats['global_mean'], 'rmse')}
- R²: {_fmt_stat(stats['global_mean'], 'r2')}

### Global median baseline

- MAE: {_fmt_stat(stats['global_median'], 'mae')}
- RMSE: {_fmt_stat(stats['global_median'], 'rmse')}
- R²: {_fmt_stat(stats['global_median'], 'r2')}

### TF-IDF + Ridge (raw)

- MAE: {_fmt_stat(stats['tfidf_ridge_raw'], 'mae')}
- RMSE: {_fmt_stat(stats['tfidf_ridge_raw'], 'rmse')}
- R²: {_fmt_stat(stats['tfidf_ridge_raw'], 'r2')}

### TF-IDF + Ridge (clipped diagnostic)

- MAE: {_fmt_stat(stats['tfidf_ridge_clipped'], 'mae')}
- RMSE: {_fmt_stat(stats['tfidf_ridge_clipped'], 'rmse')}
- R²: {_fmt_stat(stats['tfidf_ridge_clipped'], 'r2')}

R² means ignore undefined (null) folds; they are not replaced with zero.

## Pooled out-of-fold statistics

### Global mean

- MAE: {pooled['global_mean']['mae']}
- RMSE: {pooled['global_mean']['rmse']}
- R²: {pooled['global_mean']['r2']}

### Global median

- MAE: {pooled['global_median']['mae']}
- RMSE: {pooled['global_median']['rmse']}
- R²: {pooled['global_median']['r2']}

### TF-IDF + Ridge (raw)

- MAE: {pooled['tfidf_ridge_raw']['mae']}
- RMSE: {pooled['tfidf_ridge_raw']['rmse']}
- R²: {pooled['tfidf_ridge_raw']['r2']}

### TF-IDF + Ridge (clipped diagnostic)

- MAE: {pooled['tfidf_ridge_clipped']['mae']}
- RMSE: {pooled['tfidf_ridge_clipped']['rmse']}
- R²: {pooled['tfidf_ridge_clipped']['r2']}

Metrics are reported without ranking a method as successful from a single score.

## Prediction-range diagnostics (raw Ridge OOF)

- min: {pred['raw_min']}
- max: {pred['raw_max']}
- below 0: {pred['below_zero_count']}
- above 1: {pred['above_one_count']}

Raw predictions are not clipped for the primary metrics.

## Warnings

{warning_lines}

## Limitations

{limitation_lines}
"""


def write_reports(report: dict[str, Any], report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "task_exposure_grouped_cv.json"
    md_path = report_dir / "task_exposure_grouped_cv.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def evaluate_and_write(
    dataset_path: Path | None = None,
    report_dir: Path | None = None,
    *,
    n_splits: int = DEFAULT_N_SPLITS,
) -> dict[str, Any]:
    dataset_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    report_dir = Path(report_dir) if report_dir else DEFAULT_REPORT_DIR
    validated = load_and_validate_dataset(dataset_path, n_splits=n_splits)
    report = run_grouped_evaluation(validated, n_splits=n_splits)
    json_path, md_path = write_reports(report, report_dir)
    report["written_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--n-splits", type=int, default=DEFAULT_N_SPLITS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = evaluate_and_write(args.dataset, args.report_dir, n_splits=args.n_splits)
    json_path = report["written_paths"]["json"]
    md_path = report["written_paths"]["markdown"]
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "rows={dataset_row_count} occupations={number_of_occupation_groups} "
        "tasks={number_of_unique_tasks}".format(**report)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
