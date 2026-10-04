"""Retrieve published GPTs-are-GPTs E0/E1/E2 labels after occupation acceptance.

This module does not train, invent, or resume-condition E0/E1/E2 labels.
Resume text may only rank which stored tasks are shown as evidence.

Occupation states are distinct:
- candidate: matcher suggestion only (candidate_code). Does not authorize lookup.
- confirmed: accepted identifier (verified_occupation_code) after an allowed method.
- verified: published benchmark mapping for a confirmed occupation.

Matcher cluster SOCs must not skip confirmation. Lookup accepts ConfirmedOccupation
only, never OccupationCandidate or a dict that only has candidate_code.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from experiments.task_exposure.product_copy import (
    CAREER_ACTION_DISCLAIMER,
    CAREER_ACTIONS,
    CLASSES,
    MODEL_ID,
    TASK_ANALYSIS_COPY,
)

log = logging.getLogger("prayash.task_exposure")

BASE_DIR = Path(__file__).resolve().parent
BENCHMARK_PATH = (
    BASE_DIR
    / "experiments"
    / "task_exposure"
    / "data"
    / "public_benchmark"
    / "public_gpts_are_gpts_benchmark.csv"
)
IDENTITY_PATH = (
    BASE_DIR
    / "experiments"
    / "task_exposure"
    / "reports"
    / "public_benchmark"
    / "model_identity.json"
)
PRODUCT_800_PATH = BASE_DIR / "project_data" / "occupation_selection" / "occupation_master_800.csv"

TAXONOMY_NAME = "GPTs-are-GPTs"
TAXONOMY_VERSION = "human_labels E0/E1/E2"
LOOKUP_MODE = "published_benchmark_lookup"
SOURCE_TYPE_LOOKUP = "published_benchmark_lookup"
UNRESOLVED_REASON = "No exact or approved occupation mapping exists"
FORBIDDEN_WEAK_SUPERVISION_FILES = (
    "task_exposure_training.csv",
    "final_validated_task_training_table.csv",
    "ai_pass1_scores.jsonl",
    "ai_pass2_scores.jsonl",
)
CROSSWALK_PATH = (
    BASE_DIR / "project_data" / "occupation_selection" / "approved_occupation_alias_crosswalk.csv"
)
SOC_RE = re.compile(r"^\d{2}-\d{4}\.\d{2}$")
ALLOWED_CONFIRMATION_METHODS = frozenset(
    {
        "user_confirmation",
        "explicit_occupation_code",
        "candidate_confirmation",
        "user_selected_occupation",
    }
)
CANDIDATE_LOOKUP_REFUSAL = "candidate_occupation_does_not_authorize_benchmark_lookup"
SCORE_INTERPRETATION_CANDIDATE = "uncalibrated candidate score"
SCORE_INTERPRETATION_MATCHER = "uncalibrated matcher score"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "not",
    "but",
    "you",
    "your",
    "our",
    "into",
    "onto",
    "over",
    "under",
}


@dataclass(frozen=True)
class OccupationCandidate:
    """Provisional matcher output. Must not be passed to production lookup as verified."""

    candidate_code: str | None
    candidate_title: str | None
    matcher_score: float | None = None
    score_interpretation: str = SCORE_INTERPRETATION_CANDIDATE
    matcher_source: str | None = None
    mapping_source: str | None = None
    review_status: str | None = None
    reason: str | None = None

    @property
    def status(self) -> str:
        return "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "candidate",
            "candidate_code": self.candidate_code,
            "candidate_title": self.candidate_title,
            "matcher_score": self.matcher_score,
            "score_interpretation": self.score_interpretation,
            "matcher_source": self.matcher_source,
            "mapping_source": self.mapping_source,
            "review_status": self.review_status,
            "reason": self.reason,
            "confidence": self.matcher_score,
            "confidence_kind": "occupation_match_similarity",
            "match_method": None,
            "code": None,
            "title": None,
            "verified_occupation_code": None,
            "verified_occupation_title": None,
        }


@dataclass(frozen=True)
class ConfirmedOccupation:
    """Accepted occupation identifier. The only input type production lookup may use."""

    verified_occupation_code: str
    verified_occupation_title: str
    confirmation_method: str
    matcher_score: float | None = None
    score_interpretation: str = SCORE_INTERPRETATION_MATCHER
    mapping_source: str | None = None
    review_status: str | None = None
    match_method: str = "exact_code"

    @property
    def status(self) -> str:
        return "confirmed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "confirmed",
            "verified_occupation_code": self.verified_occupation_code,
            "verified_occupation_title": self.verified_occupation_title,
            "confirmation_method": self.confirmation_method,
            "matcher_score": self.matcher_score,
            "score_interpretation": self.score_interpretation,
            "mapping_source": self.mapping_source,
            "review_status": self.review_status,
            "match_method": self.match_method,
            "confidence": self.matcher_score,
            "confidence_kind": "occupation_match_similarity",
            "code": None,
            "title": None,
            "candidate_code": None,
            "candidate_title": None,
        }


def _norm_title(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _norm_code(value: object) -> str:
    return str(value or "").strip()


@lru_cache(maxsize=1)
def load_model_identity() -> dict[str, Any]:
    if not IDENTITY_PATH.is_file():
        return {"model_id": MODEL_ID, "benchmark_commit": None, "derived_dataset_sha256": None}
    return json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_product_800_codes() -> frozenset[str]:
    if not PRODUCT_800_PATH.is_file():
        log.warning("800-occupation product file missing at %s", PRODUCT_800_PATH)
        return frozenset()
    frame = pd.read_csv(PRODUCT_800_PATH, dtype=str, usecols=["occupation_code"])
    return frozenset(_norm_code(code) for code in frame["occupation_code"].tolist() if _norm_code(code))


@lru_cache(maxsize=1)
def load_approved_crosswalk() -> list[dict[str, str]]:
    """Return only rows with review_status=approved. Currently empty by design."""
    if not CROSSWALK_PATH.is_file():
        return []
    frame = pd.read_csv(CROSSWALK_PATH, dtype=str)
    if frame.empty:
        return []
    rows: list[dict[str, str]] = []
    for raw in frame.to_dict(orient="records"):
        status = str(raw.get("review_status") or "").strip().lower()
        if status != "approved":
            continue
        alias = _norm_title(raw.get("alias"))
        code = _norm_code(raw.get("canonical_occupation_code"))
        if alias and SOC_RE.match(code):
            rows.append({str(k): str(v or "") for k, v in raw.items()})
    return rows


def approved_crosswalk_count() -> int:
    return len(load_approved_crosswalk())


@lru_cache(maxsize=1)
def load_benchmark() -> pd.DataFrame:
    if BENCHMARK_PATH.name in FORBIDDEN_WEAK_SUPERVISION_FILES:
        raise RuntimeError("Production lookup refused a weak-supervision path.")
    if not BENCHMARK_PATH.is_file():
        raise FileNotFoundError(f"Published task-exposure benchmark is missing: {BENCHMARK_PATH}")
    if BENCHMARK_PATH.name != "public_gpts_are_gpts_benchmark.csv":
        raise RuntimeError("Production lookup must use the published public benchmark CSV.")
    columns = [
        "occupation_code",
        "occupation_title",
        "task_id",
        "task_text",
        "human_labels",
        "label_source",
        "source_repository",
        "source_commit",
        "source_onet_version_documented",
        "project_onet_version",
    ]
    frame = pd.read_csv(BENCHMARK_PATH, dtype=str, usecols=columns)
    frame["occupation_code"] = frame["occupation_code"].map(_norm_code)
    frame["occupation_title_norm"] = frame["occupation_title"].map(_norm_title)
    frame["human_labels"] = frame["human_labels"].str.strip().str.upper()
    return frame


def _empty_exposure(*, status: str, reason: str, identity: dict[str, Any], match_method: str = "unresolved") -> dict[str, Any]:
    return {
        "status": "unresolved" if status != "unavailable" else "unavailable",
        "source_type": SOURCE_TYPE_LOOKUP,
        "match_method": match_method if status == "unresolved" else None,
        "reason": reason or UNRESOLVED_REASON,
        "taxonomy": TAXONOMY_NAME,
        "taxonomy_version": TAXONOMY_VERSION,
        "label_field": "human_labels",
        "label_taxonomy": "E0/E1/E2",
        "model_version": identity.get("model_id") or MODEL_ID,
        "lookup_mode": LOOKUP_MODE,
        "benchmark_source": "GPTs-are-GPTs",
        "benchmark_repository_commit": identity.get("benchmark_commit") or "0471612fef3cc22b74fb884d27bff9dbd3770582",
        "benchmark_onet_version": "27.2",
        "project_onet_version": "31.0",
        "source": identity.get("benchmark_source") or "openai/GPTs-are-GPTs",
        "source_version": identity.get("benchmark_commit"),
        "source_dataset_sha256": identity.get("derived_dataset_sha256"),
        "research_population": "923 occupations",
        "product_population": "800 occupations",
        "research_scope": "GPTs-are-GPTs benchmark, 923 occupations",
        "product_coverage": "selected 800 common occupations",
        "in_research_923": False,
        "in_product_800": False,
        "occupation_task_count": 0,
        "labelled_task_count": 0,
        "unlabelled_task_count": 0,
        "excluded_task_count": 0,
        "normalization_denominator": 0,
        "occupation_wide_counts": {"E0": 0, "E1": 0, "E2": 0},
        "distribution": None,
        "occupation_wide_distribution": None,
        "resume_relevant": {
            "task_count": 0,
            "labelled_task_count": 0,
            "normalization_denominator": 0,
            "distribution": None,
            "tasks": [],
        },
        "tasks": [],
        "relevant_tasks": [],
        "label_confidence": None,
        "confidence_note": "No calibrated task-level probability is available. Labels are retrieved, not predicted from the resume or a classifier.",
        "interpretation": TASK_ANALYSIS_COPY,
        "disclaimer": (
            "These percentages describe the distribution of tasks under the published "
            "GPTs-are-GPTs taxonomy. They are not probabilities of job loss."
        ),
    }


def _distribution(labels: list[str]) -> tuple[dict[str, float] | None, dict[str, int], int]:
    valid = [label for label in labels if label in CLASSES]
    counts = {cls: valid.count(cls) for cls in CLASSES}
    denominator = len(valid)
    if not denominator:
        return None, counts, 0
    dist = {cls: counts[cls] / denominator for cls in CLASSES}
    return dist, counts, denominator


def _tokens(text: str) -> set[str]:
    return {tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) > 2 and tok not in _STOP}


def _rank_relevant_tasks(tasks: list[dict[str, Any]], skills: list[str], resume_text: str) -> list[dict[str, Any]]:
    evidence = _tokens(" ".join(skills) + " " + (resume_text or "")[:4000])
    ranked = sorted(
        tasks,
        key=lambda item: (-len(_tokens(str(item.get("task") or "")) & evidence), str(item.get("task") or "")),
    )
    return ranked[:8]


def _title_for_code(frame: pd.DataFrame, code: str) -> str:
    return str(frame.loc[frame["occupation_code"] == code, "occupation_title"].iloc[0])


def _score(value: object) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def as_confirmed_occupation(value: object) -> ConfirmedOccupation | None:
    """Return a confirmed occupation only. Candidates and legacy matched+code dicts are rejected."""
    if isinstance(value, OccupationCandidate):
        return None
    if isinstance(value, ConfirmedOccupation):
        if value.confirmation_method not in ALLOWED_CONFIRMATION_METHODS:
            return None
        if not SOC_RE.match(value.verified_occupation_code):
            return None
        return value
    if not isinstance(value, dict):
        return None
    if value.get("status") == "candidate":
        return None
    if value.get("candidate_code") and value.get("status") != "confirmed":
        return None
    if value.get("confirmation_method") not in ALLOWED_CONFIRMATION_METHODS:
        return None
    if value.get("status") != "confirmed":
        return None
    code = _norm_code(value.get("verified_occupation_code"))
    title = str(value.get("verified_occupation_title") or "").strip()
    if not SOC_RE.match(code) or not title:
        return None
    match_method = str(value.get("match_method") or "exact_code")
    if match_method not in {"exact_code", "approved_crosswalk"}:
        match_method = "exact_code"
    return ConfirmedOccupation(
        verified_occupation_code=code,
        verified_occupation_title=title,
        confirmation_method=str(value.get("confirmation_method")),
        matcher_score=_score(value.get("matcher_score", value.get("confidence"))),
        score_interpretation=str(value.get("score_interpretation") or SCORE_INTERPRETATION_MATCHER),
        mapping_source=value.get("mapping_source"),
        review_status=value.get("review_status"),
        match_method=match_method,
    )


def confirm_occupation(
    *,
    verified_occupation_code: str,
    confirmation_method: str,
    candidate: OccupationCandidate | dict[str, Any] | None = None,
    verified_occupation_title: str | None = None,
    matcher_score: float | None = None,
) -> ConfirmedOccupation:
    """Authorize an occupation identifier. Does not look up E0/E1/E2 labels."""
    method = str(confirmation_method or "").strip()
    if method not in ALLOWED_CONFIRMATION_METHODS:
        raise ValueError("confirmation_method is not an allowed server-controlled value")
    code = _norm_code(verified_occupation_code)
    if not SOC_RE.match(code):
        raise ValueError("verified_occupation_code must be an O*NET SOC (##-####.##)")

    candidate_dict = candidate.to_dict() if isinstance(candidate, OccupationCandidate) else (candidate or {})
    title = str(verified_occupation_title or "").strip()
    score = matcher_score if matcher_score is not None else _score(
        candidate_dict.get("matcher_score", candidate_dict.get("confidence"))
    )
    mapping_source = candidate_dict.get("mapping_source")
    review_status = candidate_dict.get("review_status")
    match_method = "exact_code"
    if (
        candidate_dict.get("matcher_source") == "approved_crosswalk"
        and _norm_code(candidate_dict.get("candidate_code")) == code
    ):
        match_method = "approved_crosswalk"
        review_status = review_status or "approved"

    if not title:
        frame = load_benchmark()
        subset = frame[frame["occupation_code"] == code]
        if subset.empty:
            raise ValueError("verified_occupation_code is not in the published benchmark")
        title = _title_for_code(frame, code)

    return ConfirmedOccupation(
        verified_occupation_code=code,
        verified_occupation_title=title,
        confirmation_method=method,
        matcher_score=score,
        score_interpretation=SCORE_INTERPRETATION_MATCHER,
        mapping_source=mapping_source,
        review_status=review_status,
        match_method=match_method,
    )


def resolve_occupation(
    *,
    clusters: list[dict[str, Any]] | None = None,
    top_roles: list[dict[str, Any]] | None = None,
    occupation_code: str | None = None,
) -> dict[str, Any]:
    """Return a candidate from the matcher, or a confirmed occupation for an explicit SOC.

    Cluster SOC and title suggestions stay candidates. They never authorize lookup.
    Passing occupation_code is the documented explicit_occupation_code acceptance rule.
    """
    identity = load_model_identity()
    try:
        frame = load_benchmark()
    except FileNotFoundError as exc:
        return {
            "status": "unavailable",
            "reason": str(exc),
            "candidate_code": None,
            "candidate_title": None,
            "title": None,
            "code": None,
            "confidence": None,
            "confidence_kind": "occupation_match_similarity",
            "match_method": None,
        }

    codes = set(frame["occupation_code"].unique())
    title_map: dict[str, list[str]] = {}
    for code, title in (
        frame.drop_duplicates(["occupation_code"])[["occupation_code", "occupation_title_norm"]].itertuples(
            index=False, name=None
        )
    ):
        title_map.setdefault(title, [])
        if code not in title_map[title]:
            title_map[title].append(code)

    requested = _norm_code(occupation_code)
    if requested:
        if not SOC_RE.match(requested):
            return {
                "status": "unresolved",
                "reason": "occupation_code_not_onet_soc_format",
                "title": None,
                "code": None,
                "verified_occupation_code": None,
                "confidence": None,
                "confidence_kind": "occupation_match_similarity",
                "match_method": None,
            }
        if requested not in codes:
            return {
                "status": "unresolved",
                "reason": UNRESOLVED_REASON,
                "title": None,
                "code": None,
                "verified_occupation_code": None,
                "confidence": None,
                "confidence_kind": "occupation_match_similarity",
                "match_method": None,
            }
        confirmed = confirm_occupation(
            verified_occupation_code=requested,
            confirmation_method="explicit_occupation_code",
            verified_occupation_title=_title_for_code(frame, requested),
        )
        return confirmed.to_dict()

    for cluster in clusters or []:
        code = _norm_code(cluster.get("soc_code"))
        if not SOC_RE.match(code) or code not in codes:
            continue
        return OccupationCandidate(
            candidate_code=code,
            candidate_title=_title_for_code(frame, code),
            matcher_score=_score(cluster.get("similarity")),
            matcher_source="cluster_soc",
        ).to_dict()

    for role in top_roles or []:
        title_key = _norm_title(role.get("job_role"))
        if not title_key:
            continue
        matched_codes = title_map.get(title_key) or []
        if len(matched_codes) > 1:
            return OccupationCandidate(
                candidate_code=None,
                candidate_title=str(role.get("job_role") or "") or None,
                matcher_score=_score(role.get("similarity")),
                matcher_source="exact_title",
                reason="ambiguous_exact_title_match",
            ).to_dict()
        if len(matched_codes) == 1:
            code = matched_codes[0]
            return OccupationCandidate(
                candidate_code=code,
                candidate_title=_title_for_code(frame, code),
                matcher_score=_score(role.get("similarity")),
                matcher_source="exact_title",
            ).to_dict()

    for role in top_roles or []:
        alias_key = _norm_title(role.get("job_role"))
        for mapping in load_approved_crosswalk():
            if _norm_title(mapping.get("alias")) != alias_key:
                continue
            code = _norm_code(mapping.get("canonical_occupation_code"))
            if code not in codes:
                continue
            return OccupationCandidate(
                candidate_code=code,
                candidate_title=_title_for_code(frame, code),
                matcher_score=_score(role.get("similarity")),
                matcher_source="approved_crosswalk",
                mapping_source=mapping.get("mapping_source"),
                review_status=mapping.get("review_status"),
            ).to_dict()

    fallback_title = None
    fallback_confidence = None
    if top_roles:
        fallback_title = top_roles[0].get("job_role")
        if top_roles[0].get("similarity") is not None:
            fallback_confidence = round(float(top_roles[0]["similarity"]), 4)
    return {
        "status": "unresolved",
        "reason": UNRESOLVED_REASON,
        "candidate_code": None,
        "candidate_title": fallback_title,
        "title": None,
        "code": None,
        "confidence": fallback_confidence,
        "confidence_kind": "occupation_match_similarity",
        "match_method": "unresolved",
        "model_version_note": identity.get("model_id"),
    }


def lookup_verified_task_exposure(
    verified_occupation: ConfirmedOccupation | OccupationCandidate | dict[str, Any],
    *,
    skills: list[str] | None = None,
    resume_text: str = "",
) -> dict[str, Any]:
    """Production path: retrieve published human_labels for a confirmed occupation only."""
    identity = load_model_identity()
    confirmed = as_confirmed_occupation(verified_occupation)
    if confirmed is None:
        status = "unresolved"
        reason = CANDIDATE_LOOKUP_REFUSAL
        if isinstance(verified_occupation, dict):
            raw_status = str(verified_occupation.get("status") or "")
            if raw_status in {"unavailable", "unresolved"}:
                status = raw_status
                reason = str(verified_occupation.get("reason") or UNRESOLVED_REASON)
        return _empty_exposure(status=status, reason=reason, identity=identity)

    match_method = confirmed.match_method if confirmed.match_method in {"exact_code", "approved_crosswalk"} else "exact_code"

    try:
        frame = load_benchmark()
    except FileNotFoundError as exc:
        return _empty_exposure(status="unavailable", reason=str(exc), identity=identity)

    code = confirmed.verified_occupation_code
    subset = frame[frame["occupation_code"] == code]
    if subset.empty:
        return _empty_exposure(
            status="unresolved",
            reason=UNRESOLVED_REASON,
            identity=identity,
            match_method="unresolved",
        )

    product_codes = load_product_800_codes()
    tasks: list[dict[str, Any]] = []
    labels: list[str] = []
    unlabelled = 0
    excluded = 0
    for row in subset.itertuples(index=False):
        label = str(row.human_labels or "").strip().upper()
        if label not in CLASSES:
            if label:
                excluded += 1
            else:
                unlabelled += 1
            continue
        labels.append(label)
        tasks.append(
            {
                "task": str(row.task_text or "").strip(),
                "task_id": str(row.task_id or "").strip(),
                "category": label,
                "label_source": str(row.label_source or "published_benchmark"),
                "label_confidence": None,
                "model_score": None,
                "score_interpretation": "Retrieved published human_labels; not a calibrated probability",
                "confidence_note": "No calibrated task-level probability is available",
                "source": str(row.source_repository or identity.get("benchmark_source") or ""),
                "source_version": str(row.source_commit or identity.get("benchmark_commit") or ""),
                "source_onet_version_documented": str(row.source_onet_version_documented or "27.2"),
                "project_onet_version": str(row.project_onet_version or "31.0"),
            }
        )

    dist, counts, denominator = _distribution(labels)
    relevant = _rank_relevant_tasks(tasks, skills or [], resume_text)
    relevant_labels = [str(item.get("category")) for item in relevant]
    relevant_dist, relevant_counts, relevant_den = _distribution(relevant_labels)
    return {
        "status": "verified",
        "source_type": SOURCE_TYPE_LOOKUP,
        "match_method": match_method,
        "occupation_code": code,
        "mapping_source": confirmed.mapping_source,
        "review_status": confirmed.review_status,
        "reason": None,
        "taxonomy": TAXONOMY_NAME,
        "taxonomy_version": TAXONOMY_VERSION,
        "label_field": "human_labels",
        "label_taxonomy": "E0/E1/E2",
        "model_version": identity.get("model_id") or MODEL_ID,
        "lookup_mode": LOOKUP_MODE,
        "benchmark_source": "GPTs-are-GPTs",
        "benchmark_repository_commit": identity.get("benchmark_commit") or "0471612fef3cc22b74fb884d27bff9dbd3770582",
        "benchmark_onet_version": "27.2",
        "project_onet_version": "31.0",
        "source": identity.get("benchmark_source") or "openai/GPTs-are-GPTs",
        "source_version": identity.get("benchmark_commit"),
        "source_dataset_sha256": identity.get("derived_dataset_sha256"),
        "research_population": "923 occupations",
        "product_population": "800 occupations",
        "research_scope": "GPTs-are-GPTs benchmark, 923 occupations",
        "product_coverage": "selected 800 common occupations",
        "in_research_923": True,
        "in_product_800": code in product_codes,
        "occupation_task_count": int(len(subset)),
        "labelled_task_count": denominator,
        "unlabelled_task_count": unlabelled,
        "excluded_task_count": excluded,
        "normalization_denominator": denominator,
        "occupation_wide_counts": counts,
        "distribution": dist,
        "occupation_wide_distribution": dist,
        "resume_relevant": {
            "task_count": len(relevant),
            "labelled_task_count": relevant_den,
            "normalization_denominator": relevant_den,
            "counts": relevant_counts,
            "distribution": relevant_dist,
            "note": "Resume relevance ranks which verified tasks are shown. It does not relabel tasks or replace occupation-wide distribution.",
            "tasks": relevant,
        },
        "task_count": denominator,
        "tasks": relevant,
        "relevant_tasks": relevant,
        "label_confidence": None,
        "confidence_note": "No calibrated task-level probability is available. Labels are retrieved, not predicted from the resume or a classifier.",
        "interpretation": TASK_ANALYSIS_COPY,
        "disclaimer": (
            "These percentages describe the distribution of tasks under the published "
            "GPTs-are-GPTs taxonomy. They are not probabilities of job loss."
        ),
    }


def retrieve_task_exposure(
    verified_occupation: ConfirmedOccupation | OccupationCandidate | dict[str, Any],
    *,
    skills: list[str] | None = None,
    resume_text: str = "",
) -> dict[str, Any]:
    """Compatibility alias for lookup_verified_task_exposure."""
    return lookup_verified_task_exposure(verified_occupation, skills=skills, resume_text=resume_text)


def career_development_from_analysis(
    *,
    roadmap: list[dict[str, Any]] | None = None,
    skills: list[str] | None = None,
    top_roles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    courses = []
    for item in (roadmap or [])[:8]:
        courses.append(
            {
                "course": item.get("course"),
                "skill": item.get("skill"),
                "reason": item.get("reason"),
                "url": item.get("url"),
            }
        )
    role_skills: list[str] = []
    for role in (top_roles or [])[:2]:
        for skill in role.get("skills") or []:
            text = str(skill).strip()
            if text and text.lower() not in {s.lower() for s in role_skills}:
                role_skills.append(text)
    detected = {str(s).strip().lower() for s in (skills or []) if str(s).strip()}
    skill_gaps = [skill for skill in role_skills if skill.lower() not in detected][:8]
    projects = [
        "Document a portfolio example that shows domain judgment alongside tool use.",
        "Build a small project that includes verification or quality-control of model-assisted output.",
    ]
    return {
        "skill_gaps": skill_gaps,
        "courses": courses,
        "projects": projects,
        "recommendations": list(CAREER_ACTIONS),
        "disclaimer": CAREER_ACTION_DISCLAIMER,
    }


def personal_job_loss_probability_supported() -> bool:
    """Hard stop: no individual employment-outcome model is present."""
    return False
