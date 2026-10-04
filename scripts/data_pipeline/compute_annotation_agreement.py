#!/usr/bin/env python3
"""Compute agreement after human ratings exist. Refuses empty or invented-looking files."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import BASE_DIR, markdown_table, utc_now

LABELS = BASE_DIR / "project_data" / "task_exposure_labels"
REVIEWER_1 = LABELS / "annotation_reviewer1.csv"
REVIEWER_2 = LABELS / "annotation_reviewer2.csv"
SAMPLE = LABELS / "task_exposure_250_sample.csv"
DISCREPANT = LABELS / "discrepant_tasks_for_adjudication.csv"
MERGED = LABELS / "task_exposure_250_ratings_merged.csv"
REPORT = BASE_DIR / "reports" / "data_quality" / "task_exposure_250_agreement_report.md"
ALLOWED = (0.0, 0.25, 0.5, 0.75, 1.0)
SCORE_MAP = {0.0: 0, 0.25: 1, 0.5: 2, 0.75: 3, 1.0: 4}
DISCREPANCY = 0.30


def parse_score(value: object) -> float | None:
    text = "" if value is None else str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    number = float(text)
    if number not in ALLOWED:
        raise ValueError(
            f"score {number} is not an allowed logical value {ALLOWED}. "
            "Do not replace a blank with 0.00 unless that is the reviewer's chosen score."
        )
    return number


def snap_to_logical(value: float) -> float:
    return min(ALLOWED, key=lambda allowed: (abs(allowed - value), allowed))


def gwet_ac1(y1: np.ndarray, y2: np.ndarray, categories: list[int]) -> float:
    n = len(y1)
    if n == 0:
        return float("nan")
    po = float(np.mean(y1 == y2))
    q = len(categories)
    pk = np.array([((y1 == k).mean() + (y2 == k).mean()) / 2 for k in categories])
    pe = sum(pk[i] * (1 - pk[i]) for i in range(q)) / (q - 1) if q > 1 else 0.0
    if abs(1 - pe) < 1e-12:
        return float("nan")
    return (po - pe) / (1 - pe)


def main() -> int:
    if not REVIEWER_1.exists() or not REVIEWER_2.exists():
        print("Reviewer worksheets are missing.")
        return 1
    r1 = pd.read_csv(REVIEWER_1, dtype=str, keep_default_na=False)
    r2 = pd.read_csv(REVIEWER_2, dtype=str, keep_default_na=False)
    r1_ids = set(r1.get("reviewer_1_id", pd.Series(dtype=str)).astype(str).str.strip())
    r2_ids = set(r2.get("reviewer_2_id", pd.Series(dtype=str)).astype(str).str.strip())
    if r1_ids & {"ai_pass_1", "ai_pass1"} or r2_ids & {"ai_pass_2", "ai_pass2"}:
        print(
            "Refusing: worksheets are AI scoring passes, not human ratings. "
            "Do not write human_consensus labels. "
            "Use scripts/data_pipeline/build_final_task_training_table.py."
        )
        return 3
    if "task_id" not in r1.columns or "task_id" not in r2.columns:
        print("Both worksheets must contain task_id.")
        return 1
    merged = r1.merge(r2[["task_id", "reviewer_2_score"]], on="task_id", how="inner", suffixes=("", "_r2"))
    if "reviewer_2_score_r2" in merged.columns:
        merged["reviewer_2_score"] = merged["reviewer_2_score_r2"]
    try:
        merged["reviewer_1_score_num"] = merged["reviewer_1_score"].map(parse_score)
        merged["reviewer_2_score_num"] = merged["reviewer_2_score"].map(parse_score)
    except ValueError as error:
        print(error)
        return 1
    complete = merged["reviewer_1_score_num"].notna() & merged["reviewer_2_score_num"].notna()
    n_complete = int(complete.sum())
    if n_complete < 250:
        print(
            f"Refusing agreement metrics: {n_complete}/250 rows have both reviewer scores. "
            "Do not invent labels. Complete both worksheets first."
        )
        return 2
    y1_scores = merged.loc[complete, "reviewer_1_score_num"].to_numpy()
    y2_scores = merged.loc[complete, "reviewer_2_score_num"].to_numpy()
    y1 = pd.Series(y1_scores).map(SCORE_MAP).to_numpy()
    y2 = pd.Series(y2_scores).map(SCORE_MAP).to_numpy()
    if pd.isna(y1).any() or pd.isna(y2).any():
        print("A complete score could not be mapped to the 5-point rubric.")
        return 1
    kappa = float(cohen_kappa_score(y1, y2, weights="quadratic"))
    mad = float(np.mean(np.abs(y1_scores - y2_scores)))
    ac1 = float(gwet_ac1(y1.astype(int), y2.astype(int), list(range(5))))
    merged["score_diff"] = np.abs(merged["reviewer_1_score_num"] - merged["reviewer_2_score_num"])
    discrepant = merged[merged["score_diff"] > DISCREPANCY].copy()
    agreed = merged[merged["score_diff"] <= DISCREPANCY].copy()
    raw_mean = (agreed["reviewer_1_score_num"] + agreed["reviewer_2_score_num"]) / 2
    merged.loc[agreed.index, "consensus_mean"] = raw_mean
    merged.loc[agreed.index, "adjudicated_exposure_score"] = raw_mean.map(snap_to_logical)
    merged.loc[agreed.index, "label_confidence"] = 1.0 - (agreed["score_diff"] * 0.5)
    merged.loc[agreed.index, "label_source"] = "human_consensus_logical_value"
    merged.loc[discrepant.index, "consensus_mean"] = ""
    merged.loc[discrepant.index, "adjudicated_exposure_score"] = ""
    merged.loc[discrepant.index, "label_source"] = "needs_human_adjudication"
    merged.loc[discrepant.index, "label_confidence"] = ""
    merged.to_csv(MERGED, index=False)
    discrepant.to_csv(DISCREPANT, index=False)
    gate = "high_agreement_average_non_discrepant" if kappa >= 0.70 else "adjudicate_all_discrepant_and_refine_rubric"
    report = [
        "# Task-exposure 250-sample agreement report",
        "",
        f"Generated at: {utc_now()}",
        "",
        f"- Quadratic weighted kappa: {kappa:.4f}",
        f"- Gwet AC1: {ac1:.4f}",
        f"- Mean absolute difference: {mad:.4f}",
        f"- Complete paired rows: {n_complete}/250",
        f"- Discrepant rows (|r1-r2| > {DISCREPANCY}): {len(discrepant)}",
        f"- Decision tree branch: `{gate}`",
        "",
        "Adjudicated scores for discrepant rows were left blank for a human session.",
        "Do not treat this file as production ground truth until adjudication is finished.",
        "",
        markdown_table(
            ["metric", "value"],
            [
                ["quadratic_kappa", f"{kappa:.4f}"],
                ["gwet_ac1", f"{ac1:.4f}"],
                ["mad", f"{mad:.4f}"],
                ["discrepant_rows", len(discrepant)],
            ],
        ),
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Quadratic Weighted Kappa: {kappa:.4f}")
    print(f"Gwet AC1: {ac1:.4f}")
    print(f"Mean Absolute Difference: {mad:.4f}")
    print(f"Total Discrepancy Rows Needing Adjudication: {len(discrepant)}")
    print(f"Decision tree: {gate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
