"""Server-side occupation confirmation authorization.

Does not trust client-supplied verified codes, titles, allowlist flags, or
provenance labels. Does not store resume text in the Flask session.
"""

from __future__ import annotations

import secrets
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from task_exposure_assessor import (
    SOC_RE,
    confirm_occupation,
    load_benchmark,
    lookup_verified_task_exposure,
)

BASE_DIR = Path(__file__).resolve().parent
PRODUCT_800_PATH = BASE_DIR / "project_data" / "occupation_selection" / "occupation_master_800.csv"
SESSION_PENDING_KEY = "pending_occupation_analyses"
MAX_PENDING = 2
TTL_SECONDS = 3600

ERROR_ANALYSIS_NOT_FOUND = "analysis_not_found"
ERROR_ANALYSIS_NOT_OWNED = "analysis_not_owned"
ERROR_CANDIDATE_NOT_FOUND = "candidate_not_found"
ERROR_CANDIDATE_NOT_OWNED = "candidate_not_owned"
ERROR_CANDIDATE_INVALID = "candidate_invalid"
ERROR_EXPIRED = "analysis_expired"
ERROR_CONSUMED = "candidate_consumed"
ERROR_OCCUPATION_NOT_CANONICAL = "occupation_not_canonical"
ERROR_OUTSIDE_PRODUCT = "occupation_outside_product_scope"
ERROR_NO_BENCHMARK = "benchmark_coverage_unavailable"
ERROR_SELECTION_INVALID = "occupation_selection_invalid"
ERROR_INVALID_REQUEST = "invalid_request"
ERROR_ALLOWLIST_UNAVAILABLE = "allowlist_unavailable"


class AuthorizationError(Exception):
    def __init__(self, code: str, message: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra or {}


def _norm(code: object) -> str:
    return str(code or "").strip()


def _fail_closed(message: str, exc: Exception | None = None) -> None:
    error = AuthorizationError(
        ERROR_ALLOWLIST_UNAVAILABLE,
        message,
        {"status": "unavailable"},
    )
    if exc is not None:
        raise error from exc
    raise error


@lru_cache(maxsize=1)
def allowlist_inventory() -> dict[str, Any]:
    if not PRODUCT_800_PATH.is_file():
        _fail_closed("Occupation allowlist is unavailable because the 800 product file is missing")
    try:
        frame = pd.read_csv(PRODUCT_800_PATH, dtype=str)
    except Exception as exc:
        _fail_closed("Occupation allowlist is unavailable because the 800 product file is unreadable", exc)
    required = {"occupation_code", "occupation_title"}
    if required - set(frame.columns):
        _fail_closed("Occupation allowlist is unavailable because required columns are missing")
    rows = int(len(frame))
    codes = [_norm(code) for code in frame["occupation_code"].tolist()]
    titles = {
        _norm(row.get("occupation_code")): str(row.get("occupation_title") or "").strip()
        for row in frame.to_dict(orient="records")
    }
    unique = [code for code in dict.fromkeys(codes) if code]
    duplicates = int(len(codes) - len(unique))
    invalid = [code for code in unique if not SOC_RE.match(code)]
    missing_titles = [code for code in unique if not titles.get(code)]
    product_set = {code for code in unique if SOC_RE.match(code)}
    try:
        benchmark = load_benchmark()
    except Exception as exc:
        _fail_closed(
            "Occupation allowlist is unavailable because the published benchmark is missing or unreadable",
            exc,
        )
    if "occupation_code" not in benchmark.columns:
        _fail_closed("Occupation allowlist is unavailable because the published benchmark is malformed")
    bench_codes = set(benchmark["occupation_code"].map(_norm))
    covered = sorted(code for code in product_set if code in bench_codes)
    uncovered = sorted(code for code in product_set if code not in bench_codes)
    selectable: dict[str, dict[str, Any]] = {}
    for code in covered:
        title = titles.get(code) or ""
        if not title:
            continue
        selectable[code] = {
            "occupation_code": code,
            "occupation_title": title,
            "in_product_800": True,
            "benchmark_coverage": True,
            "selectable": True,
        }
    return {
        "source_rows": rows,
        "unique_source_codes": len(unique),
        "duplicates": duplicates,
        "invalid_codes": invalid,
        "missing_titles": missing_titles,
        "benchmark_covered_codes": len(covered),
        "benchmark_uncovered_codes": len(uncovered),
        "selectable_codes": len(selectable),
        "product_set": frozenset(product_set),
        "benchmark_set": frozenset(bench_codes),
        "selectable": selectable,
        "titles": titles,
    }


def selectable_occupations() -> list[dict[str, str]]:
    inventory = allowlist_inventory()
    return [
        {"occupation_code": item["occupation_code"], "occupation_title": item["occupation_title"]}
        for item in sorted(inventory["selectable"].values(), key=lambda row: row["occupation_title"].lower())
    ]


def is_product_800(code: str) -> bool:
    return _norm(code) in allowlist_inventory()["product_set"]


def is_benchmark_covered(code: str) -> bool:
    return _norm(code) in allowlist_inventory()["benchmark_set"]


def is_selectable(code: str) -> bool:
    return _norm(code) in allowlist_inventory()["selectable"]


def canonical_title(code: str) -> str | None:
    item = allowlist_inventory()["selectable"].get(_norm(code))
    if item:
        return str(item["occupation_title"])
    return allowlist_inventory()["titles"].get(_norm(code)) or None


def _ensure_session_id(session: Any) -> str:
    token = session.get("_occupation_session_nonce")
    if not token:
        token = secrets.token_urlsafe(16)
        session["_occupation_session_nonce"] = token
        session.modified = True
    return str(token)


def prune_pending(session: Any, now: float | None = None) -> dict[str, dict[str, Any]]:
    pending = dict(session.get(SESSION_PENDING_KEY) or {})
    stamp = now if now is not None else time.time()
    kept: dict[str, dict[str, Any]] = {}
    for analysis_id, record in pending.items():
        expires = float(record.get("expires_at") or 0)
        if expires and expires < stamp:
            continue
        kept[str(analysis_id)] = record
    live = {key: value for key, value in kept.items() if not value.get("consumed")}
    consumed = {key: value for key, value in kept.items() if value.get("consumed")}
    if len(live) > MAX_PENDING:
        ordered = sorted(live.items(), key=lambda item: float(item[1].get("created_at") or 0), reverse=True)
        live = dict(ordered[:MAX_PENDING])
    kept = {**consumed, **live}
    session[SESSION_PENDING_KEY] = kept
    session.modified = True
    return kept


def attach_pending_analysis(
    session: Any,
    *,
    candidate_code: str | None,
    candidate_title: str | None,
    matcher_score: float | None,
    user_id: int | None,
    now: float | None = None,
) -> dict[str, str]:
    stamp = now if now is not None else time.time()
    nonce = _ensure_session_id(session)
    pending = prune_pending(session, now=stamp)
    analysis_id = secrets.token_urlsafe(12)
    candidate_id = secrets.token_urlsafe(12)
    pending[analysis_id] = {
        "analysis_id": analysis_id,
        "candidate_id": candidate_id,
        "candidate_code": _norm(candidate_code) or None,
        "candidate_title": str(candidate_title or "").strip() or None,
        "candidate_matcher_score": matcher_score,
        "created_at": stamp,
        "expires_at": stamp + TTL_SECONDS,
        "consumed": False,
        "session_nonce": nonce,
        "user_id": user_id,
    }
    live = {key: value for key, value in pending.items() if not value.get("consumed")}
    consumed = {key: value for key, value in pending.items() if value.get("consumed")}
    if len(live) > MAX_PENDING:
        ordered = sorted(live.items(), key=lambda item: float(item[1].get("created_at") or 0), reverse=True)
        live = dict(ordered[:MAX_PENDING])
    pending = {**consumed, **live}
    session[SESSION_PENDING_KEY] = pending
    session.modified = True
    return {"analysis_id": analysis_id, "candidate_id": candidate_id}


def _load_owned_record(
    session: Any,
    *,
    analysis_id: str,
    candidate_id: str | None,
    user_id: int | None,
    require_candidate: bool,
    now: float | None = None,
) -> dict[str, Any]:
    if not analysis_id:
        raise AuthorizationError(ERROR_INVALID_REQUEST, "analysis_id is required")
    pending = prune_pending(session, now=now)
    record = pending.get(analysis_id)
    if record is None:
        raise AuthorizationError(ERROR_ANALYSIS_NOT_FOUND, "Analysis was not found in this session")
    nonce = _ensure_session_id(session)
    if record.get("session_nonce") != nonce:
        raise AuthorizationError(ERROR_ANALYSIS_NOT_OWNED, "Analysis does not belong to this session")
    stored_user = record.get("user_id")
    if stored_user is not None and user_id != stored_user:
        raise AuthorizationError(ERROR_ANALYSIS_NOT_OWNED, "Analysis does not belong to this user")
    if user_id is not None and stored_user is not None and stored_user != user_id:
        raise AuthorizationError(ERROR_ANALYSIS_NOT_OWNED, "Analysis does not belong to this user")
    if record.get("consumed"):
        raise AuthorizationError(ERROR_CONSUMED, "This confirmation record has already been used")
    expires = float(record.get("expires_at") or 0)
    stamp = now if now is not None else time.time()
    if expires and expires < stamp:
        raise AuthorizationError(ERROR_EXPIRED, "This analysis confirmation has expired")
    if require_candidate:
        if not candidate_id:
            raise AuthorizationError(ERROR_INVALID_REQUEST, "candidate_id is required")
        if candidate_id != record.get("candidate_id"):
            raise AuthorizationError(ERROR_CANDIDATE_NOT_OWNED, "candidate_id does not belong to this analysis")
        if not record.get("candidate_code"):
            raise AuthorizationError(ERROR_CANDIDATE_INVALID, "No server-issued candidate occupation is stored")
    return record


def consume_record(session: Any, analysis_id: str) -> None:
    pending = dict(session.get(SESSION_PENDING_KEY) or {})
    record = pending.get(analysis_id)
    if record is not None:
        record = dict(record)
        record["consumed"] = True
        pending[analysis_id] = record
        session[SESSION_PENDING_KEY] = pending
        session.modified = True


def _lookup_payload(confirmed, skills: list[str] | None = None) -> dict[str, Any]:
    exposure = lookup_verified_task_exposure(confirmed, skills=skills or [], resume_text="")
    occupation = confirmed.to_dict()
    return {
        "success": True,
        "occupation_match": occupation,
        "matched_occupation": occupation,
        "task_exposure": exposure,
        "contextual_task_exposure": exposure,
    }


def confirm_server_candidate(
    session: Any,
    *,
    analysis_id: str,
    candidate_id: str,
    user_id: int | None,
    now: float | None = None,
) -> dict[str, Any]:
    record = _load_owned_record(
        session,
        analysis_id=analysis_id,
        candidate_id=candidate_id,
        user_id=user_id,
        require_candidate=True,
        now=now,
    )
    code = _norm(record.get("candidate_code"))
    if not SOC_RE.match(code):
        raise AuthorizationError(ERROR_CANDIDATE_INVALID, "Stored candidate code is not a valid O*NET SOC")
    if not is_product_800(code):
        extra = {
            "status": "unavailable",
            "research_benchmark_available": is_benchmark_covered(code),
            "product_coverage_available": False,
        }
        raise AuthorizationError(
            ERROR_OUTSIDE_PRODUCT,
            "Occupation is available in the research benchmark but outside current product coverage"
            if is_benchmark_covered(code)
            else "Occupation is outside current product coverage",
            extra,
        )
    if not is_selectable(code):
        raise AuthorizationError(
            ERROR_NO_BENCHMARK,
            "Verified published benchmark coverage is not available for this occupation",
        )
    title = canonical_title(code) or record.get("candidate_title")
    confirmed = confirm_occupation(
        verified_occupation_code=code,
        confirmation_method="candidate_confirmation",
        verified_occupation_title=title,
        matcher_score=record.get("candidate_matcher_score"),
    )
    payload = confirmed.to_dict()
    payload["source"] = "server_issued_candidate"
    consume_record(session, analysis_id)
    result = _lookup_payload(confirmed)
    result["occupation_match"]["source"] = "server_issued_candidate"
    result["occupation_match"]["confirmation_method"] = "candidate_confirmation"
    result["matched_occupation"] = result["occupation_match"]
    return result


def select_supported_occupation(
    session: Any,
    *,
    analysis_id: str,
    selected_code: str,
    user_id: int | None,
    now: float | None = None,
) -> dict[str, Any]:
    _load_owned_record(
        session,
        analysis_id=analysis_id,
        candidate_id=None,
        user_id=user_id,
        require_candidate=False,
        now=now,
    )
    code = _norm(selected_code)
    if not SOC_RE.match(code):
        raise AuthorizationError(ERROR_SELECTION_INVALID, "selected_code is not a valid O*NET SOC")
    if code not in allowlist_inventory()["titles"] and not is_product_800(code):
        if is_benchmark_covered(code):
            raise AuthorizationError(
                ERROR_OUTSIDE_PRODUCT,
                "Occupation is available in the research benchmark but outside current product coverage",
                {
                    "status": "unavailable",
                    "research_benchmark_available": True,
                    "product_coverage_available": False,
                },
            )
        raise AuthorizationError(ERROR_OCCUPATION_NOT_CANONICAL, "Occupation code is not in the canonical product dataset")
    if not is_product_800(code):
        raise AuthorizationError(
            ERROR_OUTSIDE_PRODUCT,
            "Occupation is available in the research benchmark but outside current product coverage"
            if is_benchmark_covered(code)
            else "Occupation is outside current product coverage",
            {
                "status": "unavailable",
                "research_benchmark_available": is_benchmark_covered(code),
                "product_coverage_available": False,
            },
        )
    if not is_selectable(code):
        raise AuthorizationError(
            ERROR_NO_BENCHMARK,
            "Verified published benchmark coverage is not available for this occupation",
        )
    title = canonical_title(code)
    if not title:
        raise AuthorizationError(ERROR_OCCUPATION_NOT_CANONICAL, "Occupation title is missing from server data")
    confirmed = confirm_occupation(
        verified_occupation_code=code,
        confirmation_method="user_selected_occupation",
        verified_occupation_title=title,
    )
    consume_record(session, analysis_id)
    result = _lookup_payload(confirmed)
    result["occupation_match"]["source"] = "user_selection"
    result["occupation_match"]["confirmation_method"] = "user_selected_occupation"
    result["matched_occupation"] = result["occupation_match"]
    return result
