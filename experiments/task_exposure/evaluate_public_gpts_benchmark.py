#!/usr/bin/env python3
"""Occupation-grouped classification on the public GPTs-are-GPTs benchmark.

Does not train production models and does not use GPT-4 fields as the target.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from public_benchmark_common import (  # noqa: E402
    ALLOWED_HUMAN_LABELS,
    C_CANDIDATES,
    CLAIM_BOUNDARY,
    DERIVED_CSV,
    GPT_FIELDS,
    N_SPLITS,
    REPORT_DIR,
    SPLIT_SEED,
    TARGET_FIELD,
    TEXT_COLUMN,
    TFIDF_CONFIGURATION,
    PublicBenchmarkError,
    json_ready,
    package_versions,
    sha256_file,
    text_features_exclude_targets,
    utc_now,
    verify_group_disjoint,
    write_json,
    write_md,
)

CLASSES = list(ALLOWED_HUMAN_LABELS)


def load_labelled() -> pd.DataFrame:
    frame = pd.read_csv(DERIVED_CSV, dtype=str, keep_default_na=False)
    unexpected = sorted({v for v in frame[TARGET_FIELD].unique() if v not in CLASSES})
    if unexpected:
        raise PublicBenchmarkError(f"unexpected labels in derived table {unexpected}")
    text_features_exclude_targets([TEXT_COLUMN])
    return frame


def make_tfidf() -> TfidfVectorizer:
    return TfidfVectorizer(**TFIDF_CONFIGURATION)


def make_logreg(C: float) -> Pipeline:
    return Pipeline(
        [
            ("tfidf", make_tfidf()),
            (
                "clf",
                LogisticRegression(
                    C=C,
                    max_iter=2000,
                    solver="lbfgs",
                    random_state=SPLIT_SEED,
                ),
            ),
        ]
    )


def make_svm(C: float) -> Pipeline:
    return Pipeline(
        [
            ("tfidf", make_tfidf()),
            (
                "clf",
                LinearSVC(C=C, max_iter=8000, random_state=SPLIT_SEED, dual="auto"),
            ),
        ]
    )


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba=None, labels=CLASSES) -> dict:
    report = classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )
    per_class = {}
    for label in labels:
        row = report.get(label, {})
        per_class[label] = {
            "precision": float(row.get("precision", 0.0)),
            "recall": float(row.get("recall", 0.0)),
            "f1": float(row.get("f1-score", 0.0)),
            "support": int(row.get("support", 0)),
        }
    result = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", labels=labels, zero_division=0)),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "test_task_count": int(len(y_true)),
        "test_class_distribution": pd.Series(y_true).value_counts().reindex(labels).fillna(0).astype(int).to_dict(),
    }
    if y_proba is None:
        result["log_loss"] = {
            "status": "unavailable",
            "reason": "estimator does not provide class probabilities",
        }
        result["multiclass_roc_auc"] = {
            "status": "unavailable",
            "reason": "estimator does not provide class probabilities",
        }
    else:
        result["log_loss"] = float(log_loss(y_true, y_proba, labels=labels))
        if len(set(y_true)) < 2:
            result["multiclass_roc_auc"] = {
                "status": "undefined",
                "reason": "fewer than two classes present in y_true",
            }
        else:
            result["multiclass_roc_auc"] = float(
                roc_auc_score(y_true, y_proba, multi_class="ovr", average="macro", labels=labels)
            )
    return result


def grouped_cv(pipeline: Pipeline, texts, y, groups, n_splits=N_SPLITS) -> dict:
    unique_groups = np.unique(groups)
    splits = min(n_splits, int(len(unique_groups)))
    if splits < 2:
        raise PublicBenchmarkError("not enough occupations for grouped CV")
    cv = GroupKFold(n_splits=splits)
    rows = []
    for fold, (train_idx, val_idx) in enumerate(cv.split(texts, y, groups), start=1):
        verify_group_disjoint(groups[train_idx], groups[val_idx])
        model = clone(pipeline)
        model.fit(texts[train_idx], y[train_idx])
        pred = model.predict(texts[val_idx])
        metrics = classification_metrics(y[val_idx], pred)
        rows.append(
            {
                "fold": fold,
                "accuracy": metrics["accuracy"],
                "balanced_accuracy": metrics["balanced_accuracy"],
                "macro_f1": metrics["macro_f1"],
                "weighted_f1": metrics["weighted_f1"],
                "mcc": metrics["mcc"],
                "n_train_occupations": int(len(set(groups[train_idx]))),
                "n_val_occupations": int(len(set(groups[val_idx]))),
            }
        )
        vectorizer = model.named_steps["tfidf"]
        val_tokens = " ".join(texts[val_idx]).split()
        held_out = [tok for tok in val_tokens if tok.startswith("zzleak")]
        if held_out and any(tok in vectorizer.vocabulary_ for tok in held_out):
            raise PublicBenchmarkError("TF-IDF leakage of held-out synthetic tokens")
    frame = pd.DataFrame(rows)
    summary = {metric: {"mean": float(frame[metric].mean()), "std": float(frame[metric].std(ddof=0))} for metric in (
        "accuracy",
        "balanced_accuracy",
        "macro_f1",
        "weighted_f1",
        "mcc",
    )}
    return {"folds": rows, "summary": summary}


def select_C(factory, texts, y, groups) -> tuple[float, dict]:
    scores = []
    for C in C_CANDIDATES:
        cv = grouped_cv(factory(C), texts, y, groups)
        scores.append({"C": C, "macro_f1_mean": cv["summary"]["macro_f1"]["mean"], "cv": cv})
    best = max(scores, key=lambda item: item["macro_f1_mean"])
    return float(best["C"]), {"candidates": scores, "selected_C": best["C"]}


def top_features(pipeline: Pipeline, k: int = 15) -> dict:
    vectorizer: TfidfVectorizer = pipeline.named_steps["tfidf"]
    clf = pipeline.named_steps["clf"]
    names = np.array(vectorizer.get_feature_names_out())
    coef = clf.coef_
    classes = list(clf.classes_)
    out = {}
    for index, label in enumerate(classes):
        weights = coef[index]
        order = np.argsort(weights)
        positive = order[-k:][::-1]
        negative = order[:k]
        out[label] = {
            "associated_with_class": [
                {"feature": str(names[i]), "weight": float(weights[i])} for i in positive
            ],
            "associated_against_class": [
                {"feature": str(names[i]), "weight": float(weights[i])} for i in negative
            ],
        }
    return out


def soc_metrics(frame: pd.DataFrame, y_true, y_pred) -> pd.DataFrame:
    tmp = frame.copy()
    tmp["y_true"] = y_true
    tmp["y_pred"] = y_pred
    rows = []
    for soc, part in tmp.groupby("soc_major_group"):
        n = int(len(part))
        row = {
            "soc_major_group": soc,
            "n_tasks": n,
            "n_occupations": int(part["occupation_code"].nunique()),
        }
        if n < 20:
            row["note"] = "small_group_descriptive_only"
        row["accuracy"] = float(accuracy_score(part["y_true"], part["y_pred"]))
        row["macro_f1"] = float(
            f1_score(part["y_true"], part["y_pred"], average="macro", labels=CLASSES, zero_division=0)
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("n_tasks", ascending=False)


def occupation_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for occ, part in frame.groupby("occupation_code"):
        counts = part[TARGET_FIELD].value_counts()
        n = int(len(part))
        rows.append(
            {
                "occupation_code": occ,
                "occupation_title": part["occupation_title"].iloc[0],
                "task_count": n,
                "E0_proportion": float(counts.get("E0", 0) / n),
                "E1_proportion": float(counts.get("E1", 0) / n),
                "E2_proportion": float(counts.get("E2", 0) / n),
                "dominant_category": str(counts.idxmax()),
            }
        )
    return pd.DataFrame(rows)


def metric_line(name: str, metrics: dict) -> str:
    return (
        f"- {name}: accuracy={metrics['accuracy']:.4f}; balanced_accuracy={metrics['balanced_accuracy']:.4f}; "
        f"macro-F1={metrics['macro_f1']:.4f}; weighted-F1={metrics['weighted_f1']:.4f}; MCC={metrics['mcc']:.4f}"
    )


def main() -> int:
    frame = load_labelled()
    train = frame[frame["split"] == "train"].copy()
    val = frame[frame["split"] == "validation"].copy()
    test = frame[frame["split"] == "test"].copy()
    verify_group_disjoint(train["occupation_code"].to_numpy(), val["occupation_code"].to_numpy())
    verify_group_disjoint(train["occupation_code"].to_numpy(), test["occupation_code"].to_numpy())
    verify_group_disjoint(val["occupation_code"].to_numpy(), test["occupation_code"].to_numpy())
    x_train = train[TEXT_COLUMN].to_numpy()
    y_train = train[TARGET_FIELD].to_numpy()
    g_train = train["occupation_code"].to_numpy()
    x_test = test[TEXT_COLUMN].to_numpy()
    y_test = test[TARGET_FIELD].to_numpy()

    majority = DummyClassifier(strategy="most_frequent")
    majority.fit(x_train, y_train)
    majority_pred = majority.predict(x_test)
    majority_metrics = classification_metrics(y_test, majority_pred)

    dummy = DummyClassifier(strategy="stratified", random_state=SPLIT_SEED)
    dummy.fit(x_train, y_train)
    dummy_pred = dummy.predict(x_test)
    dummy_metrics = classification_metrics(y_test, dummy_pred)

    log_C, log_search = select_C(make_logreg, x_train, y_train, g_train)
    svm_C, svm_search = select_C(make_svm, x_train, y_train, g_train)

    logreg = make_logreg(log_C)
    logreg.fit(x_train, y_train)
    log_pred = logreg.predict(x_test)
    log_proba = logreg.predict_proba(x_test)
    log_metrics = classification_metrics(y_test, log_pred, log_proba)
    log_metrics["test_occupation_count"] = int(test["occupation_code"].nunique())

    svm = make_svm(svm_C)
    svm.fit(x_train, y_train)
    svm_pred = svm.predict(x_test)
    svm_metrics = classification_metrics(y_test, svm_pred)
    svm_metrics["test_occupation_count"] = int(test["occupation_code"].nunique())

    val_pred = logreg.predict(val[TEXT_COLUMN].to_numpy())
    val_metrics = classification_metrics(val[TARGET_FIELD].to_numpy(), val_pred)
    val_metrics["note"] = "validation occupations unused for hyperparameter selection"

    soc = soc_metrics(test, y_test, log_pred)
    soc.to_csv(REPORT_DIR / "soc_group_metrics.csv", index=False)
    per_class_rows = []
    for model_name, metrics in (
        ("majority", majority_metrics),
        ("dummy_stratified", dummy_metrics),
        ("tfidf_logreg", log_metrics),
        ("tfidf_linearsvm", svm_metrics),
    ):
        for label, values in metrics["per_class"].items():
            per_class_rows.append({"model": model_name, "class": label, **values})
    pd.DataFrame(per_class_rows).to_csv(REPORT_DIR / "per_class_metrics.csv", index=False)
    pd.DataFrame(log_metrics["confusion_matrix"], index=CLASSES, columns=CLASSES).to_csv(
        REPORT_DIR / "confusion_matrix.csv"
    )
    occupation_summary(frame).to_csv(REPORT_DIR / "occupation_level_descriptive_summary.csv", index=False)

    payload = {
        "generated_at": utc_now(),
        "target": TARGET_FIELD,
        "classes": CLASSES,
        "gpt_fields_excluded_from_target": list(GPT_FIELDS),
        "tfidf": {k: list(v) if isinstance(v, tuple) else v for k, v in TFIDF_CONFIGURATION.items()},
        "split_seed": SPLIT_SEED,
        "hyperparameter_selection": {
            "group": "occupation_code",
            "method": "GroupKFold_macro_f1_on_train_occupations_only",
            "C_candidates": C_CANDIDATES,
            "logreg_selected_C": log_C,
            "linearsvm_selected_C": svm_C,
            "test_not_used": True,
            "validation_not_used_for_selection": True,
        },
        "class_distribution_full": frame[TARGET_FIELD].value_counts().sort_index().to_dict(),
        "majority_baseline": majority_metrics,
        "dummy_stratified_baseline": dummy_metrics,
        "tfidf_logistic_regression": {
            **log_metrics,
            "grouped_cv_train": log_search["candidates"][
                [item["C"] for item in log_search["candidates"]].index(log_C)
            ]["cv"],
            "top_features_associated_with_predictions": top_features(logreg),
        },
        "tfidf_linear_svm": {
            **svm_metrics,
            "grouped_cv_train": svm_search["candidates"][
                [item["C"] for item in svm_search["candidates"]].index(svm_C)
            ]["cv"],
            "top_features_associated_with_predictions": top_features(svm),
        },
        "validation_logreg_unused_for_selection": val_metrics,
        "leakage": {
            "occupation_leakage": False,
            "tfidf_leakage": False,
            "target_leakage": False,
            "hyperparameter_test_leakage": False,
        },
        "package_versions": package_versions(),
        "derived_dataset_sha256": sha256_file(DERIVED_CSV),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    write_json(REPORT_DIR / "model_evaluation.json", payload)
    write_md(
        REPORT_DIR / "model_evaluation.md",
        [
            "# Public benchmark model evaluation",
            "",
            CLAIM_BOUNDARY,
            "",
            "Target: `human_labels` in E0 / E1 / E2. GPT-4 fields were not used as the target.",
            "TF-IDF is fitted inside sklearn Pipelines on training occupations only.",
            "Hyperparameters were selected with GroupKFold on training occupations; the test occupation set was not used.",
            "",
            metric_line("Majority baseline", majority_metrics),
            metric_line("Stratified dummy baseline", dummy_metrics),
            metric_line(f"TF-IDF + Logistic Regression (C={log_C})", log_metrics),
            metric_line(f"TF-IDF + Linear SVM (C={svm_C})", svm_metrics),
            "",
            "Per-class metrics and the confusion matrix are in CSV sidecars.",
            "Linear-model n-grams are features associated with model predictions, not causal determinants of exposure.",
            "Occupation-level summaries are descriptive category shares, not Prayash 0–1 scores and not personal risk.",
            "",
            "```text",
            "Occupation leakage: false",
            "TF-IDF leakage: false",
            "Target leakage: false",
            "Hyperparameter/test leakage: false",
            "```",
            "",
        ],
    )
    print(json.dumps(json_ready({
        "logreg_C": log_C,
        "svm_C": svm_C,
        "logreg_macro_f1": log_metrics["macro_f1"],
        "svm_macro_f1": svm_metrics["macro_f1"],
        "majority_macro_f1": majority_metrics["macro_f1"],
        "test_tasks": int(len(test)),
        "test_occupations": int(test["occupation_code"].nunique()),
    }), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
