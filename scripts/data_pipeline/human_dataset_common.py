"""Shared constants for the human task-exposure track. Does not invent labels."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline_common import BASE_DIR

RUBRIC_VERSION = "human-task-exposure-v2.0"
ONET_VERSION = "31.0"
ONET_SOURCE_URL = "https://www.onetcenter.org/database.html"
BLS_SOURCE = "BLS Employment Projections Occupation.xlsx Table 1.2, 2025-2035"
ALLOWED_SCORES = (0.00, 0.25, 0.50, 0.75, 1.00)
ALLOWED_CONFIDENCE = ("high", "medium", "low")
REVIEWER_SLOT_IDS = {
    "1": "HUMAN_REVIEWER_A",
    "2": "HUMAN_REVIEWER_B",
    "3": "HUMAN_REVIEWER_C",
}
FORBIDDEN_REVIEWER_IDS = frozenset({"AI_1", "unknown", "reviewer", "test"})
SCORE_STATUS_BLANK = "blank"
SCORE_STATUS_VALID = "valid_score"
SCORE_STATUS_INVALID = "invalid_score"
SCORE_STATUS_UNRESOLVED = "unresolved"
SCORE_STATUS_NOT_SCORABLE = "not_scorable"
WORKSHEET_IDENTITY_FIELDS = (
    "task_id",
    "occupation_code",
    "occupation_title",
    "soc_code",
    "soc_major_group",
    "task_text",
    "split",
    "reviewer_slot",
)
TASK_POOL = BASE_DIR / "project_data" / "task_exposure_labels" / "onet_task_annotations_round_1.csv"
OCC_MASTER = BASE_DIR / "external_data" / "normalized" / "onet_31_0" / "occupation_master.csv"
BLS_FEATURES = (
    BASE_DIR
    / "external_data"
    / "normalized"
    / "bls_employment_projections"
    / "bls_occupation_demand_features_2025_2035.csv"
)
LABELS = BASE_DIR / "project_data" / "task_exposure_labels"
OCC_SEL = BASE_DIR / "project_data" / "occupation_selection"
REPORTS = BASE_DIR / "reports" / "data_quality"

SCORE_BLANK_FIELDS = [
    "reviewer_1_score",
    "reviewer_2_score",
    "third_reviewer_score",
    "adjudicated_exposure_score",
    "reviewer_1_confidence",
    "reviewer_2_confidence",
    "reviewer_evidence",
    "reviewer_notes",
    "adjudication_reason",
    "agreement_status",
]

ROUND1_SAMPLE = LABELS / "task_exposure_human_round1_sample.csv"
ROUND1_REVIEWER1 = LABELS / "task_exposure_human_round1_reviewer1.csv"
ROUND1_REVIEWER2 = LABELS / "task_exposure_human_round1_reviewer2.csv"
ROUND1_THIRD = LABELS / "task_exposure_human_round1_third_reviewer.csv"
ROUND1_IDENTITY_LOCK = LABELS / "task_exposure_human_round1_identity_lock.json"
WORKSHEET_COLUMN_ORDER = [
    "reviewer_id",
    "reviewer_role",
    "relevant_experience",
    "rubric_version",
    "review_date",
    "task_id",
    "occupation_code",
    "occupation_title",
    "soc_code",
    "soc_major_group",
    "task_text",
    "reviewer_score",
    "reviewer_confidence",
    "reviewer_evidence",
    "reviewer_notes",
    "split",
    "reviewer_slot",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def soc_prefix7(occupation_code: str) -> str:
    text = str(occupation_code).strip()
    return text[:7]


def load_task_pool() -> pd.DataFrame:
    frame = pd.read_csv(TASK_POOL, dtype=str, keep_default_na=False)
    required = ["occupation_code", "occupation_title", "task_id", "task_statement"]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"task pool missing {missing}")
    frame["task_text"] = frame["task_statement"].astype(str)
    frame["soc_major_group"] = frame["occupation_code"].astype(str).str[:2]
    frame["soc_code"] = frame["occupation_code"].map(soc_prefix7)
    blank_text = frame["task_text"].str.strip() == ""
    blank_id = frame["task_id"].str.strip() == ""
    blank_occ = frame["occupation_code"].str.strip() == ""
    frame = frame.loc[~blank_text & ~blank_id & ~blank_occ].copy()
    return frame


def pick_diverse_tasks(group: pd.DataFrame, k: int, rng: np.random.Generator) -> pd.DataFrame:
    g = group.drop_duplicates(subset=["task_id"]).copy()
    if len(g) <= k:
        return g
    if "task_type" in g.columns:
        core = g[g["task_type"].astype(str).str.lower() == "core"]
        other = g[g["task_type"].astype(str).str.lower() != "core"]
        n_core = min(len(core), max(1, k // 2 + k % 2))
        n_other = min(len(other), k - n_core)
        if n_core + n_other < k:
            n_core = min(len(core), k - n_other)
        parts = []
        if n_core:
            parts.append(core.sample(n=n_core, random_state=int(rng.integers(0, 10_000_000))))
        if n_other:
            parts.append(other.sample(n=n_other, random_state=int(rng.integers(0, 10_000_000))))
        picked = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["task_id"])
        if len(picked) < k:
            rest = g[~g["task_id"].isin(picked["task_id"])]
            need = k - len(picked)
            if need > 0 and len(rest):
                picked = pd.concat(
                    [
                        picked,
                        rest.sample(n=min(need, len(rest)), random_state=int(rng.integers(0, 10_000_000))),
                    ],
                    ignore_index=True,
                )
        return picked.head(k)
    return g.sample(n=k, random_state=int(rng.integers(0, 10_000_000)))


def occupation_grouped_splits(occupations: list[str], *, seed: int, train_frac=0.70, val_frac=0.15):
    occ = sorted(set(occupations))
    rng = np.random.default_rng(seed)
    order = rng.permutation(occ)
    n = len(order)
    n_train = int(round(n * train_frac))
    n_val = int(round(n * val_frac))
    if n_train + n_val >= n:
        n_val = max(1, n - n_train - 1) if n >= 3 else 0
        n_train = n - n_val - 1 if n >= 3 else n
    n_test = n - n_train - n_val
    train = list(order[:n_train])
    val = list(order[n_train : n_train + n_val])
    test = list(order[n_train + n_val :])
    mapping = {}
    for code in train:
        mapping[code] = "train"
    for code in val:
        mapping[code] = "validation"
    for code in test:
        mapping[code] = "test"
    overlap = set(train) & set(val) | set(train) & set(test) | set(val) & set(test)
    if overlap:
        raise RuntimeError(f"occupation split overlap: {overlap}")
    return mapping, {"train": n_train, "validation": n_val, "test": n_test}


def blank_human_score_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for field in SCORE_BLANK_FIELDS:
        out[field] = ""
    out["label_source"] = ""
    out["label_status"] = "unscored_human_template"
    out["rubric_version"] = RUBRIC_VERSION
    out["not_human_ground_truth"] = "true"
    out["onet_version"] = ONET_VERSION
    out["task_source"] = "O*NET 31.0 Task Statements"
    out["bls_source"] = BLS_SOURCE
    return out


def is_blank_cell(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "<na>"}


def parse_allowed_score(value: object) -> float | None:
    if is_blank_cell(value):
        return None
    number = float(str(value).strip())
    if number not in ALLOWED_SCORES:
        raise ValueError(f"score {number} is not allowed {ALLOWED_SCORES}")
    return number


def classify_score_cell(value: object, notes: object = "") -> str:
    notes_text = "" if notes is None else str(notes).strip().lower()
    if "not_scorable" in notes_text.replace(" ", "_"):
        if is_blank_cell(value):
            return SCORE_STATUS_NOT_SCORABLE
    if "unresolved" in notes_text:
        if is_blank_cell(value):
            return SCORE_STATUS_UNRESOLVED
    if is_blank_cell(value):
        return SCORE_STATUS_BLANK
    try:
        parse_allowed_score(value)
    except ValueError:
        return SCORE_STATUS_INVALID
    return SCORE_STATUS_VALID


def confidence_is_allowed(value: object) -> bool:
    if is_blank_cell(value):
        return True
    return str(value).strip() == str(value).strip().lower() and str(value).strip() in ALLOWED_CONFIDENCE


def identity_tuple(row: pd.Series) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")).replace("\r\n", "\n") for field in WORKSHEET_IDENTITY_FIELDS)


def identity_fingerprint(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    for _, row in frame.iterrows():
        digest.update(("\x1f".join(identity_tuple(row)) + "\n").encode("utf-8"))
    return digest.hexdigest()


def count_filled_scores(series: pd.Series) -> int:
    return int((~series.map(is_blank_cell)).sum())
