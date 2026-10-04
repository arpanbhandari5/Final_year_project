#!/usr/bin/env python3
"""Normalize ESCO v1.2.1 tables. Does not train or invent labels."""

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
    is_esco_uri,
    markdown_table,
    missing_counts,
    read_csv_rows,
    sha256_file,
    utc_now,
    write_csv,
    write_json,
)

ESCO_VERSION = "1.2.1"
RAW_DIR = BASE_DIR / "external_data" / "raw" / "esco" / "ESCO dataset - v1.2.1 - classification - en - csv"
OUT_DIR = BASE_DIR / "external_data" / "normalized" / "esco"
REPORT_PATH = BASE_DIR / "reports" / "data_quality" / "esco_normalization_report.md"
EXCLUSION_FIELDS = ["source_file", "source_row_number", "reason", "raw_preview"]

OCCUPATION_MAP = [
    ("conceptUri", "esco_occupation_uri"),
    ("code", "esco_occupation_code"),
    ("iscoGroup", "isco_group"),
    ("preferredLabel", "preferred_label"),
    ("altLabels", "alt_labels"),
    ("hiddenLabels", "hidden_labels"),
    ("status", "status"),
    ("modifiedDate", "modified_date"),
    ("definition", "definition"),
    ("description", "description"),
    ("conceptType", "concept_type"),
    ("inScheme", "in_scheme"),
    ("naceCode", "nace_code"),
    ("regulatedProfessionNote", "regulated_profession_note"),
    ("scopeNote", "scope_note"),
]
SKILL_MAP = [
    ("conceptUri", "esco_skill_uri"),
    ("skillType", "skill_type"),
    ("reuseLevel", "reuse_level"),
    ("preferredLabel", "preferred_label"),
    ("altLabels", "alt_labels"),
    ("hiddenLabels", "hidden_labels"),
    ("status", "status"),
    ("modifiedDate", "modified_date"),
    ("definition", "definition"),
    ("description", "description"),
    ("conceptType", "concept_type"),
    ("inScheme", "in_scheme"),
    ("scopeNote", "scope_note"),
]
OCC_SKILL_MAP = [
    ("occupationUri", "esco_occupation_uri"),
    ("occupationLabel", "occupation_label"),
    ("relationType", "relation_type"),
    ("skillType", "skill_type"),
    ("skillUri", "esco_skill_uri"),
    ("skillLabel", "skill_label"),
]
SKILL_REL_MAP = [
    ("originalSkillUri", "original_skill_uri"),
    ("originalSkillType", "original_skill_type"),
    ("relationType", "relation_type"),
    ("relatedSkillType", "related_skill_type"),
    ("relatedSkillUri", "related_skill_uri"),
]


def _meta() -> dict[str, str]:
    return {
        "source_version": ESCO_VERSION,
        "transformation_version": TRANSFORMATION_VERSION,
        "source_licence_note": "ESCO is not an automation-risk target",
    }


def _map_row(raw: dict[str, str], mapping: list[tuple[str, str]]) -> dict[str, str]:
    out = {dest: flatten_text(raw.get(source, "")) for source, dest in mapping}
    out.update(_meta())
    return out


def _preview(raw: dict[str, str]) -> str:
    return flatten_text(" | ".join(f"{key}={raw.get(key, '')}" for key in list(raw)[:4]))[:400]


def normalize_table(
    source_name: str,
    mapping: list[tuple[str, str]],
    identity_fields: list[str],
    output_name: str,
    extra_invalid: Any | None = None,
) -> dict[str, Any]:
    source_path = RAW_DIR / source_name
    original_fields, raw_rows = read_csv_rows(source_path)
    kept: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    invalid_ids = 0
    for index, raw in enumerate(raw_rows, start=2):
        mapped = _map_row(raw, mapping)
        identities = [mapped.get(field, "") for field in identity_fields]
        if all(not value for value in identities):
            excluded.append(
                {
                    "source_file": source_name,
                    "source_row_number": str(index),
                    "reason": "missing_all_identity_fields:" + ",".join(identity_fields),
                    "raw_preview": _preview(raw),
                }
            )
            continue
        if extra_invalid:
            invalid_ids += extra_invalid(mapped)
        else:
            invalid_ids += sum(1 for value in identities if value and not is_esco_uri(value))
        kept.append(mapped)

    dest_fields = [dest for _, dest in mapping] + list(_meta().keys())
    output_path = OUT_DIR / output_name
    write_csv(output_path, dest_fields, kept)
    exclusion_path = OUT_DIR / f"{output_name.replace('.csv', '')}_excluded.csv"
    write_csv(exclusion_path, EXCLUSION_FIELDS, excluded)
    identity_values = ["||".join(row.get(field, "") for field in identity_fields) for row in kept]
    report = {
        "dataset": output_name,
        "input_path": str(source_path.relative_to(BASE_DIR)).replace("\\", "/"),
        "input_sha256": sha256_file(source_path),
        "output_path": str(output_path.relative_to(BASE_DIR)).replace("\\", "/"),
        "exclusion_log_path": str(exclusion_path.relative_to(BASE_DIR)).replace("\\", "/"),
        "input_row_count": len(raw_rows),
        "output_row_count": len(kept),
        "excluded_row_count": len(excluded),
        "excluded_rows": excluded,
        "column_names": dest_fields,
        "source_column_names": original_fields,
        "missing_value_counts": missing_counts(kept, dest_fields),
        "duplicate_identifier_counts": duplicate_counts(identity_values),
        "invalid_identifier_counts": invalid_ids,
        "identity_fields": identity_fields,
        "transformation_version": TRANSFORMATION_VERSION,
        "source_version": ESCO_VERSION,
    }
    return report


def occupation_skill_invalid(row: dict[str, str]) -> int:
    return int(not is_esco_uri(row["esco_occupation_uri"])) + int(not is_esco_uri(row["esco_skill_uri"]))


def skill_rel_invalid(row: dict[str, str]) -> int:
    return int(not is_esco_uri(row["original_skill_uri"])) + int(not is_esco_uri(row["related_skill_uri"]))


def write_report(tables: list[dict[str, Any]]) -> None:
    lines = [
        "# ESCO normalization report",
        "",
        f"Generated at: {utc_now()}",
        f"Source version: {ESCO_VERSION}",
        f"Transformation version: `{TRANSFORMATION_VERSION}`",
        "",
        "ESCO is normalized for skill/occupation identifiers only. It is not an automation-risk target.",
        "Rows are retained unless every identity field is empty. Invalid URIs are counted and kept.",
        "",
    ]
    summary_rows = []
    for table in tables:
        summary_rows.append(
            [
                table["dataset"],
                table["input_row_count"],
                table["output_row_count"],
                table["excluded_row_count"],
                table["invalid_identifier_counts"],
                table["duplicate_identifier_counts"]["duplicate_identifier_values"],
            ]
        )
    lines.append(
        markdown_table(
            ["output", "input rows", "output rows", "excluded", "invalid identifier fields", "duplicate identity values"],
            summary_rows,
        )
    )
    for table in tables:
        lines.extend(
            [
                "",
                f"## {table['dataset']}",
                "",
                f"- Input path: `{table['input_path']}`",
                f"- Input SHA-256: `{table['input_sha256']}`",
                f"- Output path: `{table['output_path']}`",
                f"- Exclusion log: `{table['exclusion_log_path']}`",
                f"- Input row count: {table['input_row_count']}",
                f"- Output row count: {table['output_row_count']}",
                f"- Excluded row count: {table['excluded_row_count']}",
                f"- Column names: {', '.join(f'`{name}`' for name in table['column_names'])}",
                f"- Invalid identifier counts: {table['invalid_identifier_counts']}",
                f"- Duplicate identifier values: {table['duplicate_identifier_counts']['duplicate_identifier_values']}",
                f"- Extra rows due to duplicates: {table['duplicate_identifier_counts']['duplicate_identifier_row_extra']}",
                f"- Transformation version: `{table['transformation_version']}`",
                f"- Source version: `{table['source_version']}`",
                "",
                "Missing-value counts:",
                "",
                markdown_table(
                    ["column", "missing"],
                    [[key, value] for key, value in table["missing_value_counts"].items()],
                ),
            ]
        )
        if table["excluded_rows"]:
            lines.extend(["", "Excluded rows:", ""])
            for row in table["excluded_rows"]:
                lines.append(
                    f"- source row {row['source_row_number']}: {row['reason']} — `{row['raw_preview']}`"
                )
        else:
            lines.extend(["", "Excluded rows: none.", ""])
        if table["duplicate_identifier_counts"]["duplicate_identifier_values"]:
            lines.extend(
                [
                    "",
                    "Duplicate identity values were present in the raw ESCO file and were retained (not dropped).",
                    "",
                ]
            )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> list[dict[str, Any]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tables = [
        normalize_table("occupations_en.csv", OCCUPATION_MAP, ["esco_occupation_uri"], "esco_occupations.csv"),
        normalize_table("skills_en.csv", SKILL_MAP, ["esco_skill_uri"], "esco_skills.csv"),
        normalize_table(
            "occupationSkillRelations_en.csv",
            OCC_SKILL_MAP,
            ["esco_occupation_uri", "esco_skill_uri", "relation_type"],
            "esco_occupation_skill_relations.csv",
            occupation_skill_invalid,
        ),
        normalize_table(
            "skillSkillRelations_en.csv",
            SKILL_REL_MAP,
            ["original_skill_uri", "related_skill_uri", "relation_type"],
            "esco_skill_relations.csv",
            skill_rel_invalid,
        ),
    ]
    write_report(tables)
    write_json(OUT_DIR / "esco_normalization_stats.json", {"generated_at": utc_now(), "tables": tables})
    return tables


if __name__ == "__main__":
    main()
