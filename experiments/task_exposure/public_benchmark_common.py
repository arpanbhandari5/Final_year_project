"""Shared helpers for the isolated GPTs-are-GPTs public-benchmark experiment.

This module does not import production trainers, the 248-row evaluator, or
Prayash human-review worksheets.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "experiments" / "task_exposure" / "data" / "public_benchmark"
RAW_DIR = DATA_DIR / "raw"
REPORT_DIR = REPO_ROOT / "experiments" / "task_exposure" / "reports" / "public_benchmark"
ONET_TASKS = REPO_ROOT / "project_data" / "task_exposure_labels" / "onet_task_annotations_round_1.csv"
ONET_OCC_MASTER = REPO_ROOT / "external_data" / "normalized" / "onet_31_0" / "occupation_master.csv"
OCC_MASTER_800 = REPO_ROOT / "project_data" / "occupation_selection" / "occupation_master_800.csv"
ROUND1_R1 = REPO_ROOT / "project_data" / "task_exposure_labels" / "task_exposure_human_round1_reviewer1.csv"
ROUND1_R2 = REPO_ROOT / "project_data" / "task_exposure_labels" / "task_exposure_human_round1_reviewer2.csv"
ROUND1_R3 = REPO_ROOT / "project_data" / "task_exposure_labels" / "task_exposure_human_round1_third_reviewer.csv"

SOURCE_REPO = "openai/GPTs-are-GPTs"
SOURCE_COMMIT = "0471612fef3cc22b74fb884d27bff9dbd3770582"
SOURCE_LICENSE = "MIT"
SOURCE_URL = f"https://github.com/{SOURCE_REPO}"
SOURCE_FILE_URL = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT}/data/full_labelset.tsv"
PAPER_ONET_VERSION = "27.2"
PROJECT_ONET_VERSION = "31.0"
ALLOWED_HUMAN_LABELS = ("E0", "E1", "E2")
GPT_FIELDS = ("gpt4_exposure", "gpt4_exposure_alt_rubric", "gpt4_automation")
TARGET_FIELD = "human_labels"
TEXT_COLUMN = "task_text"
SPLIT_SEED = 202610031
N_SPLITS = 5
C_CANDIDATES = [0.1, 1.0, 10.0]
TFIDF_CONFIGURATION = {
    "ngram_range": (1, 2),
    "min_df": 1,
    "sublinear_tf": True,
    "max_features": 12000,
    "stop_words": "english",
}
HUMAN_TRACK_STATUS = "deferred_due_to_unavailable_independent_reviewers"
AI_TRACK_STATUS = "baseline_provisional_ai_weak_supervision"
CLAIM_BOUNDARY = (
    "This experiment evaluates task-level classification against a published "
    "GPTs-are-GPTs exposure taxonomy using human-derived benchmark labels. "
    "The benchmark provides an external reference and does not constitute new "
    "human validation of Prayash's original 0-1 scoring rubric."
)

RAW_LABELSET = RAW_DIR / "full_labelset.tsv"
DERIVED_CSV = DATA_DIR / "public_gpts_are_gpts_benchmark.csv"
SPLIT_MANIFEST = REPORT_DIR / "split_manifest.json"


class PublicBenchmarkError(ValueError):
    """Raised when the public benchmark cannot be used as specified."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not np.isfinite(number):
            return None
        return number
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, np.ndarray):
        return [json_ready(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_ready(payload), indent=2) + "\n", encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def normalize_task_text(value: object) -> str:
    text = "" if value is None else str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s,]", "", text)
    return text.strip()


def normalize_task_id(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if text == "" or text.lower() in {"nan", "none"}:
        return ""
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return text


def package_versions() -> dict[str, str]:
    import sklearn

    return {
        "python": sys.version.replace("\n", " "),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scikit-learn": sklearn.__version__,
    }


def load_raw_labelset(path: Path = RAW_LABELSET) -> pd.DataFrame:
    if not path.exists():
        raise PublicBenchmarkError(f"missing source file {path}")
    frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    required = [
        "O*NET-SOC Code",
        "Task ID",
        "Task",
        "human_labels",
        "human_exposure_agg",
        "gpt4_exposure",
        "gpt4_exposure_alt_rubric",
        "gpt4_automation",
    ]
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise PublicBenchmarkError(f"source schema missing {missing}; columns={list(frame.columns)}")
    return frame


def standardize_source(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "occupation_code": frame["O*NET-SOC Code"].astype(str).str.strip(),
            "occupation_title": frame.get("Title", pd.Series([""] * len(frame))).astype(str),
            "task_id": frame["Task ID"].map(normalize_task_id),
            "task_text": frame["Task"].astype(str),
            "task_type": frame.get("Task Type", pd.Series([""] * len(frame))).astype(str),
            "human_labels": frame["human_labels"].astype(str).str.strip(),
            "human_exposure_agg": frame["human_exposure_agg"].astype(str).str.strip(),
            "gpt4_exposure": frame["gpt4_exposure"].astype(str).str.strip(),
            "gpt4_exposure_alt_rubric": frame["gpt4_exposure_alt_rubric"].astype(str).str.strip(),
            "gpt4_automation": frame["gpt4_automation"].astype(str).str.strip(),
        }
    )
    if "alpha" in frame.columns:
        out["source_alpha"] = frame["alpha"].astype(str)
    if "beta" in frame.columns:
        out["source_beta"] = frame["beta"].astype(str)
    if "gamma" in frame.columns:
        out["source_gamma"] = frame["gamma"].astype(str)
    out["soc_major_group"] = out["occupation_code"].str[:2]
    out["normalized_task_text"] = out["task_text"].map(normalize_task_text)
    out["label_source"] = "gpts_are_gpts_public_benchmark"
    out["label_status"] = "human_derived_benchmark_not_prayash_review"
    out["not_prayash_human_review"] = "true"
    out["not_personal_job_loss"] = "true"
    out["source_repository"] = SOURCE_REPO
    out["source_commit"] = SOURCE_COMMIT
    out["source_onet_version_documented"] = PAPER_ONET_VERSION
    out["project_onet_version"] = PROJECT_ONET_VERSION
    return out


def validate_human_labels(frame: pd.DataFrame) -> dict[str, Any]:
    labels = frame[TARGET_FIELD].astype(str).str.strip()
    blank = int((labels == "").sum())
    observed = sorted({value for value in labels.unique() if value != ""})
    unexpected = [value for value in observed if value not in ALLOWED_HUMAN_LABELS]
    if unexpected:
        raise PublicBenchmarkError(
            f"unexpected human_labels values {unexpected}; refusing to recode or drop them"
        )
    e3 = int((labels == "E3").sum())
    return {
        "rows": int(len(frame)),
        "non_empty_human_labels": int(len(frame) - blank),
        "missing_human_labels": blank,
        "observed_labels": observed,
        "e3_in_human_labels": e3,
        "invalid_labels": unexpected,
        "class_counts": labels.value_counts().sort_index().to_dict(),
    }


def occupation_grouped_splits(
    occupations: list[str],
    *,
    seed: int = SPLIT_SEED,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> tuple[dict[str, str], dict[str, int]]:
    occ = sorted(set(occupations))
    rng = np.random.default_rng(seed)
    order = rng.permutation(occ)
    n = len(order)
    n_train = int(round(n * train_frac))
    n_val = int(round(n * val_frac))
    if n_train + n_val >= n:
        n_val = max(1, n - n_train - 1) if n >= 3 else 0
        n_train = n - n_val - 1 if n >= 3 else n
    train = list(order[:n_train])
    val = list(order[n_train : n_train + n_val])
    test = list(order[n_train + n_val :])
    mapping = {code: "train" for code in train}
    mapping.update({code: "validation" for code in val})
    mapping.update({code: "test" for code in test})
    overlap = {
        "train_validation": sorted(set(train) & set(val)),
        "train_test": sorted(set(train) & set(test)),
        "validation_test": sorted(set(val) & set(test)),
    }
    if any(overlap.values()):
        raise PublicBenchmarkError(f"occupation split overlap: {overlap}")
    return mapping, {
        "train": len(train),
        "validation": len(val),
        "test": len(test),
        "overlap": overlap,
    }


def verify_group_disjoint(train_groups: np.ndarray, other_groups: np.ndarray) -> None:
    overlap = set(train_groups) & set(other_groups)
    if overlap:
        raise PublicBenchmarkError(f"occupation leakage: {sorted(overlap)[:20]}")


def text_features_exclude_targets(columns: list[str]) -> None:
    forbidden = {
        TARGET_FIELD,
        "human_exposure_agg",
        *GPT_FIELDS,
        "source_alpha",
        "source_beta",
        "source_gamma",
        "split",
        "occupation_exposure_summary",
    }
    leaked = [col for col in columns if col in forbidden]
    if leaked:
        raise PublicBenchmarkError(f"refusing target-derived features {leaked}")
