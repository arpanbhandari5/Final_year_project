#!/usr/bin/env python3
"""Refuse experimental model training until a human-reviewed trainable table exists."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_dataset_common import LABELS

TRAINABLE = LABELS / "task_exposure_human_round1_trainable.csv"
MESSAGE = """Human-label evaluation gate: no numeric adjudicated human scores are available.

Do not train on the 248-row provisional AI table as human ground truth.
Do not run train_model.py or replace production pickles.
When human trainable rows exist, compare mean/median baselines, TF-IDF Ridge,
and at least ElasticNet or linear SVR on occupation-grouped folds, then report
held-out human test metrics separately from AI weak-supervision metrics.
"""


def main() -> int:
    if not TRAINABLE.exists():
        print(MESSAGE)
        return 2
    df = pd.read_csv(TRAINABLE, dtype=str, keep_default_na=False)
    scored = df.get("adjudicated_exposure_score", pd.Series(dtype=str)).astype(str).str.strip()
    n = int((scored != "").sum())
    if n == 0:
        print(MESSAGE)
        return 2
    print(
        f"Found {n} adjudicated human rows in {TRAINABLE.name}. "
        "Training is still a separate approved experimental step; this script does not fit models."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
