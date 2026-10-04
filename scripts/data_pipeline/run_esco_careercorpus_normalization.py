#!/usr/bin/env python3
"""Run ESCO and CareerCorpus normalization and write a combined manifest. Does not train."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import normalize_careercorpus
import normalize_esco
from pipeline_common import BASE_DIR, TRANSFORMATION_VERSION, utc_now, write_json

MANIFEST = BASE_DIR / "external_data" / "normalized" / "normalization_manifest.json"


def main() -> None:
    esco = normalize_esco.main()
    career = normalize_careercorpus.main()
    outputs = []
    retained = 0
    excluded = 0
    for name, table in esco["tables"].items():
        outputs.append(table["output_path"])
        retained += table["output_row_count"]
        excluded += table["excluded_row_count"]
    for name, table in career["tables"].items():
        outputs.append(table["output_path"])
        retained += table["output_row_count"]
        excluded += table["excluded_row_count"]
    write_json(
        MANIFEST,
        {
            "generated_at": utc_now(),
            "transformation_version": TRANSFORMATION_VERSION,
            "datasets": ["ESCO v1.2.1", "CareerCorpus"],
            "esco": esco,
            "careercorpus": career,
            "generated_files": outputs
            + [
                "reports/data_quality/esco_normalization_report.md",
                "reports/data_quality/careercorpus_normalization_report.md",
                "external_data/normalized/normalization_manifest.json",
            ],
            "rows_retained_total": retained,
            "rows_excluded_total": excluded,
            "not_trained": True,
        },
    )
    print(MANIFEST)


if __name__ == "__main__":
    main()
