#!/usr/bin/env python3
"""Stratified 300-task human Round-1 sample: 3 tasks per occupation. Scores stay blank."""

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
    REPORTS,
    REVIEWER_SLOT_IDS,
    RUBRIC_VERSION,
    blank_human_score_columns,
    load_task_pool,
    occupation_grouped_splits,
    pick_diverse_tasks,
    sha256_file,
    soc_prefix7,
)

SEED = 20261003
TASKS_PER_OCC = 3
TARGET_TASKS = 300
TARGET_OCC = TARGET_TASKS // TASKS_PER_OCC
THIRD_REVIEWER_N = 60

SAMPLE = LABELS / "task_exposure_human_round1_sample.csv"
R1 = LABELS / "task_exposure_human_round1_reviewer1.csv"
R2 = LABELS / "task_exposure_human_round1_reviewer2.csv"
R3 = LABELS / "task_exposure_human_round1_third_reviewer.csv"
SPLITS = LABELS / "task_exposure_human_round1_occupation_splits.csv"
STATS = LABELS / "task_exposure_human_round1_sample_stats.json"
README = LABELS / "HUMAN_ROUND1_SAMPLE.md"


def allocate_occupations(soc_sizes: pd.Series, n: int) -> dict[str, int]:
    raw = soc_sizes * (n / int(soc_sizes.sum()))
    base = np.floor(raw).astype(int)
    remainder = n - int(base.sum())
    alloc = base.to_dict()
    order = (raw - base).sort_values(ascending=False).index
    for group in order:
        if remainder <= 0:
            break
        if alloc[group] < int(soc_sizes[group]):
            alloc[group] += 1
            remainder -= 1
    while remainder > 0:
        grew = False
        for group in soc_sizes.sort_values(ascending=False).index:
            if remainder <= 0:
                break
            if alloc[group] < int(soc_sizes[group]):
                alloc[group] += 1
                remainder -= 1
                grew = True
        if not grew:
            break
    return {str(k): int(v) for k, v in alloc.items() if int(v) > 0}


def reviewer_sheet(sample: pd.DataFrame, reviewer_slot: int) -> pd.DataFrame:
    n = len(sample)
    slot = str(reviewer_slot)
    out = pd.DataFrame(
        {
            "reviewer_id": [REVIEWER_SLOT_IDS[slot]] * n,
            "reviewer_role": ["independent_reviewer"] * n,
            "relevant_experience": [""] * n,
            "rubric_version": [RUBRIC_VERSION] * n,
            "review_date": [""] * n,
            "task_id": sample["task_id"].astype(str).to_numpy(),
            "occupation_code": sample["occupation_code"].astype(str).to_numpy(),
            "occupation_title": sample["occupation_title"].astype(str).to_numpy(),
            "soc_code": sample["occupation_code"].map(soc_prefix7).astype(str).to_numpy(),
            "soc_major_group": sample["soc_major_group"].astype(str).to_numpy(),
            "task_text": sample["task_text"].astype(str).to_numpy(),
            "reviewer_score": [""] * n,
            "reviewer_confidence": [""] * n,
            "reviewer_evidence": [""] * n,
            "reviewer_notes": [""] * n,
            "split": sample["split"].astype(str).to_numpy(),
            "reviewer_slot": [slot] * n,
        }
    )
    return out


def main() -> int:
    pool = load_task_pool()
    counts = pool.groupby("occupation_code").size()
    eligible_occ = counts[counts >= TASKS_PER_OCC].index
    eligible = pool[pool["occupation_code"].isin(eligible_occ)].copy()
    occ_table = (
        eligible.groupby(["occupation_code", "occupation_title", "soc_major_group"], as_index=False)
        .size()
        .rename(columns={"size": "n_tasks_available"})
    )
    soc_sizes = occ_table.groupby("soc_major_group").size()
    alloc = allocate_occupations(soc_sizes, TARGET_OCC)
    rng = np.random.default_rng(SEED)
    chosen_occ = []
    for soc, n_take in alloc.items():
        part = occ_table[occ_table["soc_major_group"] == soc]
        take = min(int(n_take), len(part))
        picked = part.sample(n=take, random_state=int(rng.integers(0, 10_000_000)))
        chosen_occ.extend(picked["occupation_code"].tolist())
    chosen_occ = sorted(set(chosen_occ))
    if len(chosen_occ) > TARGET_OCC:
        chosen_occ = list(np.random.default_rng(SEED).choice(chosen_occ, size=TARGET_OCC, replace=False))
    if len(chosen_occ) < TARGET_OCC:
        leftover = occ_table[~occ_table["occupation_code"].isin(chosen_occ)]
        need = TARGET_OCC - len(chosen_occ)
        extra = leftover.sample(n=min(need, len(leftover)), random_state=SEED)
        chosen_occ.extend(extra["occupation_code"].tolist())
        chosen_occ = sorted(set(chosen_occ))[:TARGET_OCC]

    split_map, split_counts = occupation_grouped_splits(chosen_occ, seed=SEED)
    parts = []
    for occ in chosen_occ:
        g = eligible[eligible["occupation_code"] == occ]
        picked = pick_diverse_tasks(g, TASKS_PER_OCC, rng)
        parts.append(picked)
    sample = pd.concat(parts, ignore_index=True)
    sample = blank_human_score_columns(sample)
    sample["split"] = sample["occupation_code"].map(split_map)
    sample["split_key"] = sample["occupation_code"]
    keep = [
        "task_id",
        "occupation_code",
        "occupation_title",
        "soc_code",
        "soc_major_group",
        "task_text",
        "task_type",
        "task_source",
        "onet_version",
        "bls_source",
        "split",
        "split_key",
        "rubric_version",
        "label_status",
        "label_source",
        "not_human_ground_truth",
        "reviewer_1_score",
        "reviewer_2_score",
        "third_reviewer_score",
        "adjudicated_exposure_score",
        "agreement_status",
        "adjudication_reason",
        "source_citations",
    ]
    for col in keep:
        if col not in sample.columns:
            sample[col] = ""
    sample = sample[keep].drop_duplicates(subset=["task_id"])
    if sample["task_id"].duplicated().any():
        raise RuntimeError("duplicate task_id in round-1 sample")
    sample = sample.sample(frac=1, random_state=SEED).reset_index(drop=True)

    LABELS.mkdir(parents=True, exist_ok=True)
    sample.to_csv(SAMPLE, index=False)
    reviewer_sheet(sample, 1).to_csv(R1, index=False)
    reviewer_sheet(sample, 2).to_csv(R2, index=False)
    third = sample.sample(n=min(THIRD_REVIEWER_N, len(sample)), random_state=SEED + 1)
    reviewer_sheet(third, 3).to_csv(R3, index=False)

    split_df = pd.DataFrame(
        [{"occupation_code": occ, "split": split_map[occ], "seed": SEED} for occ in chosen_occ]
    ).sort_values(["split", "occupation_code"])
    split_df.to_csv(SPLITS, index=False)

    stats = {
        "generated_at": utc_now(),
        "rubric_version": RUBRIC_VERSION,
        "seed": SEED,
        "row_count": int(len(sample)),
        "occupations": int(sample["occupation_code"].nunique()),
        "soc_major_groups": int(sample["soc_major_group"].nunique()),
        "tasks_per_occupation_min": int(sample.groupby("occupation_code").size().min()),
        "tasks_per_occupation_max": int(sample.groupby("occupation_code").size().max()),
        "filled_reviewer_scores": 0,
        "split_occupation_counts": split_counts,
        "soc_allocation_occupations": alloc,
        "sha256": sha256_file(SAMPLE),
        "note": "All scores blank. Do not invent labels. Reviewer worksheets are independent.",
    }
    STATS.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    README.write_text(
        "\n".join(
            [
                "# Human Round-1 300-task sample (3 tasks per occupation)",
                "",
                f"rubric_version `{RUBRIC_VERSION}`. Scores are blank. Do not invent labels.",
                "",
                f"- sample: `{SAMPLE.name}` ({len(sample)} rows, {sample['occupation_code'].nunique()} occupations, {sample['soc_major_group'].nunique()} SOC major groups)",
                f"- reviewer 1 (`HUMAN_REVIEWER_A`): `{R1.name}`",
                f"- reviewer 2 (`HUMAN_REVIEWER_B`): `{R2.name}` (must not see reviewer 1 scores)",
                f"- third-reviewer (`HUMAN_REVIEWER_C`) subset: `{R3.name}` ({len(third)} tasks)",
                f"- frozen occupation splits: `{SPLITS.name}` {split_counts}",
                f"- SHA-256: `{stats['sha256']}`",
                "",
                "No occupation appears in more than one split.",
                "Unresolved or blank scores are excluded from training.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({k: stats[k] for k in ("row_count", "occupations", "soc_major_groups", "split_occupation_counts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
