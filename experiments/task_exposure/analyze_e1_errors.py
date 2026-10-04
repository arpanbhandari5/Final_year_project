"""Read-only E1 error analysis for the preserved public-benchmark reports.

Does not retrain, relabel, or overwrite model_evaluation.md / .json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "experiments" / "task_exposure" / "data" / "public_benchmark" / "public_gpts_are_gpts_benchmark.csv"
CONFUSION = ROOT / "experiments" / "task_exposure" / "reports" / "public_benchmark" / "confusion_matrix.csv"
PER_CLASS = ROOT / "experiments" / "task_exposure" / "reports" / "public_benchmark" / "per_class_metrics.csv"
SOC = ROOT / "experiments" / "task_exposure" / "reports" / "public_benchmark" / "soc_group_metrics.csv"
OUT_MD = ROOT / "experiments" / "task_exposure" / "reports" / "public_benchmark" / "e1_error_analysis.md"
OUT_JSON = ROOT / "experiments" / "task_exposure" / "reports" / "public_benchmark" / "e1_error_analysis.json"


def main() -> None:
    confusion = pd.read_csv(CONFUSION, index_col=0)
    # rows = true class labels in file header index
    e1_true_e0 = int(confusion.loc["E1", "E0"])
    e1_true_e1 = int(confusion.loc["E1", "E1"])
    e1_true_e2 = int(confusion.loc["E1", "E2"])
    e0_pred_e1 = int(confusion.loc["E0", "E1"])
    e2_pred_e1 = int(confusion.loc["E2", "E1"])
    support = e1_true_e0 + e1_true_e1 + e1_true_e2
    fn = e1_true_e0 + e1_true_e2
    fp = e0_pred_e1 + e2_pred_e1

    per_class = pd.read_csv(PER_CLASS)
    logreg_e1 = per_class[(per_class["model"] == "tfidf_logreg") & (per_class["class"] == "E1")].iloc[0]

    frame = pd.read_csv(BENCH, dtype=str)
    labels = frame["human_labels"].str.strip().str.upper()
    text = frame["task_text"].fillna("")
    lengths = text.str.len()
    by_class = {
        cls: {
            "n": int((labels == cls).sum()),
            "mean_chars": float(lengths[labels == cls].mean()) if (labels == cls).any() else None,
            "median_chars": float(lengths[labels == cls].median()) if (labels == cls).any() else None,
        }
        for cls in ("E0", "E1", "E2")
    }
    exact_dupes = int(text.duplicated().sum())
    norm = text.str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    norm_dupes = int(norm.duplicated().sum())

    soc = pd.read_csv(SOC)
    weak = soc.sort_values("macro_f1").head(5)

    payload = {
        "source_confusion_matrix": str(CONFUSION),
        "test_e1_support": support,
        "full_benchmark_e1_count": by_class["E1"]["n"],
        "e1_true_predicted_e0": e1_true_e0,
        "e1_true_predicted_e1": e1_true_e1,
        "e1_true_predicted_e2": e1_true_e2,
        "e1_false_negatives": fn,
        "e0_predicted_e1": e0_pred_e1,
        "e2_predicted_e1": e2_pred_e1,
        "e1_false_positives": fp,
        "logreg_e1_precision": float(logreg_e1["precision"]),
        "logreg_e1_recall": float(logreg_e1["recall"]),
        "logreg_e1_f1": float(logreg_e1["f1"]),
        "class_imbalance_full": {cls: by_class[cls]["n"] for cls in by_class},
        "task_length_chars": by_class,
        "duplicate_task_text_rows": exact_dupes,
        "normalized_duplicate_task_text_rows": norm_dupes,
        "lowest_macro_f1_soc_major_groups": weak.to_dict(orient="records"),
        "row_level_predictions_archived": False,
        "relabelled": False,
        "note": (
            "Row-level test predictions were not archived next to the confusion matrix. "
            "Occupation-group E1 rates and example misclassified task strings cannot be "
            "listed without retraining. This analysis uses the preserved confusion matrix, "
            "per-class CSV, SOC-group metrics, and full benchmark text statistics only."
        ),
        "future_experiments_not_run": [
            "class weights",
            "character n-grams",
            "word plus character features",
            "additional independent labels",
            "probability calibration",
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# E1 error analysis (read-only)",
        "",
        "Does not retrain the public-benchmark classifier. Does not invent labels.",
        "",
        "## Test-set confusion (TF-IDF + Logistic Regression, preserved matrix)",
        "",
        f"- E1 support (test): {support}",
        f"- E1 correct: {e1_true_e1}",
        f"- E1 predicted as E0 (false negatives toward E0): {e1_true_e0}",
        f"- E1 predicted as E2 (false negatives toward E2): {e1_true_e2}",
        f"- E0 predicted as E1 (false positives from E0): {e0_pred_e1}",
        f"- E2 predicted as E1 (false positives from E2): {e2_pred_e1}",
        f"- E1 false negatives total: {fn}",
        f"- E1 false positives total: {fp}",
        f"- Logistic Regression E1 precision/recall/F1: {float(logreg_e1['precision']):.3f} / {float(logreg_e1['recall']):.3f} / {float(logreg_e1['f1']):.3f}",
        "",
        "E1 performance is weaker than E0 and E2 in the reported evaluation. This is an observed metric pattern, not a causal claim.",
        "",
        "## Class imbalance (full 19,265-row benchmark)",
        "",
        f"- E0: {by_class['E0']['n']}",
        f"- E1: {by_class['E1']['n']}",
        f"- E2: {by_class['E2']['n']}",
        "",
        "## Task length (characters, full benchmark)",
        "",
        f"- E0 mean/median: {by_class['E0']['mean_chars']:.1f} / {by_class['E0']['median_chars']:.1f}",
        f"- E1 mean/median: {by_class['E1']['mean_chars']:.1f} / {by_class['E1']['median_chars']:.1f}",
        f"- E2 mean/median: {by_class['E2']['mean_chars']:.1f} / {by_class['E2']['median_chars']:.1f}",
        "",
        f"- Duplicate task_text rows: {exact_dupes}",
        f"- Duplicate normalized task_text rows: {norm_dupes}",
        "",
        "## SOC major groups with lowest preserved macro-F1",
        "",
        "| soc_major_group | n_tasks | n_occupations | accuracy | macro_f1 |",
        "|---|---|---|---|---|",
    ]
    for row in weak.itertuples(index=False):
        lines.append(
            f"| {row.soc_major_group} | {row.n_tasks} | {row.n_occupations} | {row.accuracy:.3f} | {row.macro_f1:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Limitation",
            "",
            payload["note"],
            "",
            "Recommended future experiments (not executed here): class weights; character n-grams; additional independent labels; calibration.",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
