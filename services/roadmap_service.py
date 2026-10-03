"""Deterministic reskilling roadmap generator built from the skill-gap result."""

from __future__ import annotations

from typing import Any

from services.skill_gap_service import calculate_skill_gap


def generate_roadmap(user_skills: list[str], target_role: str) -> dict[str, Any]:
    gap = calculate_skill_gap(user_skills, target_role)
    missing = sorted(
        gap["missing_details"],
        key=lambda item: (item.get("learning_order", 999), -int(item.get("importance", 0) or 0)),
    )
    roadmap = []
    for index, skill in enumerate(missing, start=1):
        importance = int(skill.get("importance", 0) or 0)
        priority = "Critical" if importance >= 5 else ("High" if importance >= 4 else "Medium")
        roadmap.append({
            "step": index,
            "skill": skill.get("skill"),
            "category": skill.get("category"),
            "priority": priority,
            "estimated_weeks": int(skill.get("estimated_weeks", 0) or 0),
            "description": f"Learn {skill.get('skill')} for a {target_role} role.",
            "status": "Not Started",
        })
    return {
        "target_role": target_role,
        "current_coverage": gap["coverage"],
        "matched_skills": gap["matched_skills"],
        "roadmap": roadmap,
    }
