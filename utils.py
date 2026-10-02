"""
Prayash — Shared Utilities
===========================
Centralises helpers used across the application so that modules do not
duplicate _clean_text, risk thresholds, or string-processing logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ── Project Paths ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "ml_models"


# ── String / Text Helpers ──────────────────────────────────────────

def clean_text(value: Any) -> str:
    """Normalise a raw CSV / form value into a clean string.

    Handles None, NaN (numpy), inline whitespace, and the literal
    string ``"nan"`` that often appears in CSV exports.
    """
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.lower() == "nan" else text


# Alias for ML modules that expect the name ``normalize_text``
normalize_text = clean_text


def parse_listish(value: Any) -> list[str]:
    """Parse a CSV field that may contain a Python list literal or a
    comma-/semicolon-/pipe-delimited string into a clean string list."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    text = clean_text(value)
    if not text:
        return []
    try:
        import ast
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [clean_text(item) for item in parsed if clean_text(item)]
    except Exception:
        pass
    parts = [part.strip(" []\"'") for part in re.split(r"[,;/|]", text)]
    return [p for p in parts if p]


def split_keywords(text: str) -> list[str]:
    """Extract meaningful keyword tokens from a piece of text."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text.lower())
    stop_words: set[str] = {
        "with", "from", "that", "this", "your", "have", "will",
        "into", "about", "for", "and", "the", "are", "our", "you",
        "role", "work", "team", "data", "skills", "career", "resume",
    }
    return [t for t in tokens if t not in stop_words]


def format_top_skills(keywords: list[str], limit: int = 8) -> list[str]:
    """Title-cased, deduplicated skill list capped at *limit* items."""
    seen: set[str] = set()
    out: list[str] = []
    for k in keywords:
        normalised = k.replace("_", " ").strip().title()
        if normalised and normalised not in seen:
            seen.add(normalised)
            out.append(normalised)
            if len(out) >= limit:
                break
    return out


# ── Email Validation ───────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def is_valid_email(email: str) -> bool:
    """Return True when *email* looks like a plausible email address."""
    return bool(_EMAIL_RE.match(email.strip()))


# ── Risk Thresholds (single source of truth) ───────────────────────

RISK_LOW: float = 0.35
"""Scores below this value are labelled *Low*."""

RISK_MODERATE: float = 0.70
"""Scores below this value (but >= *RISK_LOW*) are labelled *Moderate*.

Scores >= *RISK_MODERATE* are labelled *Elevated*.
"""


def risk_label(score: float) -> str:
    """Map a numeric risk score to its human-readable band."""
    if score < RISK_LOW:
        return "Low"
    if score < RISK_MODERATE:
        return "Moderate"
    return "Elevated"


# ── CSV / Data Helpers (shared by train_model, evaluation) ─────────

def read_csv_any(*relative_paths: str) -> pd.DataFrame:
    """Read the first CSV that exists from *relative_paths* inside DATA_DIR.

    Normalises column names with ``normalize_text`` so callers do not have
    to handle inconsistent capitalisation.
    """
    for relative_path in relative_paths:
        candidate = DATA_DIR / relative_path
        if candidate.exists():
            frame = pd.read_csv(candidate, sep=None, engine="python")
            frame.columns = [normalize_text(column) for column in frame.columns]
            return frame
    raise FileNotFoundError(
        f"None of the expected files were found: {', '.join(relative_paths)}"
    )


# ── ML Text-Building Helpers ───────────────────────────────────────

def build_job_text(row: pd.Series) -> str:
    """Concatenate job attributes into a single TF-IDF-friendly string."""
    pieces = [
        row.get("job_role", ""),
        row.get("industry", ""),
        row.get("education_level", ""),
        f"experience {row.get('experience_required_years', '')}",
        f"salary {row.get('avg_salary_usd', '')}",
        f"repetition {row.get('task_repetition_level', '')}",
        f"creativity {row.get('creativity_requirement', '')}",
        f"physical {row.get('physical_labor_level', '')}",
        f"analysis {row.get('analytical_complexity', '')}",
        f"social {row.get('social_interaction_level', '')}",
        f"skills {row.get('skill_complexity_score', '')}",
        f"communication {row.get('communication_requirement', '')}",
        f"domain {row.get('domain_specific_knowledge_level', '')}",
        f"team {row.get('team_collaboration_level', '')}",
    ]
    return normalize_text(" ".join(map(str, pieces)))


def build_resume_text(row: pd.Series) -> str:
    """Concatenate resume fields into a single TF-IDF-friendly string."""
    pieces = [
        row.get("career_objective", ""),
        " ".join(parse_listish(row.get("skills"))),
        " ".join(parse_listish(row.get("related_skils_in_job"))),
        " ".join(parse_listish(row.get("responsibilities"))),
        " ".join(parse_listish(row.get("responsibilities.1"))),
        " ".join(parse_listish(row.get("skills_required"))),
        " ".join(parse_listish(row.get("professional_company_names"))),
        " ".join(parse_listish(row.get("positions"))),
        " ".join(parse_listish(row.get("role_positions"))),
        " ".join(parse_listish(row.get("major_field_of_studies"))),
        " ".join(parse_listish(row.get("certification_skills"))),
    ]
    return normalize_text(
        " ".join(normalize_text(piece) for piece in pieces if normalize_text(piece))
    )
