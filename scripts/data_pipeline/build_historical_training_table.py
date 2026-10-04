#!/usr/bin/env python3
"""Build the historical occupation benchmark table. Does not train or invent task labels."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import BASE_DIR, markdown_table, sha256_file, utc_now, write_csv

RAW_ONET = BASE_DIR / "external_data" / "raw" / "onet_31_0" / "db_31_0_text"
MASTER = BASE_DIR / "replacement_data" / "occupation_master.csv"
LABELS = BASE_DIR / "replacement_data" / "external_occupation_labels.csv"
UNMATCHED = BASE_DIR / "replacement_data" / "unmatched_external_labels.csv"
OUTPUT = BASE_DIR / "replacement_data" / "occupation_training_table_historical_benchmark.csv"
REPORT = BASE_DIR / "reports" / "data_quality" / "historical_benchmark_build_report.md"
VERSION = "historical-benchmark-table-v1.0"

FIELDS = [
    "occupation_code",
    "onet_title",
    "onet_description",
    "source_soc",
    "source_occupation",
    "historical_computerisation_probability",
    "label_type",
    "label_source",
    "label_year",
    "source_artifact",
    "not_current_task_ground_truth",
    "source_release",
    "task_count",
    "task_text",
    "software_example_count",
    "software_text",
    "essential_skill_count",
    "essential_skills_text",
    "transferable_skill_count",
    "transferable_skills_text",
    "transformation_version",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_tab(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def unique_join(values: list[str], limit: int | None = None) -> str:
    seen: list[str] = []
    used: set[str] = set()
    for value in values:
        text = " ".join(str(value).split())
        if not text or text in used:
            continue
        used.add(text)
        seen.append(text)
        if limit is not None and len(seen) >= limit:
            break
    return " | ".join(seen)


def importance_names(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row.get("Scale ID") != "IM":
            continue
        grouped[row["O*NET-SOC Code"]].append(row.get("Element Name", ""))
    return grouped


def main() -> None:
    master = {row["O*NET-SOC Code"]: row for row in read_csv(MASTER)}
    labels = read_csv(LABELS)
    unmatched = read_csv(UNMATCHED)
    tasks = read_tab(RAW_ONET / "Task Statements.txt")
    software = read_tab(RAW_ONET / "Software Skills.txt")
    essential = read_tab(RAW_ONET / "Essential Skills.txt")
    transferable = read_tab(RAW_ONET / "Transferable Skills.txt")

    tasks_by = defaultdict(list)
    for row in tasks:
        tasks_by[row["O*NET-SOC Code"]].append(row.get("Task", ""))
    software_by = defaultdict(list)
    for row in software:
        example = row.get("Workplace Example", "")
        element = row.get("Element Name", "")
        software_by[row["O*NET-SOC Code"]].append(f"{example} ({element})".strip())
    essential_by = importance_names(essential)
    transferable_by = importance_names(transferable)

    output_rows: list[dict[str, str]] = []
    missing_master = 0
    missing_target = 0
    out_of_range = 0
    for label in labels:
        code = label.get("mapped_onet_soc_code", "")
        occupation = master.get(code, {})
        if not occupation:
            missing_master += 1
        target = label.get("prob", "")
        try:
            probability = float(target)
            if probability < 0 or probability > 1:
                out_of_range += 1
        except ValueError:
            missing_target += 1
            probability = None
        if target == "":
            missing_target += 1
        output_rows.append(
            {
                "occupation_code": code,
                "onet_title": occupation.get("Title") or label.get("onet_title", ""),
                "onet_description": occupation.get("Description", ""),
                "source_soc": label.get("source_soc", ""),
                "source_occupation": label.get("source_occupation", ""),
                "historical_computerisation_probability": target,
                "label_type": label.get("label_type", "historical_occupation_computerisation_probability"),
                "label_source": label.get("label_source", "Frey_Osborne"),
                "label_year": label.get("label_year", "2013/2017"),
                "source_artifact": label.get("source_artifact", "plotly_public_mirror"),
                "not_current_task_ground_truth": "true",
                "source_release": occupation.get("source_release", "O*NET 31.0"),
                "task_count": str(len(tasks_by.get(code, []))),
                "task_text": unique_join(tasks_by.get(code, [])),
                "software_example_count": str(len(software_by.get(code, []))),
                "software_text": unique_join(software_by.get(code, [])),
                "essential_skill_count": str(len(dict.fromkeys(essential_by.get(code, [])))),
                "essential_skills_text": unique_join(essential_by.get(code, [])),
                "transferable_skill_count": str(len(dict.fromkeys(transferable_by.get(code, [])))),
                "transferable_skills_text": unique_join(transferable_by.get(code, [])),
                "transformation_version": VERSION,
            }
        )

    write_csv(OUTPUT, FIELDS, output_rows)
    codes = [row["occupation_code"] for row in output_rows]
    duplicate_codes = len(codes) - len(set(codes))
    probabilities = []
    for row in output_rows:
        try:
            probabilities.append(float(row["historical_computerisation_probability"]))
        except ValueError:
            pass
    missing_tasks = sum(1 for row in output_rows if row["task_count"] == "0")
    report = [
        "# Historical benchmark table build report",
        "",
        f"Generated at: {utc_now()}",
        f"Transformation version: `{VERSION}`",
        "",
        "This table is an **occupation-level historical computerisation benchmark**, not current task ground truth and not a personal job-loss probability.",
        "The 84 unmatched Frey–Osborne rows were **not** fuzzy-matched and are not in this table.",
        "",
        "## Inputs",
        "",
        markdown_table(
            ["file", "sha256"],
            [
                [MASTER.relative_to(BASE_DIR).as_posix(), sha256_file(MASTER)],
                [LABELS.relative_to(BASE_DIR).as_posix(), sha256_file(LABELS)],
                [UNMATCHED.relative_to(BASE_DIR).as_posix(), sha256_file(UNMATCHED)],
                ["external_data/raw/onet_31_0/db_31_0_text/Task Statements.txt", sha256_file(RAW_ONET / "Task Statements.txt")],
                ["external_data/raw/onet_31_0/db_31_0_text/Software Skills.txt", sha256_file(RAW_ONET / "Software Skills.txt")],
                ["external_data/raw/onet_31_0/db_31_0_text/Essential Skills.txt", sha256_file(RAW_ONET / "Essential Skills.txt")],
                ["external_data/raw/onet_31_0/db_31_0_text/Transferable Skills.txt", sha256_file(RAW_ONET / "Transferable Skills.txt")],
            ],
        ),
        "",
        "## Output",
        "",
        f"- Path: `{OUTPUT.relative_to(BASE_DIR).as_posix()}`",
        f"- SHA-256: `{sha256_file(OUTPUT)}`",
        f"- Row count: {len(output_rows)}",
        f"- Unmatched historical rows left out: {len(unmatched)}",
        f"- Duplicate occupation_code extra rows: {duplicate_codes}",
        f"- Missing occupation_master join: {missing_master}",
        f"- Missing target: {missing_target}",
        f"- Target outside 0-1: {out_of_range}",
        f"- Occupations with zero task statements: {missing_tasks}",
        f"- Target min/max/mean: {min(probabilities):.4f} / {max(probabilities):.4f} / {sum(probabilities)/len(probabilities):.4f}" if probabilities else "- No numeric targets",
        "",
        "Join key: exact `mapped_onet_soc_code` = `O*NET-SOC Code`. Essential and transferable skill names use Scale ID `IM` only.",
        "Do not train a production model from this table. Do not copy these probabilities onto O*NET task annotation rows.",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(OUTPUT, len(output_rows), "unmatched_left_out", len(unmatched), "dup_codes", duplicate_codes)


if __name__ == "__main__":
    main()
