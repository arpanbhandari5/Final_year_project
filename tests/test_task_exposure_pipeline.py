import sys
from decimal import Decimal
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "data_pipeline"))

from build_final_task_training_table import (  # noqa: E402
    gwet_ac1_nominal,
    normalize_task_text,
    operational_label_confidence,
    parse_score,
    snap_mean,
    task_group_id,
)


def test_blank_is_not_zero():
    assert parse_score("") is None
    assert parse_score("0.00") == Decimal("0.00")


def test_parse_rejects_off_grid():
    try:
        parse_score("0.3")
    except ValueError:
        return
    raise AssertionError("off-grid score must raise")


def test_snap_ties_take_lower_exposure():
    assert snap_mean(Decimal("0.125")) == Decimal("0.00")
    assert snap_mean(Decimal("0.375")) == Decimal("0.25")
    assert snap_mean(Decimal("0.625")) == Decimal("0.50")


def test_normalize_order_and_trailing_punct_only():
    assert normalize_task_text("  Advise Students,  on career issues.  ") == (
        "advise students, on career issues"
    )
    assert normalize_task_text("Keep internal commas, please!") == "keep internal commas, please"


def test_empty_text_not_shared_group():
    assert task_group_id("", "5914") == "tg_empty_5914"
    assert task_group_id("", "6214") == "tg_empty_6214"
    assert task_group_id("", "5914") != task_group_id("", "6214")
    same = "act as advisers to student organizations"
    assert task_group_id(same, "a") == task_group_id(same, "b")


def test_confidence_scheme():
    assert operational_label_confidence("identical", Decimal("0.00")) == "1.00"
    assert operational_label_confidence("deterministic_mean", Decimal("0.25")) == "0.85"
    assert operational_label_confidence("deterministic_mean", Decimal("0.30")) == "0.70"
    assert operational_label_confidence("ai_adjudicated", Decimal("0.50")) == "0.60"
    assert operational_label_confidence("unresolved", Decimal("0.50")) == ""


def test_gwet_perfect_agreement():
    y = np.array([0, 1, 2, 3, 4, 0, 1, 2])
    assert abs(gwet_ac1_nominal(y, y, 5) - 1.0) < 1e-12
