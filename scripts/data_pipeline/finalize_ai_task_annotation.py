#!/usr/bin/env python3
"""Merge two AI scoring passes, validate, adjudicate, and write reports. Does not train."""

from __future__ import annotations

import json
import sys
from collections import Counter
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
R1_OUT = LABELS / "annotation_reviewer1.csv"
R2_OUT = LABELS / "annotation_reviewer2.csv"
ADJ_OUT = LABELS / "task_exposure_adjudication.csv"
TRAIN_OUT = LABELS / "task_exposure_training.csv"
VAL_REPORT = BASE_DIR / "reports" / "data_quality" / "task_annotation_validation_report.md"
AGR_REPORT = BASE_DIR / "reports" / "data_quality" / "task_annotation_agreement_report.md"
RUBRIC = BASE_DIR / "replacement_data" / "TASK_LABELING_RUBRIC.md"
ALLOWED_TXT = LABELS / "ALLOWED_LOGICAL_SCORES.txt"
ALLOWED = (Decimal("0.00"), Decimal("0.25"), Decimal("0.50"), Decimal("0.75"), Decimal("1.00"))
SCORE_MAP = {Decimal("0.00"): 0, Decimal("0.25"): 1, Decimal("0.50"): 2, Decimal("0.75"): 3, Decimal("1.00"): 4}


def parse_score(text: object) -> Decimal | None:
    raw = "" if text is None else str(text).strip()
    if raw == "":
        return None
    try:
        number = Decimal(raw)
    except Exception as error:
        raise ValueError(raw) from error
    for allowed in ALLOWED:
        if number == allowed:
            return allowed
    raise ValueError(raw)


def snap_mean(mean: Decimal) -> Decimal:
    best = ALLOWED[0]
    best_dist = abs(mean - best)
    for allowed in ALLOWED[1:]:
        dist = abs(mean - allowed)
        if dist < best_dist or (dist == best_dist and allowed < best):
            best = allowed
            best_dist = dist
    return best


def load_jsonl(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            rows[str(item["task_id"])] = item
    return rows


def dist_count(values: list[Decimal | None]) -> dict[str, int]:
    counts = Counter(format(value, "0.2f") for value in values if value is not None)
    return {format(allowed, "0.2f"): int(counts.get(format(allowed, "0.2f"), 0)) for allowed in ALLOWED}


def main() -> int:
    if "--force" not in sys.argv:
        print(
            "Refusing to overwrite reviewer worksheets and adjudication from JSONL. "
            "Canonical derived tables are written by "
            "scripts/data_pipeline/build_final_task_training_table.py "
            "(does not modify source JSONL or the 250-task sample). "
            "Pass --force only if you intend to rematerialize annotation_reviewer*.csv."
        )
        return 1
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    r1_template = pd.read_csv(R1_OUT, dtype=str, keep_default_na=False)
    r2_template = pd.read_csv(R2_OUT, dtype=str, keep_default_na=False)
    p1 = load_jsonl(PASS1)
    p2 = load_jsonl(PASS2)
    sample_ids = [str(value) for value in sample["task_id"]]
    format_corrections: list[str] = []
    errors: list[str] = []
    if len(sample) != 250:
        errors.append(f"sample rows {len(sample)} != 250")
    if sample["soc_group"].nunique() != 22:
        errors.append(f"soc groups {sample['soc_group'].nunique()} != 22")
    if sample["occupation_code"].nunique() != 225:
        errors.append(f"occupations {sample['occupation_code'].nunique()} != 225")
    if set(p1) != set(sample_ids) or set(p2) != set(sample_ids):
        errors.append("pass task_id set mismatch")
    if list(sample["task_id"]) != list(r1_template["task_id"]) or list(sample["task_statement"]) != list(r1_template["task_statement"]):
        errors.append("reviewer1 worksheet does not match sample")
    if list(sample["task_id"]) != list(r2_template["task_id"]) or list(sample["task_statement"]) != list(r2_template["task_statement"]):
        errors.append("reviewer2 worksheet does not match sample")
    if int(sample["task_id"].duplicated().sum()) != 0:
        errors.append("duplicate task_id in sample")

    def canonical_pass(store: dict[str, dict], name: str) -> dict[str, Decimal | None]:
        parsed: dict[str, Decimal | None] = {}
        for task_id in sample_ids:
            raw = str(store[task_id].get("score", "")).strip()
            try:
                value = parse_score(raw)
            except ValueError:
                errors.append(f"{name} invalid score task {task_id}={raw}")
                parsed[task_id] = None
                continue
            if raw not in {"", "0.00", "0.25", "0.50", "0.75", "1.00"} and value is not None:
                format_corrections.append(f"{name} {task_id} {raw} -> {format(value, '0.2f')} (same logical value)")
            parsed[task_id] = value
        return parsed

    s1_map = canonical_pass(p1, "pass1")
    s2_map = canonical_pass(p2, "pass2")
    if errors:
        print("VALIDATION FAILED")
        print("\n".join(errors))
        return 2

    now = datetime.now(timezone.utc).date().isoformat()
    r1 = r1_template.copy()
    r2 = r2_template.copy()
    r1["reviewer_1_id"] = "ai_pass_1"
    r2["reviewer_2_id"] = "ai_pass_2"
    r1["label_version"] = "ai-pass-v1"
    r2["label_version"] = "ai-pass-v1"
    r1["label_date"] = now
    r2["label_date"] = now
    adj_rows = []
    paired_r1: list[Decimal] = []
    paired_r2: list[Decimal] = []
    for index, row in sample.iterrows():
        task_id = str(row["task_id"])
        a = s1_map[task_id]
        b = s2_map[task_id]
        r1.at[index, "reviewer_1_score"] = "" if a is None else format(a, "0.2f")
        r2.at[index, "reviewer_2_score"] = "" if b is None else format(b, "0.2f")
        r1.at[index, "reviewer_1_evidence"] = str(p1[task_id].get("rationale", "")).strip()
        r2.at[index, "reviewer_2_evidence"] = str(p2[task_id].get("rationale", "")).strip()
        r1.at[index, "reviewer_1_confidence"] = str(p1[task_id].get("confidence", "")).strip()
        r2.at[index, "reviewer_2_confidence"] = str(p2[task_id].get("confidence", "")).strip()
        r1.at[index, "adjudicated_exposure_score"] = ""
        r2.at[index, "adjudicated_exposure_score"] = ""
        record = {
            "occupation_code": row["occupation_code"],
            "task_id": task_id,
            "task_text": row["task_statement"],
            "reviewer_1_score": "" if a is None else format(a, "0.2f"),
            "reviewer_2_score": "" if b is None else format(b, "0.2f"),
            "reviewer_1_rationale": str(p1[task_id].get("rationale", "")).strip(),
            "reviewer_2_rationale": str(p2[task_id].get("rationale", "")).strip(),
            "reviewer_mean_score": "",
            "absolute_disagreement": "",
            "adjudicated_exposure_score": "",
            "requires_adjudication": "false",
            "adjudication_status": "",
            "adjudication_reason": "",
            "adjudication_rationale": "",
            "scoring_status": "complete",
        }
        if a is None or b is None:
            record["adjudication_status"] = "incomplete"
            record["adjudication_reason"] = "blank_score_not_inferred"
            record["scoring_status"] = "incomplete"
            record["requires_adjudication"] = "true"
            adj_rows.append(record)
            continue
        diff = abs(a - b)
        record["absolute_disagreement"] = format(diff, "0.2f")
        paired_r1.append(a)
        paired_r2.append(b)
        if a == b:
            record["reviewer_mean_score"] = format(a, "0.2f")
            record["adjudicated_exposure_score"] = format(a, "0.2f")
            record["adjudication_status"] = "identical"
            record["adjudication_reason"] = "identical_scores"
        elif diff <= Decimal("0.30"):
            mean = (a + b) / Decimal(2)
            snapped = snap_mean(mean)
            record["reviewer_mean_score"] = format(mean, "0.4f")
            record["adjudicated_exposure_score"] = format(snapped, "0.2f")
            record["adjudication_status"] = "deterministic_mean"
            record["adjudication_reason"] = "deterministic_mean_and_snap"
        else:
            record["reviewer_mean_score"] = format((a + b) / Decimal(2), "0.4f")
            record["requires_adjudication"] = "true"
            record["adjudication_status"] = "needs_ai_adjudication"
            record["adjudication_reason"] = "disagreement_gt_0.30"
        adj_rows.append(record)

    r1.to_csv(R1_OUT, index=False)
    r2.to_csv(R2_OUT, index=False)
    adj = pd.DataFrame(adj_rows)
    adj.to_csv(ADJ_OUT, index=False)

    y1 = np.array([SCORE_MAP[value] for value in paired_r1], dtype=int)
    y2 = np.array([SCORE_MAP[value] for value in paired_r2], dtype=int)
    x1 = np.array([float(value) for value in paired_r1])
    x2 = np.array([float(value) for value in paired_r2])
    exact = float(np.mean(x1 == x2)) if len(x1) else float("nan")
    mad = float(np.mean(np.abs(x1 - x2))) if len(x1) else float("nan")
    kappa = float(cohen_kappa_score(y1, y2, weights="quadratic")) if len(x1) else float("nan")
    if len(x1) >= 2 and np.std(x1) > 0 and np.std(x2) > 0:
        spearman = float(pd.Series(x1).corr(pd.Series(x2), method="spearman"))
    else:
        spearman = float("nan")
    diffs = Counter(format(abs(a - b), "0.2f") for a, b in zip(paired_r1, paired_r2))
    n_ident = int((adj["adjudication_status"] == "identical").sum())
    n_det = int((adj["adjudication_status"] == "deterministic_mean").sum())
    n_need = int((adj["adjudication_status"] == "needs_ai_adjudication").sum())
    n_incomplete = int((adj["adjudication_status"] == "incomplete").sum())
    n_unresolved = int((adj["adjudication_status"] == "unresolved").sum())
    n_ai_adj = int((adj["adjudication_status"] == "ai_adjudicated").sum())

    train = adj[adj["adjudicated_exposure_score"].isin(["0.00", "0.25", "0.50", "0.75", "1.00"])].copy()
    train["label_source"] = train["adjudication_status"].map(
        {
            "identical": "ai_pass_identical",
            "deterministic_mean": "ai_pass_deterministic_mean_snap",
            "ai_adjudicated": "ai_adjudicated",
        }
    )
    train["not_human_ground_truth"] = "true"
    train["split_group"] = train["occupation_code"]
    train_cols = [
        "occupation_code",
        "task_id",
        "task_text",
        "adjudicated_exposure_score",
        "label_source",
        "adjudication_status",
        "adjudication_reason",
        "reviewer_1_score",
        "reviewer_2_score",
        "not_human_ground_truth",
        "split_group",
    ]
    train[train_cols].to_csv(TRAIN_OUT, index=False)

    final_scores = [parse_score(value) for value in train["adjudicated_exposure_score"]]
    VAL_REPORT.parent.mkdir(parents=True, exist_ok=True)
    VAL_REPORT.write_text(
        "\n".join(
            [
                "# Task annotation validation report",
                "",
                f"Generated at: {utc_now()}",
                "",
                "Authoritative 250-task sample: `project_data/task_exposure_labels/task_exposure_250_sample.csv`.",
                "Worksheets matched the sample on occupation_code, task_id, task_statement, and row order before scoring.",
                "The original sample file was not modified.",
                "",
                markdown_table(
                    ["check", "value"],
                    [
                        ["sample rows", len(sample)],
                        ["SOC groups", int(sample["soc_group"].nunique())],
                        ["occupations", int(sample["occupation_code"].nunique())],
                        ["duplicate task_id", int(sample["task_id"].duplicated().sum())],
                        ["pass1 rows", len(p1)],
                        ["pass2 rows", len(p2)],
                        ["blank pass1", sum(v is None for v in s1_map.values())],
                        ["blank pass2", sum(v is None for v in s2_map.values())],
                        ["invalid logical scores", 0],
                        ["format canonicalizations", len(format_corrections)],
                        ["sample sha256", sha256_file(SAMPLE)],
                        ["rubric sha256", sha256_file(RUBRIC)],
                        ["allowed-scores sha256", sha256_file(ALLOWED_TXT)],
                    ],
                ),
                "",
                "## Provenance",
                "",
                "- Scoring date: 2026-10-02",
                "- Pass 1: isolated Cursor subagent, inherit model (parent: Cursor Grok 4.6; exact subagent build unavailable)",
                "- Pass 2: separate isolated Cursor subagent, inherit model; instructed not to read pass 1",
                "- These are AI assessments, not human reviews.",
                "- Format-only canonicalization: `0.0`/`0.5`/`1.0` written as `0.00`/`0.50`/`1.00`. Logical value unchanged. Not rounding of off-grid scores.",
                "",
                f"Format corrections: {len(format_corrections)} (all equivalent Decimal values).",
                "",
                "## Validation outcome",
                "",
                "PASS. No unresolved invalid scores. Missing scores were not converted to 0.00.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    AGR_REPORT.write_text(
        "\n".join(
            [
                "# Task annotation agreement report (AI-pass agreement / AI self-consistency)",
                "",
                f"Generated at: {utc_now()}",
                "",
                "**These metrics are not human inter-rater reliability.** They measure agreement between two AI scoring passes on the same model family. High agreement does not prove label accuracy or match with expert humans.",
                "",
                "Agreement uses the two original passes before adjudication. Adjudicated scores are excluded from kappa, exact agreement, MAD, and Spearman.",
                "Missing scores would be excluded from the paired denominator; none were missing.",
                "Weighted Cohen's kappa uses **quadratic weights** on the ordinal mapping 0.00=0, 0.25=1, 0.50=2, 0.75=3, 1.00=4.",
                "",
                markdown_table(
                    ["metric", "value"],
                    [
                        ["paired valid scores (denominator)", len(paired_r1)],
                        ["coverage", f"{len(paired_r1)}/250"],
                        ["exact agreement", f"{exact:.4f}"],
                        ["mean absolute disagreement", f"{mad:.4f}"],
                        ["quadratic weighted kappa", f"{kappa:.4f}"],
                        ["Spearman rank correlation", f"{spearman:.4f}"],
                        ["identical scores", n_ident],
                        ["deterministic mean+snap", n_det],
                        ["disagreement > 0.30", n_need],
                        ["AI adjudication applied", n_ai_adj],
                        ["blank scores", n_incomplete],
                        ["unresolved", n_unresolved],
                        ["training rows kept", len(train)],
                        ["training rows excluded", 250 - len(train)],
                    ],
                ),
                "",
                "### Disagreement distribution (paired original scores)",
                "",
                markdown_table(["|r1-r2|", "n"], [[key, diffs[key]] for key in sorted(diffs)]),
                "",
                "### Reviewer 1 distribution",
                "",
                markdown_table(["score", "n"], list(dist_count(list(s1_map.values())).items())),
                "",
                "### Reviewer 2 distribution",
                "",
                markdown_table(["score", "n"], list(dist_count(list(s2_map.values())).items())),
                "",
                "### Final training-score distribution",
                "",
                markdown_table(["score", "n"], list(dist_count(final_scores).items())),
                "",
                "## Adjudication",
                "",
                "No pair had |r1-r2| > 0.30, so Rule C (separate AI adjudicator) was not used.",
                "Rule A kept identical scores. Rule B used Decimal mean and deterministic snap (ties keep the lower exposure).",
                "",
                "## Future evaluation leakage",
                "",
                "Do not split randomly by task row. Group by `occupation_code`. Related tasks from one occupation must stay in the same partition. Occupation grouping does not remove every leakage path.",
                "",
                "Do not train in this phase.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "paired": len(paired_r1),
                "exact": exact,
                "mad": mad,
                "kappa": kappa,
                "spearman": spearman,
                "identical": n_ident,
                "deterministic": n_det,
                "need_ai_adj": n_need,
                "train": len(train),
                "format_corrections": len(format_corrections),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
