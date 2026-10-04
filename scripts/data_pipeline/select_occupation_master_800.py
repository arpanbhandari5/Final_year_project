#!/usr/bin/env python3
"""Select up to 800 O*NET occupations using BLS commonness + SOC diversity.

BLS employment/openings/projections are selection context only, not exposure labels.
Exact SOC prefix join; no fuzzy mapping. Does not invent occupations or task scores.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import utc_now
from human_dataset_common import (
    BLS_FEATURES,
    BLS_SOURCE,
    OCC_MASTER,
    OCC_SEL,
    ONET_SOURCE_URL,
    ONET_VERSION,
    REPORTS,
    load_task_pool,
    sha256_file,
    soc_prefix7,
)

TARGET_N = 800
SEED = 20261003
MIN_TASKS = 3
OUT = OCC_SEL / "occupation_master_800.csv"
REPORT = REPORTS / "occupation_master_800_selection_report.md"
STATS = OCC_SEL / "occupation_master_800_stats.json"


def percentile_rank(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(method="average", pct=True)


def main() -> int:
    tasks = load_task_pool()
    task_counts = tasks.groupby("occupation_code").size().rename("onet_task_count")
    master = pd.read_csv(OCC_MASTER, dtype=str, keep_default_na=False)
    master = master.merge(task_counts, left_on="occupation_code", right_index=True, how="left")
    master["onet_task_count"] = pd.to_numeric(master["onet_task_count"], errors="coerce").fillna(0).astype(int)
    master["soc_code"] = master["occupation_code"].map(soc_prefix7)
    master["soc_major_group"] = master["occupation_code"].astype(str).str[:2]
    eligible = master[
        (master["occupation_code"].str.strip() != "")
        & (master["occupation_title"].str.strip() != "")
        & (master["onet_task_count"] >= MIN_TASKS)
    ].copy()

    bls = pd.read_csv(BLS_FEATURES, dtype=str, keep_default_na=False)
    line = bls[bls["occupation_type"].astype(str).str.strip() == "Line item"].copy()
    line = line.drop_duplicates(subset=["bls_matrix_code"], keep="first")
    eligible = eligible.merge(
        line,
        left_on="soc_code",
        right_on="bls_matrix_code",
        how="left",
        suffixes=("", "_bls"),
    )
    eligible["bls_mapping_status"] = np.where(
        eligible["bls_matrix_code"].astype(str).str.strip() != "",
        "exact_soc7_line_item",
        "unmapped_excluded_from_commonness_rank",
    )
    mapped = eligible[eligible["bls_mapping_status"] == "exact_soc7_line_item"].copy()
    mapped["employment_rank"] = percentile_rank(mapped["employment_2025_thousands"])
    mapped["openings_rank"] = percentile_rank(mapped["occupational_openings_annual_average_2025_2035"])
    mapped["projected_employment_rank"] = percentile_rank(mapped["employment_2035_thousands"])
    mapped["commonness_score"] = (
        0.45 * mapped["employment_rank"].fillna(0)
        + 0.35 * mapped["openings_rank"].fillna(0)
        + 0.20 * mapped["projected_employment_rank"].fillna(0)
    )

    n_emp = int(round(TARGET_N * 0.70))
    n_div = int(round(TARGET_N * 0.20))
    n_str = TARGET_N - n_emp - n_div

    selected = []
    reasons = {}
    emp_sorted = mapped.sort_values(["commonness_score", "occupation_code"], ascending=[False, True])
    # cap per SOC group in employment tranche to reduce monopoly
    soc_cap = max(8, int(np.ceil(n_emp / max(1, emp_sorted["soc_major_group"].nunique()))))
    soc_counts: dict[str, int] = {}
    for _, row in emp_sorted.iterrows():
        if len(selected) >= n_emp:
            break
        soc = str(row["soc_major_group"])
        if soc_counts.get(soc, 0) >= soc_cap:
            continue
        selected.append(str(row["occupation_code"]))
        reasons[str(row["occupation_code"])] = "employment_openings_70pct"
        soc_counts[soc] = soc_counts.get(soc, 0) + 1

    remaining = mapped[~mapped["occupation_code"].isin(selected)].copy()
    # diversity: underrepresented SOC groups
    all_soc = sorted(eligible["soc_major_group"].unique())
    current = pd.Series(soc_counts).reindex(all_soc, fill_value=0)
    target_per = max(2, int(np.floor(TARGET_N / max(1, len(all_soc)))))
    for soc in current.sort_values().index:
        if len([c for c in selected]) >= n_emp + n_div:
            break
        need = max(0, target_per - int(current.get(soc, 0)))
        pool = remaining[remaining["soc_major_group"] == soc].sort_values(
            "commonness_score", ascending=False
        )
        for _, row in pool.iterrows():
            if need <= 0:
                break
            code = str(row["occupation_code"])
            if code in reasons:
                continue
            selected.append(code)
            reasons[code] = "soc_diversity_20pct"
            soc_counts[soc] = soc_counts.get(soc, 0) + 1
            current[soc] = current.get(soc, 0) + 1
            need -= 1
            remaining = remaining[remaining["occupation_code"] != code]

    # strategic: high task coverage + still-missing SOC, then unmapped only if needed
    still = TARGET_N - len(selected)
    strat_pool = mapped[~mapped["occupation_code"].isin(selected)].sort_values(
        ["onet_task_count", "commonness_score"], ascending=[False, False]
    )
    for _, row in strat_pool.iterrows():
        if len(selected) >= TARGET_N:
            break
        code = str(row["occupation_code"])
        selected.append(code)
        reasons[code] = "strategic_coverage_10pct"
    if len(selected) < TARGET_N:
        unmapped = eligible[eligible["bls_mapping_status"] != "exact_soc7_line_item"]
        unmapped = unmapped[~unmapped["occupation_code"].isin(selected)].sort_values(
            "onet_task_count", ascending=False
        )
        for _, row in unmapped.iterrows():
            if len(selected) >= TARGET_N:
                break
            code = str(row["occupation_code"])
            selected.append(code)
            reasons[code] = "strategic_unmapped_not_in_commonness_rank"

    selected = selected[:TARGET_N]
    out = eligible[eligible["occupation_code"].isin(selected)].copy()
    out["selection_stratum"] = out["occupation_code"].map(reasons)
    out["selection_rationale"] = out["selection_stratum"]
    out["onet_version"] = ONET_VERSION
    out["onet_source_url"] = ONET_SOURCE_URL
    out["bls_source"] = BLS_SOURCE
    out["not_automation_exposure_target"] = "true"
    mapped_scores = mapped.set_index("occupation_code")["commonness_score"]
    out["commonness_score"] = out["occupation_code"].map(mapped_scores)
    keep = [
        "occupation_code",
        "occupation_title",
        "soc_code",
        "soc_major_group",
        "onet_task_count",
        "bls_matrix_code",
        "employment_2025_thousands",
        "employment_2035_thousands",
        "occupational_openings_annual_average_2025_2035",
        "commonness_score",
        "selection_stratum",
        "selection_rationale",
        "bls_mapping_status",
        "onet_version",
        "onet_source_url",
        "bls_source",
        "not_automation_exposure_target",
    ]
    for col in keep:
        if col not in out.columns:
            out[col] = ""
    out = out[keep].drop_duplicates(subset=["occupation_code"]).sort_values("occupation_code")

    OCC_SEL.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    n = int(len(out))
    unique = int(out["occupation_code"].nunique())
    stats = {
        "generated_at": utc_now(),
        "target_n": TARGET_N,
        "written_n": n,
        "unique_occupation_code": unique,
        "eligible_with_ge3_tasks": int(len(eligible)),
        "exact_bls_mapped_eligible": int(len(mapped)),
        "unmapped_eligible": int((eligible["bls_mapping_status"] != "exact_soc7_line_item").sum()),
        "stratum_counts": out["selection_stratum"].value_counts().to_dict(),
        "soc_major_groups": int(out["soc_major_group"].nunique()),
        "min_onet_task_count": int(out["onet_task_count"].min()) if n else 0,
        "sha256": sha256_file(OUT) if OUT.exists() else "",
        "gate_exactly_800": n == TARGET_N and unique == TARGET_N,
        "commonness_is_not_exposure_label": True,
    }
    STATS.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "\n".join(
            [
                "# Occupation master 800 selection",
                "",
                "BLS employment, projected employment, and annual openings were used only to rank **commonness** for sampling. They are not task-exposure labels.",
                "Join: O*NET `occupation_code` first 7 characters == BLS `bls_matrix_code` for Line item rows. No fuzzy match.",
                "",
                f"- eligible occupations with ≥{MIN_TASKS} O*NET tasks: {stats['eligible_with_ge3_tasks']}",
                f"- exact BLS-mapped eligible: {stats['exact_bls_mapped_eligible']}",
                f"- written rows: {n} (unique codes {unique}); target {TARGET_N}; gate_exactly_800={stats['gate_exactly_800']}",
                f"- SOC major groups represented: {stats['soc_major_groups']}",
                f"- stratum counts: {stats['stratum_counts']}",
                f"- SHA-256: `{stats['sha256']}`",
                "",
                "If `gate_exactly_800` is false, do not invent occupations to pad the list.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({k: stats[k] for k in ("written_n", "unique_occupation_code", "gate_exactly_800", "exact_bls_mapped_eligible")}, indent=2))
    if n != TARGET_N or unique != TARGET_N:
        print("WARNING: did not write exactly 800 unique occupations.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
