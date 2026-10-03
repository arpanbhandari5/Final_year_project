"""Pandas-based skill gap analysis over the career_skills dataset.

Deterministic only — no LLM decides coverage scores.
"""

from __future__ import annotations

from typing import Any

from services.career_data_service import CareerDataService

career_data = CareerDataService()


def normalize_skill(skill: str) -> str:
    return str(skill or "").strip().lower()


def calculate_skill_gap(user_skills: list[str], target_role: str) -> dict[str, Any]:
    requirements = career_data.get_role_requirements(target_role)
    if requirements.empty:
        raise ValueError(f"No career requirements found for {target_role}")

    user_skill_set = {normalize_skill(s) for s in (user_skills or []) if s}
    requirements = requirements.copy()
    requirements["matched"] = requirements["skill_norm"].isin(user_skill_set)

    matched = requirements[requirements["matched"]].sort_values("learning_order")
    missing = requirements[~requirements["matched"]].sort_values("learning_order")

    total_importance = float(requirements["importance"].sum() or 0)
    matched_importance = float(matched["importance"].sum() or 0)
    coverage = round(matched_importance / total_importance * 100, 2) if total_importance else 0.0

    return {
        "target_role": target_role,
        "coverage": coverage,
        "matched_skills": matched["skill"].tolist(),
        "missing_skills": missing["skill"].tolist(),
        "priority_skills": missing.sort_values("importance", ascending=False)["skill"].head(5).tolist(),
        "matched_details": matched.to_dict(orient="records"),
        "missing_details": missing.to_dict(orient="records"),
    }
