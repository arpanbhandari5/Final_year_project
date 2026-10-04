#!/usr/bin/env python3
"""Blank 3-task sample for the 800-occupation master. Does not invent labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import utc_now
from human_dataset_common import (
    LABELS,
    OCC_SEL,
    blank_human_score_columns,
    load_task_pool,
    occupation_grouped_splits,
    pick_diverse_tasks,
    sha256_file,
)

SEED = 20261003
TASKS_PER_OCC = 3
MASTER = OCC_SEL / "occupation_master_800.csv"
SAMPLE = LABELS / "task_exposure_800_sample.csv"
R1 = LABELS / "task_exposure_800_reviewer1.csv"
R2 = LABELS / "task_exposure_800_reviewer2.csv"
SPLITS = LABELS / "task_exposure_800_occupation_splits.csv"
STATS = LABELS / "task_exposure_800_sample_stats.json"


def reviewer_sheet(sample: pd.DataFrame, slot: int) -> pd.DataFrame:
    n = len(sample)
    return pd.DataFrame(
        {
            "reviewer_id": [""] * n,
            "reviewer_role": [""] * n,
            "relevant_experience": [""] * n,
            "rubric_version": sample["rubric_version"].astype(str).to_numpy(),
            "review_date": [""] * n,
            "task_id": sample["task_id"].astype(str).to_numpy(),
            "occupation_code": sample["occupation_code"].astype(str).to_numpy(),
            "occupation_title": sample["occupation_title"].astype(str).to_numpy(),
            "soc_major_group": sample["soc_major_group"].astype(str).to_numpy(),
            "task_text": sample["task_text"].astype(str).to_numpy(),
            "reviewer_score": [""] * n,
            "reviewer_confidence": [""] * n,
            "reviewer_evidence": [""] * n,
            "reviewer_notes": [""] * n,
            "split": sample["split"].astype(str).to_numpy(),
            "reviewer_slot": [str(slot)] * n,
        }
    )


def main() -> int:
    if not MASTER.exists():
        print(f"Missing {MASTER}. Run select_occupation_master_800.py first.")
        return 1
    master = pd.read_csv(MASTER, dtype=str, keep_default_na=False)
    occs = master["occupation_code"].astype(str).tolist()
    if len(set(occs)) != len(occs):
        raise RuntimeError("occupation_master_800 has duplicate occupation_code")
    pool = load_task_pool()
    pool = pool[pool["occupation_code"].isin(occs)].copy()
    rng = np.random.default_rng(SEED)
    split_map, split_counts = occupation_grouped_splits(occs, seed=SEED)
    parts = []
    shortfalls = []
    for occ in occs:
        g = pool[pool["occupation_code"] == occ]
        n_avail = int(g["task_id"].nunique())
        if n_avail < TASKS_PER_OCC:
            shortfalls.append({"occupation_code": occ, "available": n_avail})
        picked = pick_diverse_tasks(g, TASKS_PER_OCC, rng)
        parts.append(picked)
    sample = pd.concat(parts, ignore_index=True)
    sample = blank_human_score_columns(sample)
    emp = master.set_index("occupation_code")
    sample["employment_size"] = sample["occupation_code"].map(emp["employment_2025_thousands"])
    sample["projected_employment"] = sample["occupation_code"].map(emp["employment_2035_thousands"])
    sample["annual_openings"] = sample["occupation_code"].map(
        emp["occupational_openings_annual_average_2025_2035"]
    )
    sample["split"] = sample["occupation_code"].map(split_map)
    sample["split_key"] = sample["occupation_code"]
    keep = [
        "occupation_code",
        "occupation_title",
        "soc_code",
        "soc_major_group",
        "task_id",
        "task_text",
        "task_source",
        "onet_version",
        "bls_source",
        "employment_size",
        "projected_employment",
        "annual_openings",
        "reviewer_1_score",
        "reviewer_2_score",
        "adjudicated_exposure_score",
        "reviewer_1_confidence",
        "reviewer_2_confidence",
        "adjudication_status",
        "agreement_status",
        "label_source",
        "label_status",
        "rubric_version",
        "not_human_ground_truth",
        "split",
        "split_key",
    ]
    if "adjudication_status" not in sample.columns:
        sample["adjudication_status"] = ""
    sample = sample[keep]
    if sample["task_id"].duplicated().any():
        raise RuntimeError("duplicate task_id in 800 sample")
    train_occ = set(sample.loc[sample["split"] == "train", "occupation_code"])
    val_occ = set(sample.loc[sample["split"] == "validation", "occupation_code"])
    test_occ = set(sample.loc[sample["split"] == "test", "occupation_code"])
    if train_occ & val_occ or train_occ & test_occ or val_occ & test_occ:
        raise RuntimeError("occupation overlap across splits")

    LABELS.mkdir(parents=True, exist_ok=True)
    sample.to_csv(SAMPLE, index=False)
    reviewer_sheet(sample, 1).to_csv(R1, index=False)
    reviewer_sheet(sample, 2).to_csv(R2, index=False)
    pd.DataFrame(
        [{"occupation_code": occ, "split": split_map[occ], "seed": SEED} for occ in occs]
    ).sort_values(["split", "occupation_code"]).to_csv(SPLITS, index=False)

    # Frozen split extracts (still blank scores; not training inputs)
    for name, split in [
        ("task_exposure_800_human_train.csv", "train"),
        ("task_exposure_800_human_validation.csv", "validation"),
        ("task_exposure_800_human_test.csv", "test"),
    ]:
        sample[sample["split"] == split].to_csv(LABELS / name, index=False)

    stats = {
        "generated_at": utc_now(),
        "row_count": int(len(sample)),
        "occupations": int(sample["occupation_code"].nunique()),
        "tasks_per_occupation_min": int(sample.groupby("occupation_code").size().min()),
        "tasks_per_occupation_max": int(sample.groupby("occupation_code").size().max()),
        "shortfall_occupations_lt_3_tasks": shortfalls,
        "split_occupation_counts": split_counts,
        "filled_reviewer_scores": 0,
        "sha256": sha256_file(SAMPLE),
    }
    STATS.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: stats[k] for k in ("row_count", "occupations", "split_occupation_counts", "tasks_per_occupation_min")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
