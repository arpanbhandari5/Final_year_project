#!/usr/bin/env python3
"""Extract O*NET 31.0 and build the two separate label tracks. Does not train or invent scores."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_ONET_ZIP = BASE_DIR / "external_data" / "raw" / "onet_31_0" / "onet_31_0_text.zip"
RAW_ONET_DIR = BASE_DIR / "external_data" / "raw" / "onet_31_0" / "db_31_0_text"
HISTORICAL_CSV = BASE_DIR / "external_data" / "raw" / "historical_benchmark" / "frey_osborne_historical_702_occupations.csv"
REPLACEMENT = BASE_DIR / "replacement_data"
PROJECT_LABELS = BASE_DIR / "project_data" / "task_exposure_labels"

SOC_BARE = re.compile(r"^\d{2}-\d{4}$")
SOC_FULL = re.compile(r"^\d{2}-\d{4}\.\d{2}$")

TEMPLATE_FIELDS = [
    "occupation_code",
    "occupation_title",
    "task_id",
    "task_statement",
    "task_type",
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
    "source_citations",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_onet() -> None:
    if not RAW_ONET_ZIP.exists():
        raise FileNotFoundError(RAW_ONET_ZIP)
    RAW_ONET_DIR.mkdir(parents=True, exist_ok=True)
    occupation_file = RAW_ONET_DIR / "Occupation Data.txt"
    if occupation_file.exists():
        return
    with zipfile.ZipFile(RAW_ONET_ZIP) as archive:
        archive.extractall(RAW_ONET_DIR)
    nested = RAW_ONET_DIR / "db_31_0_text"
    if nested.is_dir() and not occupation_file.exists():
        for item in nested.iterdir():
            item.rename(RAW_ONET_DIR / item.name)


def read_tab_file(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def exact_onet_code(raw: str) -> str | None:
    text = str(raw or "").strip()
    if SOC_FULL.match(text):
        return text
    if SOC_BARE.match(text):
        return f"{text}.00"
    return None


def build_template(occupations: list[dict[str, str]], tasks: list[dict[str, str]]) -> Path:
    titles = {row["O*NET-SOC Code"]: row.get("Title", "") for row in occupations}
    destination = REPLACEMENT / "task_exposure_annotation_template.csv"
    PROJECT_LABELS.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_FIELDS)
        writer.writeheader()
        for row in tasks:
            writer.writerow(
                {
                    "occupation_code": row.get("O*NET-SOC Code", ""),
                    "occupation_title": titles.get(row.get("O*NET-SOC Code", ""), ""),
                    "task_id": row.get("Task ID", ""),
                    "task_statement": row.get("Task", ""),
                    "task_type": row.get("Task Type", ""),
                    "label_source": "",
                    "label_version": "",
                    "label_date": "",
                    "source_citations": "O*NET 31.0 Task Statements",
                }
            )
    (PROJECT_LABELS / "README.md").write_text(
        "Completed human labels belong here as `task_exposure_training.csv` after validation.\n"
        "Do not invent scores. Do not copy automation_risk_score or Frey-Osborne probabilities.\n",
        encoding="utf-8",
    )
    return destination


def build_historical_track(occupations: list[dict[str, str]]) -> dict[str, object]:
    onet_codes = {row["O*NET-SOC Code"] for row in occupations}
    titles = {row["O*NET-SOC Code"]: row.get("Title", "") for row in occupations}
    with HISTORICAL_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        historical = list(csv.DictReader(handle))
    columns = {name.lower(): name for name in (historical[0].keys() if historical else [])}
    soc_col = (
        columns.get("soc")
        or columns.get("code")
        or columns.get("soc code")
        or columns.get("_ - code")
    )
    occ_col = columns.get("occupation") or columns.get("job") or columns.get("title")
    prob_col = columns.get("prob") or columns.get("probability")
    if not soc_col or not prob_col:
        raise ValueError(f"Unexpected historical columns: {list(columns)}")

    mapped_rows: list[dict[str, object]] = []
    unmatched_rows: list[dict[str, object]] = []
    for row in historical:
        raw_soc = str(row.get(soc_col, "")).strip()
        candidate = exact_onet_code(raw_soc)
        record = {
            "source_soc": raw_soc,
            "mapped_onet_soc_code": candidate or "",
            "source_occupation": row.get(occ_col, "") if occ_col else "",
            "onet_title": titles.get(candidate, "") if candidate else "",
            "prob": row.get(prob_col, ""),
            "label_type": "historical_occupation_computerisation_probability",
            "label_source": "Frey_Osborne",
            "label_year": "2013/2017",
            "source_artifact": "plotly_public_mirror",
            "not_current_task_ground_truth": True,
        }
        if candidate and candidate in onet_codes:
            mapped_rows.append(record)
        else:
            record["unmatched_reason"] = "no_exact_onet_soc_match"
            unmatched_rows.append(record)

    mapped_path = REPLACEMENT / "external_occupation_labels.csv"
    unmatched_path = REPLACEMENT / "unmatched_external_labels.csv"
    occupation_master = REPLACEMENT / "occupation_master.csv"
    with occupation_master.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["O*NET-SOC Code", "Title", "Description", "source_release"])
        writer.writeheader()
        for row in occupations:
            writer.writerow(
                {
                    "O*NET-SOC Code": row.get("O*NET-SOC Code", ""),
                    "Title": row.get("Title", ""),
                    "Description": row.get("Description", ""),
                    "source_release": "O*NET 31.0",
                }
            )
    fieldnames = [
        "source_soc",
        "mapped_onet_soc_code",
        "source_occupation",
        "onet_title",
        "prob",
        "label_type",
        "label_source",
        "label_year",
        "source_artifact",
        "not_current_task_ground_truth",
        "unmatched_reason",
    ]
    with mapped_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mapped_rows)
    with unmatched_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unmatched_rows)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "onet_occupation_rows": len(occupations),
        "historical_source_rows": len(historical),
        "exact_mappings": len(mapped_rows),
        "unmapped_rows": len(unmatched_rows),
        "fuzzy_matching": False,
        "mapping_rule": "append .00 to bare ##-#### SOC codes and require an exact O*NET-SOC Code match",
        "not_current_task_ground_truth": True,
        "files": {
            "occupation_master": str(occupation_master.relative_to(BASE_DIR)),
            "external_occupation_labels": str(mapped_path.relative_to(BASE_DIR)),
            "unmatched_external_labels": str(unmatched_path.relative_to(BASE_DIR)),
        },
    }
    (REPLACEMENT / "mapping_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def find_file(name: str) -> Path:
    matches = list(RAW_ONET_DIR.rglob(name))
    if not matches:
        raise FileNotFoundError(name)
    return matches[0]


def main() -> None:
    extract_onet()
    occupations = read_tab_file(find_file("Occupation Data.txt"))
    tasks = read_tab_file(find_file("Task Statements.txt"))
    template = build_template(occupations, tasks)
    report = build_historical_track(occupations)
    report["task_statement_rows"] = len(tasks)
    report["annotation_template"] = str(template.relative_to(BASE_DIR))
    report["raw_hashes"] = {
        "onet_31_0_text.zip": sha256(RAW_ONET_ZIP),
        "frey_osborne_historical_702_occupations.csv": sha256(HISTORICAL_CSV),
    }
    (REPLACEMENT / "mapping_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
