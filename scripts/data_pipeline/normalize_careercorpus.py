#!/usr/bin/env python3
"""Normalize CareerCorpus resumes vs annotations. Does not train or invent O*NET labels."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import (
    BASE_DIR,
    TRANSFORMATION_VERSION,
    duplicate_counts,
    flatten_text,
    inspect_xlsx,
    markdown_table,
    missing_counts,
    sha256_file,
    utc_now,
    write_csv,
    write_json,
)

SOURCE_VERSION = "CareerCorpus-xlsx-raw"
RAW_PATH = BASE_DIR / "external_data" / "raw" / "careercorpus" / "CareerCorpus.xlsx"
OUT_DIR = BASE_DIR / "external_data" / "normalized" / "careercorpus"
REPORT_PATH = BASE_DIR / "reports" / "data_quality" / "careercorpus_normalization_report.md"
RESUME_FIELDS = [
    "resume_id",
    "domain",
    "education",
    "skills_and_achievements",
    "experience",
    "job_type",
    "source_sheet",
    "source_row_number",
    "source_version",
    "transformation_version",
    "not_onet_task_label",
]
ANNOTATION_FIELDS = [
    "resume_id",
    "annotator_1_score",
    "annotator_2_score",
    "label_source",
    "source_sheet",
    "source_row_number",
    "source_version",
    "transformation_version",
    "not_onet_task_label",
]
EXCLUSION_FIELDS = ["source_sheet", "source_row_number", "reason", "raw_preview"]
EXPECTED_HEADER = [
    "ID",
    "Domain",
    "Education",
    "Skills and Achievements",
    "Experience",
    "Job_type",
    "Annotator-1",
    "Annotator-2",
]


def _cell(row: list[str], index: int) -> str:
    return flatten_text(row[index] if index < len(row) else "")


def _in_unit_interval(value: str) -> bool:
    if not value:
        return False
    try:
        number = float(value)
    except ValueError:
        return False
    return 0.0 <= number <= 1.0


def normalize() -> dict[str, Any]:
    if not RAW_PATH.exists():
        raise FileNotFoundError(RAW_PATH)
    sheets = inspect_xlsx(RAW_PATH)
    resumes: list[dict[str, str]] = []
    annotations: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    invalid_ids = 0
    invalid_annotation_values = 0
    unused_sheets: list[dict[str, Any]] = []
    sheet_summaries: list[dict[str, Any]] = []

    for sheet in sheets:
        header = [flatten_text(value) for value in sheet["header"]]
        sheet_summaries.append(
            {
                "name": sheet["name"],
                "path": sheet["path"],
                "header": header,
                "xml_row_count": sheet["xml_row_count"],
                "data_row_count": len(sheet["data_rows"]),
            }
        )
        if header[:8] != EXPECTED_HEADER:
            unused_sheets.append(
                {
                    "name": sheet["name"],
                    "reason": "unexpected_or_empty_header",
                    "header": header,
                    "data_row_count": len(sheet["data_rows"]),
                }
            )
            for offset, raw_row in enumerate(sheet["data_rows"], start=2):
                if any(flatten_text(value) for value in raw_row):
                    excluded.append(
                        {
                            "source_sheet": sheet["name"],
                            "source_row_number": str(offset),
                            "reason": "sheet_header_did_not_match_expected_career_corpus_schema",
                            "raw_preview": flatten_text(" | ".join(raw_row))[:400],
                        }
                    )
            continue
        for offset, raw_row in enumerate(sheet["data_rows"], start=2):
            resume_id = _cell(raw_row, 0)
            domain = _cell(raw_row, 1)
            education = _cell(raw_row, 2)
            skills = _cell(raw_row, 3)
            experience = _cell(raw_row, 4)
            job_type = _cell(raw_row, 5)
            annotator_1 = _cell(raw_row, 6)
            annotator_2 = _cell(raw_row, 7)
            preview = flatten_text(" | ".join(raw_row[:8]))[:400]
            if not any([resume_id, domain, education, skills, experience, job_type, annotator_1, annotator_2]):
                excluded.append(
                    {
                        "source_sheet": sheet["name"],
                        "source_row_number": str(offset),
                        "reason": "empty_row",
                        "raw_preview": preview,
                    }
                )
                continue
            if not resume_id:
                excluded.append(
                    {
                        "source_sheet": sheet["name"],
                        "source_row_number": str(offset),
                        "reason": "missing_resume_id",
                        "raw_preview": preview,
                    }
                )
                continue
            if not resume_id.isdigit():
                invalid_ids += 1
            if annotator_1 and not _in_unit_interval(annotator_1):
                invalid_annotation_values += 1
            if annotator_2 and not _in_unit_interval(annotator_2):
                invalid_annotation_values += 1
            common = {
                "resume_id": resume_id,
                "source_sheet": sheet["name"],
                "source_row_number": str(offset),
                "source_version": SOURCE_VERSION,
                "transformation_version": TRANSFORMATION_VERSION,
                "not_onet_task_label": "true",
            }
            resumes.append(
                {
                    **common,
                    "domain": domain,
                    "education": education,
                    "skills_and_achievements": skills,
                    "experience": experience,
                    "job_type": job_type,
                }
            )
            annotations.append(
                {
                    **common,
                    "annotator_1_score": annotator_1,
                    "annotator_2_score": annotator_2,
                    "label_source": "CareerCorpus",
                }
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resume_path = OUT_DIR / "careercorpus_resumes.csv"
    annotation_path = OUT_DIR / "careercorpus_annotations.csv"
    exclusion_path = OUT_DIR / "careercorpus_excluded.csv"
    write_csv(resume_path, RESUME_FIELDS, resumes)
    write_csv(annotation_path, ANNOTATION_FIELDS, annotations)
    write_csv(exclusion_path, EXCLUSION_FIELDS, excluded)

    input_data_rows = sum(item["data_row_count"] for item in sheet_summaries)
    payload = {
        "input_path": str(RAW_PATH.relative_to(BASE_DIR)).replace("\\", "/"),
        "input_sha256": sha256_file(RAW_PATH),
        "source_version": SOURCE_VERSION,
        "transformation_version": TRANSFORMATION_VERSION,
        "workbook_sheets": sheet_summaries,
        "unused_or_unexpected_sheets": unused_sheets,
        "input_row_count": input_data_rows,
        "excluded_row_count": len(excluded),
        "excluded_rows": excluded,
        "invalid_identifier_counts": invalid_ids,
        "invalid_annotation_value_counts": invalid_annotation_values,
        "tables": [
            {
                "dataset": "careercorpus_resumes.csv",
                "input_path": str(RAW_PATH.relative_to(BASE_DIR)).replace("\\", "/"),
                "input_sha256": sha256_file(RAW_PATH),
                "output_path": str(resume_path.relative_to(BASE_DIR)).replace("\\", "/"),
                "input_row_count": input_data_rows,
                "output_row_count": len(resumes),
                "column_names": RESUME_FIELDS,
                "missing_value_counts": missing_counts(resumes, RESUME_FIELDS),
                "duplicate_identifier_counts": duplicate_counts([row["resume_id"] for row in resumes]),
                "invalid_identifier_counts": invalid_ids,
                "transformation_version": TRANSFORMATION_VERSION,
                "source_version": SOURCE_VERSION,
            },
            {
                "dataset": "careercorpus_annotations.csv",
                "input_path": str(RAW_PATH.relative_to(BASE_DIR)).replace("\\", "/"),
                "input_sha256": sha256_file(RAW_PATH),
                "output_path": str(annotation_path.relative_to(BASE_DIR)).replace("\\", "/"),
                "input_row_count": input_data_rows,
                "output_row_count": len(annotations),
                "column_names": ANNOTATION_FIELDS,
                "missing_value_counts": missing_counts(annotations, ANNOTATION_FIELDS),
                "duplicate_identifier_counts": duplicate_counts([row["resume_id"] for row in annotations]),
                "invalid_identifier_counts": invalid_ids,
                "transformation_version": TRANSFORMATION_VERSION,
                "source_version": SOURCE_VERSION,
            },
        ],
        "exclusion_log_path": str(exclusion_path.relative_to(BASE_DIR)).replace("\\", "/"),
        "note": "CareerCorpus annotator scores are resume-domain labels, not O*NET task-exposure labels.",
    }
    write_json(OUT_DIR / "careercorpus_normalization_stats.json", payload)
    _write_report(payload)
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# CareerCorpus normalization report",
        "",
        f"Generated at: {utc_now()}",
        f"Input path: `{payload['input_path']}`",
        f"Input SHA-256: `{payload['input_sha256']}`",
        f"Source version: `{payload['source_version']}`",
        f"Transformation version: `{payload['transformation_version']}`",
        "",
        "Workbook sheets inspected:",
        "",
        markdown_table(
            ["sheet", "xml rows", "data rows", "header"],
            [
                [sheet["name"], sheet["xml_row_count"], sheet["data_row_count"], ", ".join(sheet["header"])]
                for sheet in payload["workbook_sheets"]
            ],
        ),
        "",
        payload["note"],
        "Resume text and annotation scores are written to separate files. No O*NET task labels were filled.",
        "",
        markdown_table(
            ["output", "input rows", "output rows", "invalid resume_id values", "duplicate resume_id values"],
            [
                [
                    table["dataset"],
                    table["input_row_count"],
                    table["output_row_count"],
                    table["invalid_identifier_counts"],
                    table["duplicate_identifier_counts"]["duplicate_identifier_values"],
                ]
                for table in payload["tables"]
            ],
        ),
        "",
        f"Excluded row count: {payload['excluded_row_count']}",
        f"Invalid annotation value counts: {payload['invalid_annotation_value_counts']}",
        f"Exclusion log: `{payload['exclusion_log_path']}`",
        "",
    ]
    for table in payload["tables"]:
        lines.extend(
            [
                f"## {table['dataset']}",
                "",
                f"- Output path: `{table['output_path']}`",
                f"- Column names: {', '.join(f'`{name}`' for name in table['column_names'])}",
                "",
                "Missing-value counts:",
                "",
                markdown_table(
                    ["column", "missing"],
                    [[key, value] for key, value in table["missing_value_counts"].items()],
                ),
                "",
            ]
        )
    if payload["excluded_rows"]:
        lines.append("Excluded rows (complete list is in the exclusion log):")
        lines.append("")
        empty_rows = [
            int(row["source_row_number"])
            for row in payload["excluded_rows"]
            if row["reason"] == "empty_row" and str(row["source_row_number"]).isdigit()
        ]
        other = [row for row in payload["excluded_rows"] if row["reason"] != "empty_row"]
        if empty_rows:
            lines.append(
                f"- Sheet1 rows {min(empty_rows)}-{max(empty_rows)}: empty_row ({len(empty_rows)} rows). Full list: `{payload['exclusion_log_path']}`"
            )
        for row in other:
            lines.append(
                f"- {row['source_sheet']} row {row['source_row_number']}: {row['reason']} — `{row['raw_preview']}`"
            )
    else:
        lines.append("Excluded rows: none.")
    if payload["unused_or_unexpected_sheets"]:
        lines.extend(["", "Unexpected sheets:", ""])
        for sheet in payload["unused_or_unexpected_sheets"]:
            lines.append(f"- {sheet['name']}: {sheet['reason']} header={sheet['header']}")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> dict[str, Any]:
    return normalize()


if __name__ == "__main__":
    main()
