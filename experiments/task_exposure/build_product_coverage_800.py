#!/usr/bin/env python3
"""Build 800-occupation product coverage summaries from the existing 923 benchmark.

Does not retrain. Does not overwrite the 923-occupation experiment reports.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from public_benchmark_common import (  # noqa: E402
    DATA_DIR,
    DERIVED_CSV,
    OCC_MASTER_800,
    REPORT_DIR,
    sha256_file,
    utc_now,
    write_json,
    write_md,
)
from product_copy import MODEL_ID, PRODUCT_LAYER  # noqa: E402

OUT_CSV = DATA_DIR / "product_coverage_800_occupation_summaries.csv"
OUT_OUTSIDE = DATA_DIR / "benchmark_occupations_outside_product_800.csv"


def representative_task(part: pd.DataFrame, label: str) -> str:
    rows = part.loc[part["human_labels"] == label, "task_text"]
    if rows.empty:
        return ""
    return str(rows.iloc[0])


def main() -> int:
    bench = pd.read_csv(DERIVED_CSV, dtype=str, keep_default_na=False)
    selected = pd.read_csv(OCC_MASTER_800, dtype=str, keep_default_na=False)
    selected_codes = selected["occupation_code"].astype(str).str.strip()
    if selected_codes.nunique() != 800 or len(selected_codes) != 800:
        raise SystemExit("800-occupation selection is not exactly 800 unique codes")
    bench_codes = set(bench["occupation_code"].astype(str).str.strip())
    product_codes = set(selected_codes)
    outside = sorted(bench_codes - product_codes)
    rows = []
    for code in selected_codes:
        part = bench[bench["occupation_code"] == code]
        n = int(len(part))
        counts = part["human_labels"].value_counts()
        e0 = int(counts.get("E0", 0))
        e1 = int(counts.get("E1", 0))
        e2 = int(counts.get("E2", 0))
        rows.append(
            {
                "occupation_code": code,
                "occupation_title": part["occupation_title"].iloc[0] if n else "",
                "n_benchmark_tasks": n,
                "E0_task_count": e0,
                "E1_task_count": e1,
                "E2_task_count": e2,
                "E0_proportion": "" if n == 0 else f"{e0 / n:.6f}",
                "E1_proportion": "" if n == 0 else f"{e1 / n:.6f}",
                "E2_proportion": "" if n == 0 else f"{e2 / n:.6f}",
                "example_task_E0": representative_task(part, "E0"),
                "example_task_E1": representative_task(part, "E1"),
                "example_task_E2": representative_task(part, "E2"),
                "source": "GPTs-are-GPTs human_labels on public_gpts_are_gpts_benchmark.csv",
                "model_identity": MODEL_ID,
                "product_layer": PRODUCT_LAYER,
                "research_model_population": "923 occupations / 19265 tasks",
                "not_personal_job_loss": "true",
                "not_jobs_disappearing_percentage": "true",
                "coverage_limitations": (
                    "Task-level benchmark category shares for product coverage. "
                    "Not a probability that workers will lose jobs. "
                    "Absence from this 800-row file does not mean the occupation is absent from the 923-occupation research model."
                ),
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT_CSV, index=False)
    pd.DataFrame({"occupation_code": outside, "in_923_benchmark": True, "in_800_product_subset": False}).to_csv(
        OUT_OUTSIDE, index=False
    )
    write_json(
        REPORT_DIR / "product_coverage_800.json",
        {
            "generated_at": utc_now(),
            "product_subset_occupations": 800,
            "product_subset_path": OCC_MASTER_800.as_posix(),
            "product_subset_sha256": sha256_file(OCC_MASTER_800),
            "summaries_path": OUT_CSV.as_posix(),
            "summaries_sha256": sha256_file(OUT_CSV),
            "benchmark_occupations_outside_800": len(outside),
            "outside_list_path": OUT_OUTSIDE.as_posix(),
            "used_for_model_training": False,
            "note": "Descriptive summaries of published benchmark human_labels. Not a retrained 800-occupation model.",
        },
    )
    write_md(
        REPORT_DIR / "product_coverage_800.md",
        [
            "# Prayash common-occupation coverage — 800 occupations",
            "",
            "This is a **product coverage subset**, not the research model population.",
            "",
            "- Research/model population: 923 occupations, 19,265 tasks.",
            "- Product subset: 800 occupations, all of which have exact benchmark occupation matches.",
            f"- Occupations in the 923 benchmark but outside the 800 subset: {len(outside)}.",
            "- The 923-occupation classifier was **not** retrained on these 800 codes.",
            "",
            "Occupation E0/E1/E2 counts are summaries of published task-level benchmark labels.",
            "They are not the probability that workers will lose their jobs, and not the percentage of jobs that will disappear.",
            "",
        ],
    )
    print(
        {
            "product_occupations": 800,
            "outside_923_not_in_800": len(outside),
            "summaries": OUT_CSV.name,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
