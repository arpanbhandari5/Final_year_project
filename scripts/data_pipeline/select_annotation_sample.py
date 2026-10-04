#!/usr/bin/env python3
"""Select a blank 250-task annotation sample. Does not invent scores."""

from __future__ import annotations

import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import BASE_DIR, write_csv

SOURCE = BASE_DIR / "project_data" / "task_exposure_labels" / "onet_task_annotations_round_1.csv"
OUTPUT = BASE_DIR / "project_data" / "task_exposure_labels" / "onet_task_annotations_round_1_sample.csv"
README = BASE_DIR / "project_data" / "task_exposure_labels" / "ROUND_1_SAMPLE.md"
TARGET = 250


def main() -> None:
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("occupation_code", "")[:2]].append(row)
    selected: list[dict[str, str]] = []
    soc_groups = sorted(grouped)
    index = {key: 0 for key in soc_groups}
    while len(selected) < TARGET:
        progressed = False
        for key in soc_groups:
            bucket = grouped[key]
            cursor = index[key]
            if cursor >= len(bucket):
                continue
            selected.append(bucket[cursor])
            index[key] = cursor + 1
            progressed = True
            if len(selected) >= TARGET:
                break
        if not progressed:
            break
    for row in selected:
        for field in (
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
            "label_source",
            "label_version",
            "label_date",
        ):
            row[field] = ""
    write_csv(OUTPUT, fields, selected)
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    README.write_text(
        "\n".join(
            [
                "# Round-1 annotation sample",
                "",
                f"Selected {len(selected)} blank task rows from `{SOURCE.name}` by cycling SOC major groups.",
                "Scores are empty. Do not use automation_risk_score or Frey–Osborne probabilities as labels.",
                "",
                f"- Output: `{OUTPUT.relative_to(BASE_DIR).as_posix()}`",
                f"- SHA-256: `{digest}`",
                f"- Occupations represented: {len({row['occupation_code'] for row in selected})}",
                f"- SOC major groups represented: {len({row['occupation_code'][:2] for row in selected})}",
                "",
                "Required human fields: reviewer_1_score, reviewer_2_score, reviewer confidence, notes,",
                "adjudicated_exposure_score, label_source, label_version, label_date.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(OUTPUT, len(selected), "occupations", len({row["occupation_code"] for row in selected}))


if __name__ == "__main__":
    main()
