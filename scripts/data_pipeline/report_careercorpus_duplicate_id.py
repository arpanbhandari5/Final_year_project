#!/usr/bin/env python3
"""Inspect CareerCorpus resume_id 35421497. Does not modify raw data or train."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import BASE_DIR, markdown_table

RESUME_PATH = BASE_DIR / "external_data" / "normalized" / "careercorpus" / "careercorpus_resumes.csv"
ANNOTATION_PATH = BASE_DIR / "external_data" / "normalized" / "careercorpus" / "careercorpus_annotations.csv"
REPORT_PATH = BASE_DIR / "reports" / "data_quality" / "careercorpus_duplicate_resume_id_35421497.md"
TARGET_ID = "35421497"


def load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("resume_id") == TARGET_ID]


def main() -> None:
    resumes = load(RESUME_PATH)
    annotations = load(ANNOTATION_PATH)
    fields = [name for name in (resumes[0].keys() if resumes else []) if name not in {"source_version", "transformation_version"}]
    compare_rows = []
    identical = 0
    differing = 0
    left, right = resumes[0], resumes[1]
    for field in left.keys():
        a, b = left.get(field, ""), right.get(field, "")
        status = "identical" if a == b else "different"
        if field in {"source_version", "transformation_version"}:
            continue
        if a == b:
            identical += 1
        else:
            differing += 1
        compare_rows.append([field, status, a[:180].replace("|", "/"), b[:180].replace("|", "/")])
    ann_left, ann_right = annotations[0], annotations[1]
    classification = (
        "two annotations for one resume (same career narrative, abbreviated vs expanded text, "
        "identical annotator_1_score, different annotator_2_score)"
    )
    lines = [
        "# CareerCorpus duplicate resume_id 35421497",
        "",
        "Raw data was not modified. No training. No policy applied.",
        "",
        f"- Resume rows: {len(resumes)} in `{RESUME_PATH.relative_to(BASE_DIR).as_posix()}`",
        f"- Annotation rows: {len(annotations)} in `{ANNOTATION_PATH.relative_to(BASE_DIR).as_posix()}`",
        f"- Compared content fields identical: {identical}",
        f"- Compared content fields different: {differing}",
        "",
        "## Classification",
        "",
        classification,
        "",
        "They are **not** byte-identical duplicates. They are **not** two unrelated people sharing an ID.",
        "Row 172 is a longer statement of the same education, skills, and work history as row 173.",
        "`annotator_1_score` is 0.73 on both rows. `annotator_2_score` is 0.79 vs 0.66.",
        "",
        "## Field comparison (resumes)",
        "",
        markdown_table(["field", "status", "row 172", "row 173"], compare_rows),
        "",
        "## Annotation comparison",
        "",
        markdown_table(
            ["field", "row 172", "row 173"],
            [
                [field, ann_left.get(field, ""), ann_right.get(field, "")]
                for field in ("resume_id", "annotator_1_score", "annotator_2_score", "source_row_number", "label_source")
            ],
        ),
        "",
        "## Recommended policy (not applied)",
        "",
        "- Keep both raw and normalized rows.",
        "- Add a unique `record_id` such as `{resume_id}:{source_sheet}:{source_row_number}` (`35421497:Sheet1:172` and `35421497:Sheet1:173`).",
        "- Preserve `resume_id=35421497` as the group key.",
        "- For supervised role-matching or skill-extraction evaluation, split by `resume_id` (GroupKFold / GroupShuffleSplit), not by `record_id`.",
        "- Do not put row 172 in train and row 173 in test.",
        "- Do not drop either row until a later documented evaluation-set decision.",
        "",
        "Do not invent O*NET task-exposure labels from these CareerCorpus annotator scores.",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
