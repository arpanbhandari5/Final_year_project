#!/usr/bin/env python3
"""Run ESCO and CareerCorpus normalization only. Does not train."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import BASE_DIR, TRANSFORMATION_VERSION, utc_now, write_json
from normalize_careercorpus import main as normalize_careercorpus
from normalize_esco import main as normalize_esco


def main() -> None:
    esco_tables = normalize_esco()
    career = normalize_careercorpus()
    manifest = {
        "generated_at": utc_now(),
        "transformation_version": TRANSFORMATION_VERSION,
        "phase": "normalize_esco_and_careercorpus_only",
        "trained_model": False,
        "modified_production_data": False,
        "esco": {
            "source_version": "1.2.1",
            "tables": [
                {
                    "dataset": table["dataset"],
                    "input_path": table["input_path"],
                    "input_sha256": table["input_sha256"],
                    "output_path": table["output_path"],
                    "input_row_count": table["input_row_count"],
                    "output_row_count": table["output_row_count"],
                    "excluded_row_count": table["excluded_row_count"],
                    "column_names": table["column_names"],
                    "missing_value_counts": table["missing_value_counts"],
                    "duplicate_identifier_counts": table["duplicate_identifier_counts"],
                    "invalid_identifier_counts": table["invalid_identifier_counts"],
                    "transformation_version": table["transformation_version"],
                    "source_version": table["source_version"],
                }
                for table in esco_tables
            ],
        },
        "careercorpus": {
            "input_path": career["input_path"],
            "input_sha256": career["input_sha256"],
            "source_version": career["source_version"],
            "transformation_version": career["transformation_version"],
            "input_row_count": career["input_row_count"],
            "excluded_row_count": career["excluded_row_count"],
            "tables": career["tables"],
        },
    }
    write_json(BASE_DIR / "external_data" / "normalized" / "normalization_manifest.json", manifest)
    print(f"ESCO tables: {len(esco_tables)}")
    print(f"CareerCorpus resumes: {career['tables'][0]['output_row_count']}")
    print(f"CareerCorpus annotations: {career['tables'][1]['output_row_count']}")
    print(f"CareerCorpus excluded: {career['excluded_row_count']}")


if __name__ == "__main__":
    main()
