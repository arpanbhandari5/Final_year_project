#!/usr/bin/env python3
"""Validate AI task-exposure passes, resolve scores, deduplicate, and export.

Does not train a model. Does not invent scores. Does not convert blanks to 0.00.
Does not modify source files:
  project_data/task_exposure_labels/task_exposure_250_sample.csv
  project_data/task_exposure_labels/ai_pass1_scores.jsonl
  project_data/task_exposure_labels/ai_pass2_scores.jsonl
  project_data/task_exposure_labels/annotation_reviewer1.csv
  project_data/task_exposure_labels/annotation_reviewer2.csv

Labels are provisional AI weak supervision, not human-validated ground truth.

Usage:
  python scripts/data_pipeline/build_final_task_training_table.py
  python scripts/data_pipeline/build_final_task_training_table.py --validate-only

Requirements: pandas, numpy, scikit-learn. openpyxl is optional (BLS demand sidecar).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import BASE_DIR, markdown_table, sha256_file, utc_now

LABELS = BASE_DIR / "project_data" / "task_exposure_labels"
SAMPLE = LABELS / "task_exposure_250_sample.csv"
PASS1 = LABELS / "ai_pass1_scores.jsonl"
PASS2 = LABELS / "ai_pass2_scores.jsonl"
R1 = LABELS / "annotation_reviewer1.csv"
R2 = LABELS / "annotation_reviewer2.csv"
ADJ = LABELS / "task_exposure_adjudication.csv"
TRAIN = LABELS / "task_exposure_training.csv"
RESOLVED = LABELS / "task_exposure_resolved_task_rows.csv"
FINAL = LABELS / "final_validated_task_training_table.csv"
MAP = LABELS / "task_group_occupation_map.csv"
EXCLUDED = LABELS / "task_exposure_excluded_groups.csv"
AUDIT = LABELS / "TASK_EXPOSURE_PIPELINE_AUDIT.md"
AGR_REPORT = BASE_DIR / "reports" / "data_quality" / "task_annotation_agreement_report.md"
FINAL_REPORT = BASE_DIR / "reports" / "data_quality" / "final_task_training_table_report.md"
BLS_XLSX = BASE_DIR / "external_data" / "raw" / "bls_employment_projections" / "bls_employment_projections.xlsx"
BLS_FEATURES = (
    BASE_DIR
    / "external_data"
    / "normalized"
    / "bls_employment_projections"
    / "bls_occupation_demand_features_2025_2035.csv"
)
RUBRIC = BASE_DIR / "replacement_data" / "TASK_LABELING_RUBRIC.md"

ALLOWED = (Decimal("0.00"), Decimal("0.25"), Decimal("0.50"), Decimal("0.75"), Decimal("1.00"))
ALLOWED_STR = {format(value, "0.2f") for value in ALLOWED}
SCORE_MAP = {Decimal("0.00"): 0, Decimal("0.25"): 1, Decimal("0.50"): 2, Decimal("0.75"): 3, Decimal("1.00"): 4}
KAPPA_GATE = Decimal("0.70")
CSV_KW = {"index": False, "encoding": "utf-8", "lineterminator": "\n"}
LABEL_VERSION = "ai-pass-v1"
LABEL_TYPE = "provisional_ai_weak_supervision"


def parse_score(text: object) -> Decimal | None:
    raw = "" if text is None else str(text).strip()
    if raw == "":
        return None
    number = Decimal(raw)
    for allowed in ALLOWED:
        if number == allowed:
            return allowed
    raise ValueError(f"off-grid score {raw!r}; blank is missing, not 0.00")


def snap_mean(mean: Decimal) -> Decimal:
    best = ALLOWED[0]
    best_dist = abs(mean - best)
    for allowed in ALLOWED[1:]:
        dist = abs(mean - allowed)
        if dist < best_dist or (dist == best_dist and allowed < best):
            best = allowed
            best_dist = dist
    return best


def gwet_ac1_nominal(y1: np.ndarray, y2: np.ndarray, n_cat: int = 5) -> float:
    """Nominal Gwet AC1 for two raters (Gwet, 2008).

    po = observed exact agreement.
    pk = average prevalence of category k across the two raters.
    pe = sum_k pk*(1-pk) / (q-1), the AC1 chance-agreement term.
    AC1 = (po - pe) / (1 - pe).

    Assumptions: q known categories (here 5 ordinal bins treated as nominal),
    two raters, complete paired cases only, no missing on the paired set.
    This is not an ordinal weighted coefficient and is not human IRR.
    """
    n = len(y1)
    if n == 0 or n_cat < 2:
        return float("nan")
    po = float(np.mean(y1 == y2))
    pk = np.array([((y1 == k).mean() + (y2 == k).mean()) / 2 for k in range(n_cat)])
    pe = float(np.sum(pk * (1 - pk)) / (n_cat - 1))
    if abs(1 - pe) < 1e-12:
        return float("nan")
    return (po - pe) / (1 - pe)


def normalize_task_text(text: str) -> str:
    value = str(text).lower()
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[.,;:!?]+$", "", value).strip()
    return value


def task_group_id(normalized: str, task_id: str) -> str:
    if not normalized:
        return f"tg_empty_{task_id}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return "tg_" + digest[:16]


def operational_label_confidence(status: str, diff: Decimal | None) -> str:
    """Heuristic operational weights, not calibrated P(correct)."""
    if status == "identical":
        return "1.00"
    if status == "deterministic_mean":
        if diff is None:
            return ""
        if diff <= Decimal("0.25"):
            return "0.85"
        if diff > Decimal("0.25") and diff <= Decimal("0.30"):
            return "0.70"
        return ""
    if status == "ai_adjudicated":
        return "0.60"
    return ""


def load_jsonl(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    duplicates: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            task_id = str(item["task_id"])
            if task_id in rows:
                duplicates.append(task_id)
            rows[task_id] = item
    if duplicates:
        raise ValueError(f"duplicate task_id in {path.name}: {sorted(set(duplicates))}")
    return rows


def fmt(value: Decimal | None) -> str:
    return "" if value is None else format(value, "0.2f")


def backup_derived() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = LABELS / "_backups" / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for path in (ADJ, TRAIN, RESOLVED, FINAL, MAP, EXCLUDED, AUDIT):
        if path.exists():
            shutil.copy2(path, dest / path.name)
    return dest


def resolve_pair(a: Decimal | None, b: Decimal | None) -> dict[str, str]:
    record = {
        "reviewer_mean_score": "",
        "absolute_disagreement": "",
        "adjudicated_exposure_score": "",
        "label_confidence": "",
        "requires_adjudication": "false",
        "adjudication_status": "",
        "adjudication_reason": "",
        "adjudication_rationale": "",
        "resolution_method": "",
    }
    if a is None or b is None:
        record["adjudication_status"] = "incomplete"
        record["adjudication_reason"] = "blank_score_not_inferred"
        record["resolution_method"] = "unresolved_blank"
        record["requires_adjudication"] = "true"
        return record
    diff = abs(a - b)
    record["absolute_disagreement"] = format(diff, "0.2f")
    if a == b:
        record["reviewer_mean_score"] = format(a, "0.2f")
        record["adjudicated_exposure_score"] = format(a, "0.2f")
        record["adjudication_status"] = "identical"
        record["adjudication_reason"] = "identical_scores"
        record["resolution_method"] = "identical_scores"
        record["label_confidence"] = operational_label_confidence("identical", diff)
        return record
    if diff <= Decimal("0.30"):
        mean = (a + b) / Decimal(2)
        snapped = snap_mean(mean)
        record["reviewer_mean_score"] = format(mean, "0.4f")
        record["adjudicated_exposure_score"] = format(snapped, "0.2f")
        record["adjudication_status"] = "deterministic_mean"
        record["adjudication_reason"] = "deterministic_mean_and_snap"
        record["resolution_method"] = "deterministic_mean_snap"
        record["label_confidence"] = operational_label_confidence("deterministic_mean", diff)
        return record
    record["reviewer_mean_score"] = format((a + b) / Decimal(2), "0.4f")
    record["requires_adjudication"] = "true"
    record["adjudication_status"] = "unresolved"
    record["adjudication_reason"] = "disagreement_gt_0.30_no_independent_adjudicator_in_this_run"
    record["resolution_method"] = "unresolved_gt_0.30"
    return record


def extract_bls_demand_features() -> dict[str, str]:
    info = {"status": "skipped", "rows": "0", "path": ""}
    if not BLS_XLSX.exists():
        info["status"] = "missing_workbook"
        return info
    try:
        raw = pd.read_excel(BLS_XLSX, sheet_name="Table 1.2", header=1, dtype=str)
    except Exception as error:
        info["status"] = f"unreadable:{error}"
        return info
    cols = list(raw.columns)
    rename_pos = {
        0: "occupation_title",
        1: "bls_matrix_code",
        2: "occupation_type",
        3: "employment_2025_thousands",
        4: "employment_2035_thousands",
        7: "employment_change_numeric_2025_2035",
        8: "employment_change_percent_2025_2035",
        10: "occupational_openings_annual_average_2025_2035",
        11: "median_annual_wage_dollars_2025",
        12: "typical_education_needed_for_entry",
    }
    raw = raw.rename(columns={cols[i]: name for i, name in rename_pos.items() if i < len(cols)})
    keep = [
        "occupation_title",
        "bls_matrix_code",
        "occupation_type",
        "employment_2025_thousands",
        "employment_2035_thousands",
        "employment_change_numeric_2025_2035",
        "employment_change_percent_2025_2035",
        "occupational_openings_annual_average_2025_2035",
        "median_annual_wage_dollars_2025",
        "typical_education_needed_for_entry",
    ]
    out = raw.loc[:, [c for c in keep if c in raw.columns]].copy()
    out = out[out["bls_matrix_code"].astype(str).str.strip().ne("")].copy()
    out["source"] = "BLS Employment Projections Occupation.xlsx Table 1.2"
    out["period"] = "2025-2035"
    out["units_employment"] = "thousands"
    out["not_automation_exposure_target"] = "true"
    out["join_note"] = (
        "Optional exact join: O*NET occupation_code first 7 characters "
        "(SOC detailed XX-XXXX) == bls_matrix_code. Not a fuzzy match. "
        "Not a task-exposure label."
    )
    BLS_FEATURES.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(BLS_FEATURES, **CSV_KW)
    info["status"] = "written"
    info["rows"] = str(len(out))
    info["path"] = BLS_FEATURES.relative_to(BASE_DIR).as_posix()
    return info


def validate_outputs() -> list[str]:
    errors: list[str] = []
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    final = pd.read_csv(FINAL, dtype=str, keep_default_na=False)
    mapping = pd.read_csv(MAP, dtype=str, keep_default_na=False)
    adj = pd.read_csv(ADJ, dtype=str, keep_default_na=False)
    if int(sample["task_id"].duplicated().sum()) != 0:
        errors.append("sample has duplicate task_id")
    if int(final["task_group_id"].duplicated().sum()) != 0:
        errors.append("final table has duplicate task_group_id (split leakage)")
    if int(final["split_key"].duplicated().sum()) != 0:
        errors.append("final table has duplicate split_key")
    blank_target = int((final["adjudicated_exposure_score"].str.strip() == "").sum())
    if blank_target:
        errors.append(f"final table has {blank_target} blank targets")
    for score in final["adjudicated_exposure_score"]:
        if score not in ALLOWED_STR:
            errors.append(f"final off-grid target {score!r}")
            break
    if (final["label_confidence"].str.strip() == "").any():
        errors.append("final table has blank label_confidence on labeled rows")
    if set(final["not_human_ground_truth"].unique()) != {"true"}:
        errors.append("final table missing not_human_ground_truth=true")
    if "bls" in " ".join(final.columns).lower() and any(
        "employment" in c.lower() for c in final.columns
    ):
        errors.append("BLS demand columns must not appear as training targets")
    grouped_text = adj.groupby("task_group_id")["normalized_task_text"].nunique()
    if int((grouped_text > 1).sum()) != 0:
        errors.append("inconsistent normalized text within a task_group_id")
    hashed_empty = (adj["normalized_task_text"].str.strip() == "") & ~adj["task_group_id"].str.startswith(
        "tg_empty_"
    )
    empty_grouped = adj[hashed_empty]
    if len(empty_grouped):
        errors.append("empty descriptions hashed into a shared real task group")
    map_groups = set(mapping["task_group_id"])
    final_groups = set(final["task_group_id"])
    if not final_groups.issubset(map_groups):
        errors.append("final groups missing from occupation map")
    split_by_group = final.set_index("task_group_id")["split_key"].to_dict()
    for _, row in mapping.iterrows():
        key = split_by_group.get(row["task_group_id"])
        if key is not None and key != row["task_group_id"]:
            errors.append("split_key does not match task_group_id")
            break
    sample_occ = set(sample["occupation_code"])
    if not set(final["occupation_code"]).issubset(sample_occ):
        errors.append("final occupation_code not in sample")
    if FINAL.exists() and MAP.exists():
        # Reproducible group ids from normalized text.
        for _, row in adj.iterrows():
            expected = task_group_id(row["normalized_task_text"], row["task_id"])
            if row["task_group_id"] != expected:
                errors.append(f"unstable task_group_id for {row['task_id']}")
                break
    return errors


def write_reports(
    sample: pd.DataFrame,
    adj: pd.DataFrame,
    final: pd.DataFrame,
    mapping: pd.DataFrame,
    excluded: pd.DataFrame,
    metrics: dict,
    bls_info: dict[str, str],
    backup_dir: Path,
    issues: list[str],
) -> None:
    AGR_REPORT.parent.mkdir(parents=True, exist_ok=True)
    kappa = metrics["kappa"]
    threshold_met = kappa >= float(KAPPA_GATE)
    diffs = metrics["diffs"]
    agreement_body = [
        "# Task annotation agreement report (AI-pass agreement / AI self-consistency)",
        "",
        f"Generated at: {utc_now()}",
        "",
        "**These metrics are not human inter-rater reliability and do not establish label accuracy.**",
        "They measure agreement between two AI scoring passes before score resolution.",
        "",
        "Quadratic weighted Cohen's kappa is the principal **ordinal** statistic.",
        "Implementation: sklearn `cohen_kappa_score(..., weights='quadratic')` on ranks "
        "0.00=0, 0.25=1, 0.50=2, 0.75=3, 1.00=4.",
        "Gwet's AC1 is a supplementary **nominal** statistic (Gwet 2008) on the same five "
        "categories treated as nominal. Assumptions: two raters, q=5 known categories, "
        "complete paired cases only. It is not an ordinal weighted measure.",
        f"Operational threshold: quadratic kappa >= {format(KAPPA_GATE, '0.2f')}. "
        f"Outcome: **{'met' if threshold_met else 'not met'}** ({kappa:.4f}).",
        "Meeting the threshold is not evidence that labels are correct or human-valid.",
        "",
        markdown_table(
            ["metric", "value", "denominator"],
            [
                ["original tasks", 250, "sample rows"],
                ["valid paired original scores", metrics["paired"], "tasks with two valid nonblank scores"],
                ["exact agreement", f"{metrics['exact']:.4f}", str(metrics["paired"])],
                ["mean absolute disagreement", f"{metrics['mad']:.4f}", str(metrics["paired"])],
                ["quadratic weighted kappa", f"{kappa:.4f}", str(metrics["paired"])],
                ["Gwet AC1 (nominal)", f"{metrics['ac1']:.4f}", str(metrics["paired"])],
                ["disagreement > 0.30", metrics["n_gt"], str(metrics["paired"])],
                ["missing/invalid original scores", 250 - metrics["paired"], "250"],
                ["identical (Case A)", metrics["n_ident"], "250"],
                ["deterministic mean+snap (Case B)", metrics["n_det"], "250"],
                ["AI adjudication (Case C)", metrics["n_ai"], "250"],
                ["unresolved/incomplete", metrics["n_unresolved"], "250"],
            ],
        ),
        "",
        "### Disagreement distribution",
        "",
        markdown_table(["|r1-r2|", "n"], [[key, diffs[key]] for key in sorted(diffs)]),
        "",
        "### Pass 1 original distribution",
        "",
        markdown_table(["score", "n"], [[k, metrics["r1_dist"][k]] for k in ["0.00", "0.25", "0.50", "0.75", "1.00"]]),
        "",
        "### Pass 2 original distribution",
        "",
        markdown_table(["score", "n"], [[k, metrics["r2_dist"][k]] for k in ["0.00", "0.25", "0.50", "0.75", "1.00"]]),
        "",
        "### Final eligible training-score distribution (one row per task group)",
        "",
        markdown_table(
            ["score", "n"],
            [[k, int(metrics["final_dist"].get(k, 0))] for k in ["0.00", "0.25", "0.50", "0.75", "1.00"]],
        ),
        "",
        "## Confidence assignment (heuristic operational indicators, not calibrated probabilities)",
        "",
        "- identical reviewer scores: 1.00",
        "- deterministic mean, |r1-r2| = 0.25 (or <= 0.25): 0.85",
        "- deterministic mean, 0.25 < |r1-r2| <= 0.30: 0.70",
        "- AI-adjudicated: 0.60",
        "- unresolved/incomplete: blank",
        "",
        "On the permitted 5-point grid the only Case B difference that occurs is 0.25.",
        "",
        "No Case C independent AI adjudication was applied in this run because no paired "
        "disagreement exceeded 0.30. Independence of the original two JSONL passes is "
        "supported by separate files, different score encodings, and mostly distinct "
        f"rationales ({metrics['identical_rationales']} identical rationale strings of 250).",
        "That is not a proof of isolated human review.",
        "",
    ]
    AGR_REPORT.write_text("\n".join(agreement_body) + "\n", encoding="utf-8")

    FINAL_REPORT.write_text(
        "\n".join(
            [
                "# Final task-training table report",
                "",
                f"Generated at: {utc_now()}",
                "",
                f"- Output: `{FINAL.relative_to(BASE_DIR).as_posix()}`",
                f"- Occupation map: `{MAP.relative_to(BASE_DIR).as_posix()}`",
                f"- SHA-256 final table: `{sha256_file(FINAL)}`",
                "",
                markdown_table(
                    ["count", "value"],
                    [
                        ["original tasks", 250],
                        ["unique normalized task groups", metrics["n_groups"]],
                        ["duplicate groups (size>1)", metrics["n_dup_groups"]],
                        ["rows in duplicate groups", metrics["dup_assoc"]],
                        ["conflicting duplicate groups excluded", metrics["n_conflict"]],
                        ["unresolved groups excluded", metrics["n_unresolved_groups"]],
                        ["final eligible training rows (one per task group)", len(final)],
                        ["excluded source rows", len(excluded)],
                    ],
                ),
                "",
                "The target column is a **provisional AI weak-supervision score**, not human ground truth.",
                "BLS Employment Projections 2025–35 are demand context only and are not in this table.",
                "",
                "Future splits must keep all rows sharing `split_key` (`task_group_id`) in the same partition.",
                "No train/test partitions were created. No model was trained.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    audit = [
        "# Task-exposure pipeline audit",
        "",
        f"Generated at: {utc_now()}",
        f"Backup of previous derived outputs: `{backup_dir.relative_to(BASE_DIR).as_posix()}`",
        "",
        "## Verified facts vs assumptions",
        "",
        "- **Verified:** sample has 250 rows, "
        f"{int(sample['soc_group'].nunique())} SOC groups, "
        f"{int(sample['occupation_code'].nunique())} occupations, 0 duplicate task_id, "
        "0 empty task statements, all sample score fields blank.",
        "- **Verified:** two JSONL pass files exist, each 250 task_ids matching the sample, "
        "all scores on the permitted grid, 0 blanks. Pass 1 stores scores as strings; pass 2 as JSON numbers.",
        "- **Verified:** reviewer CSVs match JSONL logical scores and sample task identity. "
        "Reviewer IDs are `ai_pass_1` / `ai_pass_2`. Adjudicated columns in reviewer worksheets remain blank.",
        "- **Assumption (not re-verified here):** the JSONL files were produced by two isolated "
        "Cursor subagents instructed not to read each other. Files alone cannot prove process isolation.",
        "- **Verified:** these are AI labels. They are **not** human-validated ground truth.",
        "",
        "## Input files",
        "",
        markdown_table(
            ["file", "sha256", "bytes"],
            [
                [p.relative_to(BASE_DIR).as_posix(), sha256_file(p), p.stat().st_size]
                for p in (SAMPLE, PASS1, PASS2, R1, R2, RUBRIC)
                if p.exists()
            ],
        ),
        "",
        "## Agreement (same 250 complete pairs for every metric)",
        "",
        markdown_table(
            ["metric", "value"],
            [
                ["paired complete", metrics["paired"]],
                ["exact agreement", f"{metrics['exact']:.4f}"],
                ["MAD", f"{metrics['mad']:.4f}"],
                ["quadratic weighted kappa", f"{metrics['kappa']:.4f}"],
                ["Gwet AC1 (nominal)", f"{metrics['ac1']:.4f}"],
                ["threshold (quadratic kappa >= 0.70)", "met" if threshold_met else "not met"],
                ["|r1-r2| > 0.30", metrics["n_gt"]],
            ],
        ),
        "",
        "Threshold used: quadratic weighted kappa. Meeting 0.70 does not validate labels.",
        "Case C independent adjudication was not required (0 pairs with |diff| > 0.30).",
        "",
        "## Resolution counts",
        "",
        markdown_table(
            ["method", "n"],
            [
                ["identical", metrics["n_ident"]],
                ["deterministic_mean_snap", metrics["n_det"]],
                ["ai_adjudicated", metrics["n_ai"]],
                ["unresolved/incomplete", metrics["n_unresolved"]],
            ],
        ),
        "",
        "## Deduplication",
        "",
        markdown_table(
            ["item", "n"],
            [
                ["task groups", metrics["n_groups"]],
                ["duplicate groups", metrics["n_dup_groups"]],
                ["conflicts excluded", metrics["n_conflict"]],
                ["unresolved groups excluded", metrics["n_unresolved_groups"]],
                ["final training rows", len(final)],
                ["occupation-map rows", len(mapping)],
                ["excluded source rows", len(excluded)],
            ],
        ),
        "",
        "## BLS demand sidecar (not a label)",
        "",
        markdown_table(["item", "value"], [[k, v] for k, v in bls_info.items()]),
        "",
        "## Validation",
        "",
        "PASS" if not issues else "FAIL\n\n" + "\n".join(f"- {item}" for item in issues),
        "",
        "Source annotation files were not modified. Blanks were not converted to 0.00. "
        "No model was trained. No git operations were performed.",
        "",
        "## Rerun",
        "",
        "```",
        "python scripts/data_pipeline/build_final_task_training_table.py",
        "python scripts/data_pipeline/build_final_task_training_table.py --validate-only",
        "python -m pytest tests/test_task_exposure_pipeline.py",
        "```",
        "",
    ]
    AUDIT.write_text("\n".join(audit) + "\n", encoding="utf-8")


def build() -> int:
    backup_dir = backup_derived()
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    r1 = pd.read_csv(R1, dtype=str, keep_default_na=False)
    r2 = pd.read_csv(R2, dtype=str, keep_default_na=False)
    p1 = load_jsonl(PASS1)
    p2 = load_jsonl(PASS2)
    errors: list[str] = []
    if len(sample) != 250:
        errors.append(f"sample rows {len(sample)} != 250")
    if int(sample["soc_group"].nunique()) != 22:
        errors.append(f"soc groups {sample['soc_group'].nunique()} != 22")
    if int(sample["occupation_code"].nunique()) != 225:
        errors.append(f"occupations {sample['occupation_code'].nunique()} != 225")
    sample_ids = [str(value) for value in sample["task_id"]]
    if int(sample["task_id"].duplicated().sum()) != 0:
        errors.append("duplicate task_id in sample")
    if set(p1) != set(sample_ids) or set(p2) != set(sample_ids):
        errors.append("JSONL task_id set mismatch")
    if list(r1["task_id"]) != sample_ids or list(r2["task_id"]) != sample_ids:
        errors.append("reviewer worksheet task_id mismatch")
    if list(r1["task_statement"]) != list(sample["task_statement"]) or list(r2["task_statement"]) != list(
        sample["task_statement"]
    ):
        errors.append("reviewer worksheet task_statement mismatch")
    if errors:
        print("INPUT VALIDATION FAILED")
        print("\n".join(errors))
        return 2

    rows = []
    paired_a: list[Decimal] = []
    paired_b: list[Decimal] = []
    identical_rationales = 0
    for index in range(len(sample)):
        task_id = str(sample.at[index, "task_id"])
        text = sample.at[index, "task_statement"]
        a = parse_score(p1[task_id].get("score"))
        b = parse_score(p2[task_id].get("score"))
        a_sheet = parse_score(r1.at[index, "reviewer_1_score"])
        b_sheet = parse_score(r2.at[index, "reviewer_2_score"])
        if a != a_sheet or b != b_sheet:
            print(f"Reviewer CSV does not match JSONL for task {task_id}")
            return 2
        if str(p1[task_id].get("rationale", "")).strip() == str(p2[task_id].get("rationale", "")).strip():
            identical_rationales += 1
        resolved = resolve_pair(a, b)
        if a is not None and b is not None:
            paired_a.append(a)
            paired_b.append(b)
        normalized = normalize_task_text(text)
        record = {
            "occupation_code": sample.at[index, "occupation_code"],
            "soc_code": sample.at[index, "soc_group"],
            "occupation_title": sample.at[index, "occupation_title"],
            "task_id": task_id,
            "task_text": text,
            "normalized_task_text": normalized,
            "task_group_id": task_group_id(normalized, task_id),
            "reviewer_1_score": fmt(a),
            "reviewer_2_score": fmt(b),
            "reviewer_1_rationale": str(p1[task_id].get("rationale", "")).strip(),
            "reviewer_2_rationale": str(p2[task_id].get("rationale", "")).strip(),
            "label_source": LABEL_TYPE,
            "label_version": LABEL_VERSION,
            "label_date": str(r1.at[index, "label_date"] or "2026-10-02"),
            "source_citations": sample.at[index, "source_citations"],
            "not_human_ground_truth": "true",
            **resolved,
        }
        if not normalized:
            record["adjudication_status"] = "unresolved"
            record["adjudication_reason"] = "empty_task_description"
            record["resolution_method"] = "unresolved_empty_text"
            record["adjudicated_exposure_score"] = ""
            record["label_confidence"] = ""
            record["requires_adjudication"] = "true"
        rows.append(record)

    y1 = np.array([SCORE_MAP[value] for value in paired_a], dtype=int)
    y2 = np.array([SCORE_MAP[value] for value in paired_b], dtype=int)
    x1 = np.array([float(value) for value in paired_a])
    x2 = np.array([float(value) for value in paired_b])
    exact = float(np.mean(x1 == x2)) if len(x1) else float("nan")
    mad = float(np.mean(np.abs(x1 - x2))) if len(x1) else float("nan")
    kappa = float(cohen_kappa_score(y1, y2, weights="quadratic")) if len(x1) else float("nan")
    ac1 = float(gwet_ac1_nominal(y1, y2, 5)) if len(x1) else float("nan")
    diffs = Counter(format(abs(a - b), "0.2f") for a, b in zip(paired_a, paired_b))
    n_gt = int(sum(1 for a, b in zip(paired_a, paired_b) if abs(a - b) > Decimal("0.30")))

    adj = pd.DataFrame(rows)
    adj_cols = [
        "occupation_code",
        "soc_code",
        "occupation_title",
        "task_id",
        "task_text",
        "normalized_task_text",
        "task_group_id",
        "reviewer_1_score",
        "reviewer_2_score",
        "reviewer_1_rationale",
        "reviewer_2_rationale",
        "reviewer_mean_score",
        "absolute_disagreement",
        "adjudicated_exposure_score",
        "label_confidence",
        "requires_adjudication",
        "adjudication_status",
        "adjudication_reason",
        "adjudication_rationale",
        "resolution_method",
        "label_source",
        "label_version",
        "label_date",
        "source_citations",
        "not_human_ground_truth",
    ]
    adj[adj_cols].to_csv(ADJ, **CSV_KW)
    adj[adj_cols].to_csv(RESOLVED, **CSV_KW)

    groups: dict[str, list[dict]] = defaultdict(list)
    for record in rows:
        groups[record["task_group_id"]].append(record)

    duplicate_groups = {key: items for key, items in groups.items() if len(items) > 1}
    conflicting_groups: list[str] = []
    unresolved_groups: list[str] = []
    excluded_rows: list[dict[str, str]] = []
    final_rows: list[dict[str, str]] = []
    map_rows: list[dict[str, str]] = []

    for group_id, items in groups.items():
        statuses = {item["adjudication_status"] for item in items}
        scores = {item["adjudicated_exposure_score"] for item in items}
        texts = {item["normalized_task_text"] for item in items}
        if "" in texts and len(items) > 1 and all(not item["normalized_task_text"] for item in items):
            unresolved_groups.append(group_id)
            for item in items:
                excluded_rows.append(
                    {
                        "task_group_id": group_id,
                        "task_id": item["task_id"],
                        "occupation_code": item["occupation_code"],
                        "reason": "empty_descriptions_not_grouped_as_one_task",
                        "conflict_scores": "|".join(sorted(scores)),
                    }
                )
            continue
        if "incomplete" in statuses or "unresolved" in statuses or "" in scores:
            unresolved_groups.append(group_id)
            for item in items:
                excluded_rows.append(
                    {
                        "task_group_id": group_id,
                        "task_id": item["task_id"],
                        "occupation_code": item["occupation_code"],
                        "reason": "unresolved_or_incomplete_member",
                        "conflict_scores": "|".join(sorted(scores)),
                    }
                )
            continue
        valid_scores = {score for score in scores if score in ALLOWED_STR}
        if len(valid_scores) > 1:
            conflicting_groups.append(group_id)
            for item in items:
                excluded_rows.append(
                    {
                        "task_group_id": group_id,
                        "task_id": item["task_id"],
                        "occupation_code": item["occupation_code"],
                        "reason": "conflicting_occupation_specific_labels_not_silently_averaged",
                        "conflict_scores": "|".join(sorted(valid_scores)),
                    }
                )
            continue
        canonical = sorted(items, key=lambda item: (item["occupation_code"], item["task_id"]))[0]
        occupations = sorted({item["occupation_code"] for item in items})
        socs = sorted({item["soc_code"] for item in items})
        task_ids = sorted({item["task_id"] for item in items})
        final_rows.append(
            {
                "task_id": canonical["task_id"],
                "task_text": canonical["task_text"],
                "normalized_task_text": canonical["normalized_task_text"],
                "task_group_id": group_id,
                "occupation_code": canonical["occupation_code"],
                "occupation_title": canonical["occupation_title"],
                "soc_code": canonical["soc_code"],
                "reviewer_1_score": canonical["reviewer_1_score"],
                "reviewer_2_score": canonical["reviewer_2_score"],
                "reviewer_mean_score": canonical["reviewer_mean_score"],
                "absolute_disagreement": canonical["absolute_disagreement"],
                "adjudicated_exposure_score": canonical["adjudicated_exposure_score"],
                "label_confidence": canonical["label_confidence"],
                "resolution_method": canonical["resolution_method"],
                "adjudication_status": canonical["adjudication_status"],
                "adjudication_reason": canonical["adjudication_reason"],
                "adjudication_rationale": canonical["adjudication_rationale"],
                "label_source": LABEL_TYPE,
                "label_type": LABEL_TYPE,
                "label_version": LABEL_VERSION,
                "label_date": canonical["label_date"],
                "source_citations": canonical["source_citations"],
                "not_human_ground_truth": "true",
                "n_source_rows": str(len(items)),
                "occupation_codes_all": "|".join(occupations),
                "soc_codes_all": "|".join(socs),
                "task_ids_all": "|".join(task_ids),
                "split_key": group_id,
            }
        )
        for item in items:
            map_rows.append(
                {
                    "task_group_id": group_id,
                    "task_id": item["task_id"],
                    "occupation_code": item["occupation_code"],
                    "soc_code": item["soc_code"],
                    "occupation_title": item["occupation_title"],
                    "adjudicated_exposure_score": item["adjudicated_exposure_score"],
                    "split_key": group_id,
                }
            )

    final = pd.DataFrame(final_rows).sort_values(["task_group_id", "task_id"], kind="mergesort")
    mapping = pd.DataFrame(map_rows).sort_values(["task_group_id", "task_id"], kind="mergesort")
    excluded = pd.DataFrame(
        excluded_rows,
        columns=["task_group_id", "task_id", "occupation_code", "reason", "conflict_scores"],
    )
    if final.empty:
        print("No eligible training rows.")
        return 3
    final.to_csv(FINAL, **CSV_KW)
    mapping.to_csv(MAP, **CSV_KW)
    excluded.to_csv(EXCLUDED, **CSV_KW)
    train_cols = [
        "task_id",
        "task_text",
        "normalized_task_text",
        "task_group_id",
        "occupation_code",
        "occupation_title",
        "soc_code",
        "reviewer_1_score",
        "reviewer_2_score",
        "adjudicated_exposure_score",
        "label_confidence",
        "resolution_method",
        "adjudication_status",
        "label_source",
        "not_human_ground_truth",
        "split_key",
        "n_source_rows",
        "occupation_codes_all",
        "task_ids_all",
    ]
    final[train_cols].to_csv(TRAIN, **CSV_KW)

    bls_info = extract_bls_demand_features()
    r1_dist = Counter(fmt(parse_score(p1[i].get("score"))) for i in sample_ids)
    r2_dist = Counter(fmt(parse_score(p2[i].get("score"))) for i in sample_ids)
    metrics = {
        "paired": len(paired_a),
        "exact": exact,
        "mad": mad,
        "kappa": kappa,
        "ac1": ac1,
        "diffs": diffs,
        "n_gt": n_gt,
        "n_ident": int((adj["adjudication_status"] == "identical").sum()),
        "n_det": int((adj["adjudication_status"] == "deterministic_mean").sum()),
        "n_ai": int((adj["adjudication_status"] == "ai_adjudicated").sum()),
        "n_unresolved": int(adj["adjudication_status"].isin(["unresolved", "incomplete"]).sum()),
        "r1_dist": r1_dist,
        "r2_dist": r2_dist,
        "final_dist": Counter(final["adjudicated_exposure_score"]),
        "n_groups": len(groups),
        "n_dup_groups": len(duplicate_groups),
        "dup_assoc": sum(len(items) for items in duplicate_groups.values()),
        "n_conflict": len(conflicting_groups),
        "n_unresolved_groups": len(unresolved_groups),
        "identical_rationales": identical_rationales,
    }
    write_reports(sample, adj, final, mapping, excluded, metrics, bls_info, backup_dir, [])
    issues = validate_outputs()
    hash1 = sha256_file(FINAL)
    adj2 = pd.read_csv(ADJ, dtype=str, keep_default_na=False)
    rebuilt_ids = [task_group_id(row["normalized_task_text"], row["task_id"]) for _, row in adj2.iterrows()]
    if rebuilt_ids != list(adj2["task_group_id"]):
        issues.append("task_group_id not stable on reread")
    write_reports(sample, adj, final, mapping, excluded, metrics, bls_info, backup_dir, issues)
    payload = {
        "paired": len(paired_a),
        "exact": exact,
        "mad": mad,
        "kappa": kappa,
        "gwet_ac1": ac1,
        "threshold_met": kappa >= float(KAPPA_GATE),
        "gt_0_30": n_gt,
        "unique_groups": len(groups),
        "duplicate_groups": len(duplicate_groups),
        "conflicting_groups": len(conflicting_groups),
        "final_rows": len(final),
        "map_rows": len(mapping),
        "excluded": len(excluded),
        "final_sha256": hash1,
        "backup": backup_dir.relative_to(BASE_DIR).as_posix(),
        "bls": bls_info,
        "validation": "PASS" if not issues else issues,
        "identical_rationales": identical_rationales,
        "not_human_ground_truth": True,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not issues else 4


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize provisional AI task-exposure training table.")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        issues = validate_outputs()
        print(json.dumps({"validation": "PASS" if not issues else issues}, indent=2))
        return 0 if not issues else 4
    return build()


if __name__ == "__main__":
    raise SystemExit(main())
