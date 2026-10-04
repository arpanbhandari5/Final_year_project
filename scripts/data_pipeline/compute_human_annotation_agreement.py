#!/usr/bin/env python3
"""Human-track agreement. Refuses to compute kappa on blank or AI worksheets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import utc_now
from human_dataset_common import ALLOWED_SCORES, LABELS, REPORTS

R1 = LABELS / "task_exposure_human_round1_reviewer1.csv"
R2 = LABELS / "task_exposure_human_round1_reviewer2.csv"
R3 = LABELS / "task_exposure_human_round1_third_reviewer.csv"
MERGED = LABELS / "task_exposure_human_round1_ratings_merged.csv"
UNRESOLVED = LABELS / "task_exposure_human_round1_unresolved.csv"
TRAINABLE = LABELS / "task_exposure_human_round1_trainable.csv"
REPORT = REPORTS / "task_exposure_human_round1_agreement_report.md"
STATS = REPORTS / "task_exposure_human_round1_agreement_stats.json"


def parse_score(value: object) -> float | None:
    text = "" if value is None else str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    number = float(text)
    if number not in ALLOWED_SCORES:
        raise ValueError(f"score {number} is not allowed {ALLOWED_SCORES}")
    return number


def snap(value: float) -> float:
    return min(ALLOWED_SCORES, key=lambda allowed: (abs(allowed - value), allowed))


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not R1.exists() or not R2.exists():
        print("Round-1 reviewer worksheets missing.")
        return 1
    r1 = pd.read_csv(R1, dtype=str, keep_default_na=False)
    r2 = pd.read_csv(R2, dtype=str, keep_default_na=False)
    merged = r1.merge(
        r2[["task_id", "reviewer_score"]].rename(columns={"reviewer_score": "reviewer_2_score"}),
        on="task_id",
        how="inner",
    )
    merged = merged.rename(columns={"reviewer_score": "reviewer_1_score"})
    if R3.exists():
        r3 = pd.read_csv(R3, dtype=str, keep_default_na=False)
        merged = merged.merge(
            r3[["task_id", "reviewer_score"]].rename(columns={"reviewer_score": "third_reviewer_score"}),
            on="task_id",
            how="left",
        )
    else:
        merged["third_reviewer_score"] = ""
    if "adjudicated_exposure_score" not in merged.columns:
        merged["adjudicated_exposure_score"] = ""
    s1 = merged["reviewer_1_score"].map(parse_score)
    s2 = merged["reviewer_2_score"].map(parse_score)
    n_scored = int((s1.notna() & s2.notna()).sum())
    stats = {
        "generated_at": utc_now(),
        "paired_rows": int(len(merged)),
        "paired_human_scores": n_scored,
        "exact_agreement": None,
        "quadratic_weighted_kappa": None,
        "mean_absolute_disagreement": None,
        "third_reviewer_file_rows": int(len(pd.read_csv(R3))) if R3.exists() else 0,
        "trainable_rows": 0,
        "unresolved_rows": 0,
        "note": "AI dual-pass kappa is not human IRR.",
    }
    if n_scored == 0:
        stats["note"] += " No human scores present; kappa not computed; no training table written."
        STATS.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
        REPORT.write_text(
            "\n".join(
                [
                    "# Human Round-1 agreement",
                    "",
                    "No paired human scores yet. Kappa was not computed.",
                    "Do not treat AI-pass quadratic kappa 0.912 as human inter-rater reliability.",
                    "Unresolved and blank rows are excluded from training.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print("No human scores; agreement deferred.")
        return 0

    pair = merged.loc[s1.notna() & s2.notna()].copy()
    pair["s1"] = s1
    pair["s2"] = s2
    pair["abs_diff"] = (pair["s1"] - pair["s2"]).abs()
    exact = int((pair["s1"] == pair["s2"]).sum())
    y1 = pair["s1"].map({0.0: 0, 0.25: 1, 0.5: 2, 0.75: 3, 1.0: 4}).to_numpy()
    y2 = pair["s2"].map({0.0: 0, 0.25: 1, 0.5: 2, 0.75: 3, 1.0: 4}).to_numpy()
    kappa = float(cohen_kappa_score(y1, y2, weights="quadratic"))
    mae = float(pair["abs_diff"].mean())
    adj = []
    unresolved = []
    for _, row in pair.iterrows():
        diff = float(row["abs_diff"])
        rec = row.to_dict()
        if diff == 0:
            rec["adjudicated_exposure_score"] = f"{row['s1']:.2f}"
            rec["agreement_status"] = "exact_agreement"
            rec["adjudication_reason"] = "identical_scores"
            adj.append(rec)
        elif abs(diff - 0.25) < 1e-9:
            rec["adjudicated_exposure_score"] = f"{snap((row['s1'] + row['s2']) / 2):.2f}"
            rec["agreement_status"] = "one_level_mean_snap"
            rec["adjudication_reason"] = "difference_0.25_mean_snap_tie_lower"
            adj.append(rec)
        else:
            rec["adjudicated_exposure_score"] = ""
            rec["agreement_status"] = "needs_third_reviewer"
            rec["adjudication_reason"] = "difference_ge_0.50_or_uncertain"
            unresolved.append(rec)
    trainable = pd.DataFrame(adj)
    unres = pd.DataFrame(unresolved)
    trainable.to_csv(TRAINABLE, index=False)
    unres.to_csv(UNRESOLVED, index=False)
    pair.to_csv(MERGED, index=False)
    stats.update(
        {
            "exact_agreement": exact / len(pair),
            "quadratic_weighted_kappa": kappa,
            "mean_absolute_disagreement": mae,
            "trainable_rows": int(len(trainable)),
            "unresolved_rows": int(len(unres)),
            "score_distribution_reviewer_1": pair["s1"].value_counts().sort_index().to_dict(),
            "score_distribution_reviewer_2": pair["s2"].value_counts().sort_index().to_dict(),
        }
    )
    STATS.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        f"# Human Round-1 agreement\n\nPaired scores {len(pair)}. Exact agreement {stats['exact_agreement']}. "
        f"Quadratic weighted kappa {kappa:.3f}. MAE disagreement {mae:.3f}. "
        f"Trainable {len(trainable)}; unresolved excluded from training {len(unres)}.\n",
        encoding="utf-8",
    )
    print(json.dumps({k: stats[k] for k in ("paired_human_scores", "trainable_rows", "unresolved_rows")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
