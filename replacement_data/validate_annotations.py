#!/usr/bin/env python3
"""Validate completed human task labels. Does not invent or fill scores."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCHEMA_FIELDS = {
    "reviewer_1_score",
    "reviewer_2_score",
    "adjudicated_exposure_score",
    "label_source",
    "label_version",
    "occupation_code",
    "task_id",
}


def parse_score(value: str) -> float | None:
    text = (value or "").strip()
    if text == "":
        return None
    return float(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels_csv")
    parser.add_argument("--occupation-master", default="replacement_data/occupation_master.csv")
    args = parser.parse_args()
    path = Path(args.labels_csv)
    if not path.exists():
        print(f"missing {path}")
        return 1
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    occupation_codes: set[str] = set()
    occ_path = Path(args.occupation_master)
    if occ_path.exists():
        with occ_path.open("r", encoding="utf-8-sig", newline="") as handle:
            occupation_codes = {row["O*NET-SOC Code"] for row in csv.DictReader(handle)}

    issues: list[str] = []
    complete = 0
    for index, row in enumerate(rows, start=2):
        scores = {field: parse_score(row.get(field, "")) for field in ("reviewer_1_score", "reviewer_2_score", "adjudicated_exposure_score")}
        if all(value is None for value in scores.values()):
            continue
        if any(value is None for value in scores.values()):
            issues.append(f"line {index}: incomplete reviewer/adjudicated scores; missing is not zero")
            continue
        for field, value in scores.items():
            if value is None or value < 0.0 or value > 1.0:
                issues.append(f"line {index}: {field} out of range")
        if occupation_codes and row.get("occupation_code") not in occupation_codes:
            issues.append(f"line {index}: occupation_code not in occupation_master.csv")
        complete += 1

    report = {"complete_rows": complete, "issue_count": len(issues), "issues": issues[:50]}
    print(json.dumps(report, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
