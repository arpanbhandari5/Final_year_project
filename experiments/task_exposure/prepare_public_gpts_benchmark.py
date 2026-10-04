#!/usr/bin/env python3
"""Prepare the isolated GPTs-are-GPTs classification dataset.

Does not write Prayash reviewer worksheets, production models, or 248-row reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from public_benchmark_common import (  # noqa: E402
    ALLOWED_HUMAN_LABELS,
    CLAIM_BOUNDARY,
    DATA_DIR,
    DERIVED_CSV,
    GPT_FIELDS,
    HUMAN_TRACK_STATUS,
    OCC_MASTER_800,
    ONET_OCC_MASTER,
    ONET_TASKS,
    PAPER_ONET_VERSION,
    PROJECT_ONET_VERSION,
    RAW_DIR,
    RAW_LABELSET,
    REPORT_DIR,
    ROUND1_R1,
    ROUND1_R2,
    ROUND1_R3,
    SOURCE_COMMIT,
    SOURCE_FILE_URL,
    SOURCE_LICENSE,
    SOURCE_REPO,
    SOURCE_URL,
    SPLIT_MANIFEST,
    SPLIT_SEED,
    TARGET_FIELD,
    TEXT_COLUMN,
    PublicBenchmarkError,
    load_raw_labelset,
    normalize_task_id,
    normalize_task_text,
    occupation_grouped_splits,
    package_versions,
    sha256_file,
    standardize_source,
    utc_now,
    validate_human_labels,
    write_json,
    write_md,
)


def quality_report(frame: pd.DataFrame) -> dict:
    labels = frame[TARGET_FIELD].astype(str).str.strip()
    occ_task = frame["occupation_code"].astype(str) + "|" + frame["task_id"].astype(str)
    text_dup = frame[TEXT_COLUMN].astype(str).str.strip()
    norm = frame["normalized_task_text"]
    gpt_vs_human = {
        field: int((frame[field].astype(str).str.strip() != labels).sum())
        for field in GPT_FIELDS
        if field in frame.columns
    }
    return {
        "rows": int(len(frame)),
        "unique_occupations": int(frame["occupation_code"].nunique()),
        "missing_occupation_code": int((frame["occupation_code"].str.strip() == "").sum()),
        "missing_task_id": int((frame["task_id"].str.strip() == "").sum()),
        "missing_task_text": int((frame[TEXT_COLUMN].str.strip() == "").sum()),
        "missing_human_labels": int((labels == "").sum()),
        "invalid_human_labels": sorted({v for v in labels.unique() if v and v not in ALLOWED_HUMAN_LABELS}),
        "duplicate_occupation_task_pairs": int(occ_task.duplicated().sum()),
        "duplicate_task_ids": int(frame["task_id"].duplicated().sum()),
        "duplicate_task_text": int(text_dup.duplicated().sum()),
        "duplicate_normalized_task_text": int(norm.duplicated().sum()),
        "class_counts": labels.value_counts().sort_index().to_dict(),
        "human_vs_human_exposure_agg_mismatches": int(
            (frame["human_exposure_agg"].astype(str).str.strip() != labels).sum()
        ),
        "human_vs_gpt_mismatches": gpt_vs_human,
        "gpt_fields_excluded_from_target": list(GPT_FIELDS),
    }


def task_id_compatibility(public: pd.DataFrame) -> dict:
    onet = pd.read_csv(ONET_TASKS, dtype=str, keep_default_na=False)
    onet["task_id"] = onet["task_id"].map(normalize_task_id)
    onet["occupation_code"] = onet["occupation_code"].astype(str).str.strip()
    onet["task_text"] = onet["task_statement"].astype(str)
    onet["normalized_task_text"] = onet["task_text"].map(normalize_task_text)
    pub = public.copy()
    pub_ids = set(pub["task_id"])
    onet_ids = set(onet["task_id"])
    exact_id = pub_ids & onet_ids
    pub_occ = set(pub["occupation_code"])
    onet_occ = set(onet["occupation_code"])
    exact_occ = pub_occ & onet_occ
    merged = pub.merge(
        onet[["task_id", "occupation_code", "task_text", "normalized_task_text"]].rename(
            columns={
                "occupation_code": "onet31_occupation_code",
                "task_text": "onet31_task_text",
                "normalized_task_text": "onet31_normalized_task_text",
            }
        ),
        on="task_id",
        how="inner",
    )
    exact_text = int((merged[TEXT_COLUMN] == merged["onet31_task_text"]).sum())
    norm_text = int((merged["normalized_task_text"] == merged["onet31_normalized_task_text"]).sum())
    changed_text = int(len(merged) - exact_text)
    same_occ_diff_id = 0
    for occ in exact_occ:
        p_ids = set(pub.loc[pub["occupation_code"] == occ, "task_id"])
        o_ids = set(onet.loc[onet["occupation_code"] == occ, "task_id"])
        if p_ids != o_ids:
            same_occ_diff_id += 1
    occ_task_mismatch = int((merged["occupation_code"] != merged["onet31_occupation_code"]).sum())
    return {
        "public_task_rows": int(len(pub)),
        "onet31_task_rows": int(len(onet)),
        "exact_task_id_matches": int(len(exact_id)),
        "exact_task_id_match_rate": float(len(exact_id) / max(len(pub_ids), 1)),
        "exact_occupation_code_matches": int(len(exact_occ)),
        "occupation_task_id_pair_mismatches_on_matched_ids": occ_task_mismatch,
        "exact_task_text_matches_among_matched_ids": exact_text,
        "normalized_task_text_matches_among_matched_ids": norm_text,
        "same_task_id_changed_task_text": changed_text,
        "occupations_with_same_code_different_task_ids": same_occ_diff_id,
        "public_source_onet_version_documented": PAPER_ONET_VERSION,
        "project_onet_version": PROJECT_ONET_VERSION,
        "silent_fuzzy_join_used": False,
        "used_as_own_task_corpus": True,
        "note": (
            "Public benchmark task IDs are not treated as O*NET 31.0 IDs. "
            "No fuzzy or semantic label transfer is performed."
        ),
    }


def occupation_coverage(public: pd.DataFrame) -> dict:
    master = pd.read_csv(ONET_OCC_MASTER, dtype=str, keep_default_na=False)
    selected = pd.read_csv(OCC_MASTER_800, dtype=str, keep_default_na=False)
    pub_occ = set(public["occupation_code"].astype(str).str.strip())
    master_occ = set(master["occupation_code"].astype(str).str.strip())
    selected_occ = set(selected["occupation_code"].astype(str).str.strip())
    selected_match = selected_occ & pub_occ
    return {
        "project_occupation_count": int(len(master_occ)),
        "public_benchmark_occupation_count": int(len(pub_occ)),
        "selected_800_occupation_count": int(len(selected_occ)),
        "selected_800_with_exact_benchmark_occupation_match": int(len(selected_match)),
        "selected_800_without_benchmark_occupation_match": int(len(selected_occ - pub_occ)),
        "coverage_percentage": float(100.0 * len(selected_match) / max(len(selected_occ), 1)),
        "public_exact_occupation_matches_to_project_master": int(len(pub_occ & master_occ)),
        "800_selection_modified": False,
    }


def reviewer_sheets_untouched() -> dict:
    payload = {}
    for name, path in (("reviewer1", ROUND1_R1), ("reviewer2", ROUND1_R2), ("third", ROUND1_R3)):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        payload[name] = {
            "path": path.as_posix(),
            "rows": int(len(frame)),
            "filled_reviewer_scores": int((frame["reviewer_score"].astype(str).str.strip() != "").sum()),
            "sha256": sha256_file(path),
        }
    payload["status"] = HUMAN_TRACK_STATUS
    return payload


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_LABELSET.exists():
        raise PublicBenchmarkError(
            f"Source file missing: {RAW_LABELSET}. Download {SOURCE_FILE_URL} without overwriting after success."
        )
    raw = load_raw_labelset()
    standardized = standardize_source(raw)
    label_info = validate_human_labels(standardized)
    quality = quality_report(standardized)
    if quality["invalid_human_labels"]:
        raise PublicBenchmarkError(f"invalid human_labels {quality['invalid_human_labels']}")
    matching = task_id_compatibility(standardized)
    coverage = occupation_coverage(standardized)
    labelled = standardized.loc[standardized[TARGET_FIELD].isin(ALLOWED_HUMAN_LABELS)].copy()
    mapping, split_counts = occupation_grouped_splits(labelled["occupation_code"].tolist(), seed=SPLIT_SEED)
    labelled["split"] = labelled["occupation_code"].map(mapping)
    labelled.to_csv(DERIVED_CSV, index=False)
    train_occ = sorted(code for code, split in mapping.items() if split == "train")
    val_occ = sorted(code for code, split in mapping.items() if split == "validation")
    test_occ = sorted(code for code, split in mapping.items() if split == "test")
    (DATA_DIR / "public_benchmark_train_occupations.csv").write_text(
        "occupation_code\n" + "\n".join(train_occ) + "\n", encoding="utf-8"
    )
    (DATA_DIR / "public_benchmark_validation_occupations.csv").write_text(
        "occupation_code\n" + "\n".join(val_occ) + "\n", encoding="utf-8"
    )
    (DATA_DIR / "public_benchmark_test_occupations.csv").write_text(
        "occupation_code\n" + "\n".join(test_occ) + "\n", encoding="utf-8"
    )
    overlap = split_counts["overlap"]
    by_split = labelled.groupby("split").size().to_dict()
    split_payload = {
        "seed": SPLIT_SEED,
        "method": "occupation_grouped_70_15_15",
        "not_reused_prayash_560_120_120": True,
        "train_occupations": int(split_counts["train"]),
        "validation_occupations": int(split_counts["validation"]),
        "test_occupations": int(split_counts["test"]),
        "train_tasks": int(by_split.get("train", 0)),
        "validation_tasks": int(by_split.get("validation", 0)),
        "test_tasks": int(by_split.get("test", 0)),
        "train_validation_overlap": overlap["train_validation"],
        "train_test_overlap": overlap["train_test"],
        "validation_test_overlap": overlap["validation_test"],
        "train_occupations_list": train_occ,
        "validation_occupations_list": val_occ,
        "test_occupations_list": test_occ,
    }
    write_json(SPLIT_MANIFEST, split_payload)
    provenance = {
        "generated_at": utc_now(),
        "repository": SOURCE_REPO,
        "commit": SOURCE_COMMIT,
        "license": SOURCE_LICENSE,
        "source_url": SOURCE_URL,
        "source_file_url": SOURCE_FILE_URL,
        "source_file": RAW_LABELSET.as_posix(),
        "source_file_sha256": sha256_file(RAW_LABELSET),
        "derived_dataset": DERIVED_CSV.as_posix(),
        "derived_dataset_sha256": sha256_file(DERIVED_CSV),
        "source_rows": int(len(standardized)),
        "source_occupations": int(standardized["occupation_code"].nunique()),
        "rows_with_non_empty_human_labels": int(label_info["non_empty_human_labels"]),
        "human_derived_labelled_task_rows": int(label_info["non_empty_human_labels"]),
        "direct_task_level_human_annotation_count": "not separately recoverable from released file",
        "paper_note": (
            "Eloundou et al. describe annotation of detailed work activities, annotation of a "
            "subset of O*NET tasks, and aggregation to task and occupation levels. The released "
            "file's non-empty human_labels count is not a count of independent direct task reviews."
        ),
        "source_onet_version_documented": PAPER_ONET_VERSION,
        "project_onet_version": PROJECT_ONET_VERSION,
        "package_versions": package_versions(),
        "human_review_track_status": HUMAN_TRACK_STATUS,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    write_json(REPORT_DIR / "source_provenance.json", provenance)
    write_md(
        REPORT_DIR / "source_provenance.md",
        [
            "# Public GPTs-are-GPTs source provenance",
            "",
            f"Repository: `{SOURCE_REPO}`",
            f"Commit: `{SOURCE_COMMIT}`",
            f"License: `{SOURCE_LICENSE}`",
            f"Source rows: {provenance['source_rows']}",
            f"Source occupations: {provenance['source_occupations']}",
            "",
            "```text",
            f"Rows with non-empty human_labels: {provenance['rows_with_non_empty_human_labels']}",
            f"Human-derived labelled task rows: {provenance['human_derived_labelled_task_rows']}",
            "Direct task-level human annotation count: not separately recoverable from released file",
            "```",
            "",
            "The released benchmark contains these task rows with non-empty human-derived exposure labels under the GPTs-are-GPTs taxonomy.",
            "Do not state that every labelled row received an independent direct human review.",
            "",
            provenance["paper_note"],
            "",
            CLAIM_BOUNDARY,
            "",
        ],
    )
    write_json(REPORT_DIR / "dataset_quality.json", {**quality, "label_info": label_info})
    write_md(
        REPORT_DIR / "dataset_quality.md",
        [
            "# Dataset quality",
            "",
            f"Usable labelled tasks (E0/E1/E2): {int(len(labelled))}",
            f"Unique occupations (labelled): {int(labelled['occupation_code'].nunique())}",
            f"Missing labels: {quality['missing_human_labels']}",
            f"Invalid labels: {quality['invalid_human_labels'] or 'none'}",
            f"Duplicate occupation/task pairs: {quality['duplicate_occupation_task_pairs']}",
            f"Class counts: {json.dumps(quality['class_counts'])}",
            f"Human vs GPT-4 field mismatches: {json.dumps(quality['human_vs_gpt_mismatches'])}",
            "",
            "GPT-4 fields are preserved and are not used as the training target.",
            "No automatic class rebalancing was applied.",
            "",
        ],
    )
    write_json(REPORT_DIR / "occupation_coverage.json", {**coverage, "task_matching": matching})
    write_md(
        REPORT_DIR / "occupation_coverage.md",
        [
            "# Occupation coverage and task-ID compatibility",
            "",
            f"Project occupation master count: {coverage['project_occupation_count']}",
            f"Public benchmark occupation count: {coverage['public_benchmark_occupation_count']}",
            f"Selected 800 occupation count: {coverage['selected_800_occupation_count']}",
            f"Selected 800 with exact benchmark occupation match: {coverage['selected_800_with_exact_benchmark_occupation_match']}",
            f"Selected 800 without benchmark occupation match: {coverage['selected_800_without_benchmark_occupation_match']}",
            f"Coverage percentage: {coverage['coverage_percentage']:.2f}",
            "",
            f"Exact occupation matches (public vs O*NET 31.0 master): {coverage['public_exact_occupation_matches_to_project_master']}",
            f"Exact task-ID matches: {matching['exact_task_id_matches']}",
            f"Task-ID match rate: {matching['exact_task_id_match_rate']:.4f}",
            f"Exact text matches among matched IDs: {matching['exact_task_text_matches_among_matched_ids']}",
            f"Normalized text matches among matched IDs: {matching['normalized_task_text_matches_among_matched_ids']}",
            f"Same task ID but changed task text: {matching['same_task_id_changed_task_text']}",
            f"Version difference: public paper O*NET {PAPER_ONET_VERSION} vs project O*NET {PROJECT_ONET_VERSION}",
            "",
            matching["note"],
            "",
            "The existing 800-occupation selection was not regenerated.",
            "",
        ],
    )
    write_json(REPORT_DIR / "reviewer_track_status.json", reviewer_sheets_untouched())
    write_md(
        REPORT_DIR / "README.md",
        [
            "# Public GPTs-are-GPTs classification experiment",
            "",
            "Separate from the 248-row provisional AI weak-supervision experiment, the deferred Prayash human-review worksheets, the production model, and `evaluation.py`.",
            "",
            f"Human-review track status: `{HUMAN_TRACK_STATUS}`",
            "",
            "Primary target: `human_labels` in {E0, E1, E2}.",
            "E0 = no direct LLM exposure; E1 = direct LLM exposure; E2 = exposure through an LLM-powered application.",
            "Do not map these classes onto the Prayash 0.00–1.00 rubric.",
            "",
            CLAIM_BOUNDARY,
            "",
            "The model does not predict personal job-loss risk, employment probability, or individual displacement.",
            "",
        ],
    )
    print(
        json.dumps(
            {
                "source_rows": provenance["source_rows"],
                "labelled_rows": int(len(labelled)),
                "occupations": provenance["source_occupations"],
                "missing_labels": quality["missing_human_labels"],
                "split": {
                    k: split_payload[k]
                    for k in (
                        "train_occupations",
                        "validation_occupations",
                        "test_occupations",
                        "train_tasks",
                        "validation_tasks",
                        "test_tasks",
                    )
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
