"""Candidate occupations must not reach production benchmark lookup."""

from __future__ import annotations

import pytest

from task_exposure_assessor import (
    CANDIDATE_LOOKUP_REFUSAL,
    ConfirmedOccupation,
    OccupationCandidate,
    as_confirmed_occupation,
    confirm_occupation,
    lookup_verified_task_exposure,
    resolve_occupation,
)


def test_cluster_soc_is_candidate_not_verified() -> None:
    match = resolve_occupation(
        clusters=[{"soc_code": "53-7121.00", "similarity": 0.18}],
        top_roles=[{"job_role": "Chief Executives", "similarity": 0.9}],
    )
    assert match["status"] == "candidate"
    assert match["candidate_code"] == "53-7121.00"
    assert match["code"] is None
    assert match["verified_occupation_code"] is None
    assert match["score_interpretation"] == "uncalibrated candidate score"
    exposure = lookup_verified_task_exposure(match)
    assert exposure["status"] != "verified"
    assert exposure["distribution"] is None
    assert exposure["reason"] == CANDIDATE_LOOKUP_REFUSAL


def test_occupation_candidate_object_cannot_authorize_lookup() -> None:
    candidate = OccupationCandidate(
        candidate_code="53-7121.00",
        candidate_title="Tank Car, Truck, and Ship Loaders",
        matcher_score=0.18,
    )
    assert as_confirmed_occupation(candidate) is None
    exposure = lookup_verified_task_exposure(candidate)
    assert exposure["status"] == "unresolved"
    assert exposure["occupation_wide_distribution"] is None
    assert exposure["tasks"] == []


def test_legacy_matched_code_dict_cannot_authorize_lookup() -> None:
    sneaky = {
        "status": "matched",
        "code": "11-1011.00",
        "title": "Chief Executives",
        "match_method": "exact_code",
        "candidate_code": "11-1011.00",
    }
    assert as_confirmed_occupation(sneaky) is None
    exposure = lookup_verified_task_exposure(sneaky)
    assert exposure["status"] != "verified"
    assert exposure["distribution"] is None


def test_user_confirmation_then_lookup() -> None:
    candidate = resolve_occupation(clusters=[{"soc_code": "15-1252.00", "similarity": 0.86}])
    assert candidate["status"] == "candidate"
    confirmed = confirm_occupation(
        verified_occupation_code="15-1252.00",
        confirmation_method="user_confirmation",
        candidate=candidate,
    )
    assert isinstance(confirmed, ConfirmedOccupation)
    assert confirmed.status == "confirmed"
    assert confirmed.verified_occupation_code == "15-1252.00"
    assert confirmed.verified_occupation_title == "Software Developers"
    assert confirmed.confirmation_method == "user_confirmation"
    exposure = lookup_verified_task_exposure(confirmed)
    assert exposure["status"] == "verified"
    assert exposure["match_method"] == "exact_code"
    assert exposure["occupation_code"] == "15-1252.00"
    assert exposure["distribution"] is not None


def test_explicit_occupation_code_is_documented_acceptance_rule() -> None:
    match = resolve_occupation(occupation_code="11-1011.00")
    assert match["status"] == "confirmed"
    assert match["confirmation_method"] == "explicit_occupation_code"
    assert match["verified_occupation_code"] == "11-1011.00"
    exposure = lookup_verified_task_exposure(match)
    assert exposure["status"] == "verified"


def test_invalid_confirmation_method_rejected() -> None:
    with pytest.raises(ValueError):
        confirm_occupation(
            verified_occupation_code="11-1011.00",
            confirmation_method="automatic_cluster",
        )
