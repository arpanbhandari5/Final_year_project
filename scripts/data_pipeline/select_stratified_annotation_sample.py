#!/usr/bin/env python3
"""Draw a reproducible stratified 250-task sample. Does not invent scores."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import BASE_DIR, utc_now

SOURCE = BASE_DIR / "project_data" / "task_exposure_labels" / "onet_task_annotations_round_1.csv"
OUT_DIR = BASE_DIR / "project_data" / "task_exposure_labels"
SAMPLE = OUT_DIR / "task_exposure_250_sample.csv"
LEGACY_SAMPLE = OUT_DIR / "onet_task_annotations_round_1_sample.csv"
REVIEWER_1 = OUT_DIR / "annotation_reviewer1.csv"
REVIEWER_2 = OUT_DIR / "annotation_reviewer2.csv"
STATS = OUT_DIR / "task_exposure_250_sample_stats.json"
README = OUT_DIR / "ROUND_1_SAMPLE.md"
TARGET = 250
SEED = 42
SCORE_FIELDS = [
    "reviewer_1_id",
    "reviewer_1_score",
    "reviewer_1_confidence",
    "reviewer_1_evidence",
    "reviewer_2_id",
    "reviewer_2_score",
    "reviewer_2_confidence",
    "reviewer_2_evidence",
    "adjudicated_exposure_score",
    "adjudication_notes",
    "label_confidence",
    "label_notes",
    "label_source",
    "label_version",
    "label_date",
]


def allocate(sizes: pd.Series, n: int) -> pd.Series:
    raw = sizes * (n / int(sizes.sum()))
    base = np.floor(raw).astype(int)
    remainder = n - int(base.sum())
    order = (raw - base).sort_values(ascending=False).index
    alloc = base.copy()
    for group in order:
        if remainder <= 0:
            break
        if alloc[group] < sizes[group]:
            alloc[group] += 1
            remainder -= 1
    for group in sizes.index:
        if alloc[group] > sizes[group]:
            overflow = int(alloc[group] - sizes[group])
            alloc[group] = sizes[group]
            remainder += overflow
    while remainder > 0:
        grew = False
        for group in sizes.sort_values(ascending=False).index:
            if remainder <= 0:
                break
            if alloc[group] < sizes[group]:
                alloc[group] += 1
                remainder -= 1
                grew = True
        if not grew:
            break
    return alloc


def blank_scores(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for field in SCORE_FIELDS:
        if field not in out.columns:
            out[field] = ""
        else:
            out[field] = ""
    return out


def main() -> None:
    df = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    df["soc_group"] = df["occupation_code"].astype(str).str[:2]
    sizes = df.groupby("soc_group").size()
    alloc = allocate(sizes, TARGET)
    parts: list[pd.DataFrame] = []
    for group, count in alloc.items():
        if count <= 0:
            continue
        part = df[df["soc_group"] == group]
        parts.append(part.sample(n=int(count), random_state=SEED))
    sample = blank_scores(pd.concat(parts, ignore_index=True))
    sample = sample.sample(frac=1, random_state=SEED).reset_index(drop=True)
    if len(sample) > TARGET:
        sample = sample.head(TARGET)
    sample_columns = [
        "occupation_code",
        "occupation_title",
        "task_id",
        "task_statement",
        "task_type",
        "soc_group",
        *SCORE_FIELDS,
        "source_citations",
    ]
    sample = sample[sample_columns]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample.to_csv(SAMPLE, index=False)
    sample.to_csv(LEGACY_SAMPLE, index=False)

    reviewer_1 = sample.drop(
        columns=["reviewer_2_id", "reviewer_2_score", "reviewer_2_confidence", "reviewer_2_evidence"]
    )
    reviewer_2 = sample.drop(
        columns=["reviewer_1_id", "reviewer_1_score", "reviewer_1_confidence", "reviewer_1_evidence"]
    )
    reviewer_1.to_csv(REVIEWER_1, index=False)
    reviewer_2.to_csv(REVIEWER_2, index=False)

    digest = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    stats = {
        "generated_at": utc_now(),
        "source": str(SOURCE.relative_to(BASE_DIR)).replace("\\", "/"),
        "output": str(SAMPLE.relative_to(BASE_DIR)).replace("\\", "/"),
        "row_count": int(len(sample)),
        "soc_groups": int(sample["soc_group"].nunique()),
        "occupations": int(sample["occupation_code"].nunique()),
        "seed": SEED,
        "allocation": {str(key): int(value) for key, value in alloc.items() if int(value) > 0},
        "filled_reviewer_scores": 0,
        "sha256": digest,
    }
    STATS.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    README.write_text(
        "\n".join(
            [
                "# Round-1 stratified 250-task sample",
                "",
                f"Reproducible stratified sample from `{SOURCE.name}` (`random_state={SEED}`).",
                "All reviewer and adjudicated score fields are blank. Do not invent labels.",
                "",
                f"- Canonical sample: `{SAMPLE.relative_to(BASE_DIR).as_posix()}`",
                f"- Reviewer 1 worksheet: `{REVIEWER_1.relative_to(BASE_DIR).as_posix()}`",
                f"- Reviewer 2 worksheet: `{REVIEWER_2.relative_to(BASE_DIR).as_posix()}`",
                f"- Tasks: {len(sample)}",
                f"- SOC major groups: {sample['soc_group'].nunique()}",
                f"- Occupations: {sample['occupation_code'].nunique()}",
                f"- SHA-256: `{digest}`",
                "",
                "Reviewers must not share scores until all 250 rows are rated.",
                "Run `scripts/data_pipeline/compute_annotation_agreement.py` only after both worksheets are complete.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Sample generated successfully with {len(sample)} tasks across {sample['soc_group'].nunique()} SOC groups.")


if __name__ == "__main__":
    main()
