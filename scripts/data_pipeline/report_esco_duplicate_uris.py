#!/usr/bin/env python3
"""Inspect duplicate ESCO URIs in normalized tables. Does not modify raw files or train."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import BASE_DIR, markdown_table

ESCO_DIR = BASE_DIR / "external_data" / "normalized" / "esco"
REPORT_PATH = BASE_DIR / "reports" / "data_quality" / "esco_duplicate_uri_report.md"


def load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def groups(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return {uri: items for uri, items in grouped.items() if len(items) > 1}


def compare_group(items: list[dict[str, str]]) -> dict[str, object]:
    fields = list(items[0].keys())
    conflicting: list[str] = []
    identical_fields: list[str] = []
    for field in fields:
        values = {item.get(field, "") for item in items}
        if len(values) == 1:
            identical_fields.append(field)
        else:
            conflicting.append(field)
    return {
        "n": len(items),
        "identical_row_copies": len(conflicting) == 0,
        "conflicting_fields": conflicting,
        "identical_fields": identical_fields,
        "preferred_label": items[0].get("preferred_label", ""),
    }


def render_section(title: str, key: str, grouped: dict[str, list[dict[str, str]]]) -> list[str]:
    identical_copies = sum(1 for items in grouped.values() if compare_group(items)["identical_row_copies"])
    conflicting_uris = sum(1 for items in grouped.values() if not compare_group(items)["identical_row_copies"])
    lines = [
        f"## {title}",
        "",
        f"- Duplicate {key} values: {len(grouped)}",
        f"- URI groups that are identical extra copies: {identical_copies}",
        f"- URI groups with at least one conflicting field: {conflicting_uris}",
        "",
    ]
    summary = []
    for uri, items in grouped.items():
        info = compare_group(items)
        summary.append(
            [
                uri.replace("http://data.europa.eu/esco/", ""),
                info["n"],
                info["preferred_label"],
                "identical copies" if info["identical_row_copies"] else "conflict: " + ", ".join(info["conflicting_fields"]),
            ]
        )
        lines.extend(
            [
                f"### {uri}",
                "",
                f"- Preferred label: {info['preferred_label']}",
                f"- Occurrences: {info['n']}",
                f"- Verdict: {'identical extra copies of the same source row' if info['identical_row_copies'] else 'conflicting values'}",
                "",
            ]
        )
        if not info["identical_row_copies"]:
            for field in info["conflicting_fields"]:
                values = [item.get(field, "")[:200] for item in items]
                lines.append(f"- `{field}`: {values}")
            lines.append("")
    lines.extend(
        [
            markdown_table(["uri suffix", "n", "preferred_label", "verdict"], summary),
            "",
        ]
    )
    return lines


def main() -> None:
    occupations = groups(load(ESCO_DIR / "esco_occupations.csv"), "esco_occupation_uri")
    skills = groups(load(ESCO_DIR / "esco_skills.csv"), "esco_skill_uri")
    occ_identical = all(compare_group(items)["identical_row_copies"] for items in occupations.values())
    skill_identical = all(compare_group(items)["identical_row_copies"] for items in skills.values())
    lines = [
        "# ESCO duplicate URI report",
        "",
        "Raw ESCO files were not modified. Normalized rows were not deleted. No training.",
        "",
        "Source: `external_data/normalized/esco/esco_occupations.csv` and `esco_skills.csv`.",
        "",
        "## Recommendation (not applied)",
        "",
    ]
    if occ_identical and skill_identical:
        lines.extend(
            [
                "All duplicate occupation and skill URI groups are **identical extra copies** of the same preferred label and other fields.",
                "Later, a controlled `norm-v1.1` table may drop extra copies with `keep=first` keyed on URI.",
                "Until that version exists, keep all source rows so counts stay auditable against the raw CSVs.",
                "For feature joins, collapse to one row per URI (first occurrence) inside the feature builder, not by editing raw files.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "At least one URI group has conflicting fields. Preserve all source rows.",
                "Resolve conflicts only with an explicit rule (for example, keep the longest description, or keep both with a `duplicate_instance` index).",
                "Do not silently pick a label.",
                "",
            ]
        )
    lines.extend(render_section("Duplicate occupation URIs", "esco_occupation_uri", occupations))
    lines.extend(render_section("Duplicate skill URIs", "esco_skill_uri", skills))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)
    print("occupation_groups", len(occupations), "skill_groups", len(skills))
    print("occ_identical", occ_identical, "skill_identical", skill_identical)


if __name__ == "__main__":
    main()
