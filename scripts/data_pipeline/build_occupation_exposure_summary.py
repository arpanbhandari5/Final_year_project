#!/usr/bin/env python3
"""Occupation-level summaries from human-adjudicated task scores only."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_dataset_common import LABELS

SOURCE = LABELS / "task_exposure_human_round1_trainable.csv"
OUT = LABELS / "occupation_task_exposure_summary.csv"


def main() -> int:
    if not SOURCE.exists():
        print(f"No trainable human table at {SOURCE}. Nothing to aggregate.")
        return 0
    df = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    if "adjudicated_exposure_score" not in df.columns:
        print("Missing adjudicated_exposure_score")
        return 1
    scores = pd.to_numeric(df["adjudicated_exposure_score"], errors="coerce")
    if scores.notna().sum() == 0:
        print("Trainable table has no numeric adjudicated scores. Refusing to invent summaries.")
        return 0
    work = df.loc[scores.notna()].copy()
    work["score"] = scores.loc[scores.notna()]
    rows = []
    for occ, g in work.groupby("occupation_code"):
        n = int(len(g))
        s = g["score"]
        coverage = "low" if n <= 1 else ("moderate" if n < 5 else "higher")
        rows.append(
            {
                "occupation_code": occ,
                "occupation_title": g["occupation_title"].iloc[0] if "occupation_title" in g.columns else "",
                "reviewed_task_count": n,
                "mean_task_exposure": float(s.mean()),
                "median_task_exposure": float(s.median()),
                "minimum_task_exposure": float(s.min()),
                "maximum_task_exposure": float(s.max()),
                "standard_deviation": float(s.std(ddof=1)) if n > 1 else "",
                "p25_task_exposure": float(s.quantile(0.25)),
                "p75_task_exposure": float(s.quantile(0.75)),
                "high_exposure_task_fraction": float((s >= 0.75).mean()),
                "low_exposure_task_fraction": float((s <= 0.25).mean()),
                "evidence_coverage": coverage,
                "label_status": "adjudicated_human",
                "interpretation": "contextual task-exposure estimate",
            }
        )
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(rows)} occupations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
