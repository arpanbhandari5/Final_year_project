#!/usr/bin/env python3
"""Assign reviewer IDs and freeze identity metadata. Does not fill scores."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_dataset_common import (
    ROUND1_IDENTITY_LOCK,
    ROUND1_REVIEWER1,
    ROUND1_REVIEWER2,
    ROUND1_SAMPLE,
    ROUND1_THIRD,
    REVIEWER_SLOT_IDS,
    WORKSHEET_COLUMN_ORDER,
    count_filled_scores,
    identity_fingerprint,
    soc_prefix7,
)

INDEPENDENT_ROLE = "independent_reviewer"


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def prepare_worksheet(path: Path, slot: str) -> pd.DataFrame:
    frame = load_csv(path)
    n_scores = count_filled_scores(frame["reviewer_score"])
    if n_scores != 0:
        raise RuntimeError(f"{path.name} already has {n_scores} reviewer scores; abort")
    if "reviewer_confidence" in frame.columns and count_filled_scores(frame["reviewer_confidence"]) != 0:
        raise RuntimeError(f"{path.name} already has confidence values; abort")
    frame["reviewer_id"] = REVIEWER_SLOT_IDS[slot]
    frame["reviewer_role"] = INDEPENDENT_ROLE
    if "soc_code" not in frame.columns:
        frame.insert(
            list(frame.columns).index("occupation_title") + 1,
            "soc_code",
            frame["occupation_code"].map(soc_prefix7),
        )
    else:
        frame["soc_code"] = frame["occupation_code"].map(soc_prefix7)
    ordered = [col for col in WORKSHEET_COLUMN_ORDER if col in frame.columns]
    extra = [col for col in frame.columns if col not in ordered]
    return frame[ordered + extra]


def lock_payload(sample: pd.DataFrame, sheets: dict[str, pd.DataFrame]) -> dict:
    payload = {
        "stable_row_identifier": "task_id",
        "identity_fields": [
            "task_id",
            "occupation_code",
            "occupation_title",
            "soc_code",
            "soc_major_group",
            "task_text",
            "split",
            "reviewer_slot",
        ],
        "note": "Returned worksheets must keep this row order and these identity fields unchanged.",
        "sample_task_id_order": sample["task_id"].astype(str).tolist(),
        "sample_identity_sha256": identity_fingerprint(sample),
    }
    for name, frame in sheets.items():
        payload[f"{name}_task_id_order"] = frame["task_id"].astype(str).tolist()
        payload[f"{name}_identity_sha256"] = identity_fingerprint(frame)
        payload[f"{name}_row_count"] = int(len(frame))
    return payload


def main() -> int:
    r1 = prepare_worksheet(ROUND1_REVIEWER1, "1")
    r2 = prepare_worksheet(ROUND1_REVIEWER2, "2")
    r3 = prepare_worksheet(ROUND1_THIRD, "3")
    sample = load_csv(ROUND1_SAMPLE)
    if count_filled_scores(sample.get("reviewer_1_score", pd.Series(dtype=str))) != 0:
        raise RuntimeError("sample reviewer_1_score is not blank")
    if count_filled_scores(sample.get("reviewer_2_score", pd.Series(dtype=str))) != 0:
        raise RuntimeError("sample reviewer_2_score is not blank")
    if count_filled_scores(sample.get("adjudicated_exposure_score", pd.Series(dtype=str))) != 0:
        raise RuntimeError("sample adjudicated_exposure_score is not blank")
    if "third_reviewer_score" not in sample.columns:
        insert_at = list(sample.columns).index("reviewer_2_score") + 1
        sample.insert(insert_at, "third_reviewer_score", "")
    else:
        if count_filled_scores(sample["third_reviewer_score"]) != 0:
            raise RuntimeError("sample third_reviewer_score is not blank")
        sample["third_reviewer_score"] = sample["third_reviewer_score"]

    r1.to_csv(ROUND1_REVIEWER1, index=False)
    r2.to_csv(ROUND1_REVIEWER2, index=False)
    r3.to_csv(ROUND1_THIRD, index=False)
    sample.to_csv(ROUND1_SAMPLE, index=False)

    lock = lock_payload(sample, {"reviewer1": r1, "reviewer2": r2, "third_reviewer": r3})
    ROUND1_IDENTITY_LOCK.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewer_ids": [REVIEWER_SLOT_IDS["1"], REVIEWER_SLOT_IDS["2"], REVIEWER_SLOT_IDS["3"]],
                "filled_reviewer_scores": 0,
                "filled_adjudicated_scores": 0,
                "identity_lock": ROUND1_IDENTITY_LOCK.name,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
