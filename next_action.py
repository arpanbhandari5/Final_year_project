"""Rank exactly one next career-development action from goal + evidence."""

from __future__ import annotations

from typing import Any

from risk_assessor import analyze_skills_gap, get_available_roles

IMMEDIATE_GOALS = (
    "Explore careers",
    "Improve my resume",
    "Prepare for a target role",
    "Learn missing skills",
    "Apply for jobs",
)

SKILL_STATUSES = (
    "confirmed",
    "needs_review",
    "not_relevant",
    "missing_evidence",
    "user-added",
)


def map_occupation_to_gap_role(title: str) -> str:
    roles = get_available_roles()
    lowered = (title or "").strip().lower()
    if not lowered:
        return "Software Engineer"
    for role in roles:
        if role.lower() in lowered or lowered in role.lower():
            return role
    tokens = set(lowered.replace("/", " ").replace("-", " ").split())
    best = "Software Engineer"
    best_n = 0
    for role in roles:
        overlap = len(tokens & set(role.lower().split()))
        if overlap > best_n:
            best, best_n = role, overlap
    return best


def _skill_names(skills: list[dict[str, Any]]) -> list[str]:
    names = []
    for item in skills:
        status = str(item.get("status") or "needs_review")
        if status in {"not_relevant"}:
            continue
        name = str(item.get("skill") or "").strip()
        if name:
            names.append(name)
    return names


def recommend_next_action(
    *,
    goal: dict[str, Any] | None,
    skills: list[dict[str, Any]],
) -> dict[str, Any]:
    if not goal or not str(goal.get("target_role") or "").strip():
        return {
            "action_type": "set_goal",
            "title": "Choose a target occupation",
            "description": "Set a supported occupation and weekly learning time so recommendations can be specific.",
            "source_type": "career_goal",
            "source_id": "goal",
            "gap": None,
        }
    if not skills:
        return {
            "action_type": "add_evidence",
            "title": "Add resume evidence",
            "description": "Confirm at least one skill with an evidence excerpt from your resume.",
            "source_type": "evidence",
            "source_id": "empty",
            "gap": None,
        }

    names = _skill_names(skills)
    review = [item for item in skills if str(item.get("status") or "") == "needs_review"]
    missing_ev = [item for item in skills if str(item.get("status") or "") == "missing_evidence"]
    immediate = str(goal.get("immediate_goal") or "")
    hours = goal.get("time_per_week")
    short_week = isinstance(hours, (int, float)) and float(hours) < 5

    if review:
        skill = str(review[0].get("skill") or "this skill")
        return {
            "action_type": "review_evidence",
            "title": f"Review your {skill} evidence",
            "description": "Confirm, edit, or mark this item not relevant so the next recommendation can use it.",
            "source_type": "evidence",
            "source_id": str(review[0].get("id") or ""),
            "gap": {"needs_review": [skill], "strong_evidence": [], "not_evidenced": []},
        }
    if missing_ev:
        skill = str(missing_ev[0].get("skill") or "a listed skill")
        return {
            "action_type": "add_evidence",
            "title": f"Add evidence for {skill}",
            "description": "Attach a short excerpt from your resume that shows this skill.",
            "source_type": "evidence",
            "source_id": str(missing_ev[0].get("id") or ""),
            "gap": {"needs_review": [], "strong_evidence": names, "not_evidenced": [skill]},
        }

    role = map_occupation_to_gap_role(str(goal.get("target_role") or ""))
    proxy = " ".join(f"{item.get('skill', '')} {item.get('evidence_span', '')}" for item in skills)
    gap = analyze_skills_gap(proxy if len(proxy.strip()) >= 20 else (proxy + " experience skills"), role)
    missing = []
    matched = []
    if "error" not in gap:
        missing = list(gap.get("missing_skills") or [])
        matched = list(gap.get("matched_skills") or [])
    summary = {
        "strong_evidence": matched[:8],
        "needs_review": [str(item.get("skill")) for item in review],
        "not_evidenced": missing[:8],
        "mapped_role": role,
    }

    if immediate == "Improve my resume":
        return {
            "action_type": "update_resume",
            "title": "Update your resume summary",
            "description": "Rewrite the opening summary so it names the target occupation and one evidenced skill.",
            "source_type": "career_goal",
            "source_id": "resume_summary",
            "gap": summary,
        }
    if immediate == "Apply for jobs":
        return {
            "action_type": "paste_job",
            "title": "Paste a target job description",
            "description": "Save one job posting you care about. Application tracking is not part of this step.",
            "source_type": "career_goal",
            "source_id": "job_paste",
            "gap": summary,
        }
    if missing:
        skill = missing[0]
        duration = "a 2-hour starter exercise" if short_week else "the first focused project"
        return {
            "action_type": "learn_skill",
            "title": f"Build one small {skill} project",
            "description": f"This is the highest-priority missing skill for {role}. Use {duration} this week, then mark the action complete.",
            "source_type": "skill_gap",
            "source_id": skill,
            "gap": summary,
        }
    return {
        "action_type": "explore",
        "title": "Complete the first course in your learning path",
        "description": f"Evidence already covers the listed {role} skills. Take one structured next course, then re-check this workspace.",
        "source_type": "skill_gap",
        "source_id": role,
        "gap": summary,
    }
