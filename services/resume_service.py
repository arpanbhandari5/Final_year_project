"""
Prayash — Resume / Career Services
===================================
Rule-based career intelligence used by the assistant when no LLM is
available (or as deterministic building blocks that the LLM can enrich).

The heart of this module is ``rule_based_career_answer`` — the fallback
chat brain that was previously inlined in ``app.py``. Keeping it here means
the legacy floating widget and the new ChatGPT-style page share ONE
implementation instead of two divergent copies.

Career tool functions (ATS scoring, skill-gap, JD comparison, interview
questions, cover letter, …) are exposed individually so the frontend can
render structured panels, and reused by the assistant for personalised,
resume-aware answers.
"""

from __future__ import annotations

import re
from typing import Any

from resume_parser import (
    analyze_resume_quality,
    extract_contact_info,
    extract_skills_from_text,
    parse_resume_enhanced,
)
from risk_assessor import (
    analyze_resume as assess_resume,
)
from risk_assessor import (
    analyze_skills_gap,
    generate_learning_roadmap,
    get_available_roles,
    suggest_career_paths,
)
from utils import clean_text

RESUME_MIN_CHARS = 20
"""Minimum resume length before we consider a document "usable"."""


# ════════════════════════════════════════════════════════════════════
# Rule-based chat brain (moved verbatim from app.py)
# ════════════════════════════════════════════════════════════════════


def rule_based_career_answer(
    question: str,
    resume_text: str = "",
    history: list[dict[str, str]] | None = None,
) -> str:
    """Rule-based fallback answer for the career chat when no LLM is available.

    Order matters — more specific topics are matched first so that, e.g.,
    "Tips for job interviews?" returns interview advice rather than the generic
    job-search answer, and "Help me plan my career path" gets dedicated
    career-path guidance instead of the same job-search text.

    When a resume (or other attached document) is available its extracted
    skills are woven into the answer so the guidance is personalised to the
    user instead of returning the same generic text every time.
    """
    q = (question or "").lower()
    resume_text = (resume_text or "").strip()

    def has_any(keywords: list[str]) -> bool:
        # Word-boundary prefix match: "skill" matches "skills" and "learning"
        # matches "learn", but "earn" never matches inside "learn" or "bearn".
        return any(re.search(rf"\b{re.escape(kw)}", q) for kw in keywords)

    # ── Resume-aware personalisation ──
    skills = extract_skills_from_text(resume_text) if len(resume_text) >= RESUME_MIN_CHARS else None
    skill_names = (skills.get("all_skills") or [])[:8] if skills else []
    top_skills = ", ".join(skill_names) if skill_names else ""

    # ── Answer from the attached document (factual Q&A) ──
    parsed_doc = None
    if len(resume_text) >= RESUME_MIN_CHARS:
        try:
            parsed_doc = parse_resume_enhanced(resume_text)
        except Exception:
            parsed_doc = None

    if parsed_doc:
        def _bullet_lines(items: list) -> str:
            lines = [str(x).strip() for x in items if str(x).strip()]
            return "\n".join(f"• {line}" for line in lines[:6])

        # Fallback for documents without clearly-separated section headers:
        # scan the raw text for the sentences that actually mention the topic.
        def _snippet(keywords: list[str], limit: int = 4) -> str:
            hits: list[str] = []
            for part in re.split(r"(?<=[.!?])\s+", resume_text):
                p = part.strip()
                if not p or len(p) < 12:
                    continue
                if p not in hits and any(re.search(rf"\b{re.escape(kw)}", p, re.IGNORECASE) for kw in keywords):
                    hits.append(p)
                if len(hits) >= limit:
                    break
            return "\n".join(f"• {h}" for h in hits)

        edu = _bullet_lines(parsed_doc.get("education") or [])
        exp = _bullet_lines(parsed_doc.get("experience") or [])
        proj = _bullet_lines(parsed_doc.get("projects") or [])
        cert = _bullet_lines(parsed_doc.get("certifications") or [])
        # Raw-text fallbacks for when section parsing came up empty
        if not edu:
            edu = _snippet(["education", "degree", "university", "college", "school", "bachelor", "master", "phd", "bsc", "msc"])
        if not exp:
            exp = _snippet(["experience", "worked", "work at", "employment", "intern", "role at", "led", "built", "developed"])
        if not proj:
            proj = _snippet(["project", "portfolio", "dashboard", "app", "platform", "system"])
        if not cert:
            cert = _snippet(["certif", "license", "course", "training", "credential"])

        # Education questions
        if has_any(["education", "degree", "university", "college", "school", "academic"]):
            if edu:
                return f"🎓 From your attached document, here's the education I found:\n{edu}\n\nWant me to suggest roles that build on this background?"
            return "Your attached document doesn't show a clear education section. Try asking about your skills or experience instead."

        # Experience / work-history questions
        if has_any(["experience", "work", "employment", "job history", "what have you done"]):
            if exp:
                return f"💼 From your attached document, here's the experience I found:\n{exp}\n\nAsk me how to position this for your next application."
            if edu:
                return f"Your attached document doesn't show a clear experience section, but your education includes:\n{edu}"
            return "Your attached document doesn't show a clear experience section. Try asking about your skills or education."

        # Projects / portfolio questions
        if has_any(["project", "portfolio", "built", "created"]):
            if proj:
                return f"🛠️ From your attached document, here are the projects I found:\n{proj}\n\nWant tips on presenting these in interviews?"
            if exp:
                return f"Your attached document doesn't list a dedicated projects section, but your experience includes:\n{exp}"
            return "Your attached document doesn't list any projects. Try asking about your skills or experience."

        # Certification questions
        if has_any(["certif", "license", "credential"]):
            if cert:
                return f"📜 From your attached document, here are the certifications I found:\n{cert}"
            return "Your attached document doesn't show any certifications. Try asking about your education or skills."

        # Profile summary / tell-me-about questions
        if has_any(["summarize", "summary", "tell me about", "overview", "what's in", "about my resume", "about this resume"]):
            parts = []
            if edu:
                parts.append(f"Education:\n{edu}")
            if exp:
                parts.append(f"Experience:\n{exp}")
            if proj:
                parts.append(f"Projects:\n{proj}")
            if top_skills:
                parts.append(f"Key skills: {top_skills}.")
            if parts:
                return "📄 Here's a summary of your attached document:\n\n" + "\n\n".join(parts) + "\n\nWhat would you like to focus on next?"
            return "I've read your attached document. Ask me about your skills, roles that fit, or what to learn next."

        # Role-fit questions — rank careers using the actual document
        if has_any(["roles fit", "which roles", "what roles", "role match", "best fit", "fit my profile", "suitable role", "career options"]):
            try:
                paths = suggest_career_paths(resume_text)[:5]
            except Exception:
                paths = []
            if paths:
                lines = [f"• {p.get('role')} — {p.get('score', 0):.0f}% match" for p in paths]
                return ("🎯 Based on your attached document, here are the roles that fit your profile:\n"
                        + "\n".join(lines)
                        + (f"\n\nTop skills driving these matches: {top_skills}." if top_skills else "")
                        + "\n\nAsk me for a learning roadmap toward any of these.")
            if top_skills:
                return f"Based on your attached document, your strongest skills are {top_skills}. Tell me your target role and I'll suggest how to position yourself."

    if has_any(["interview", "mock", "crack", "behavioral"]):
        if top_skills:
            return (
                f"Great — to prep for interviews with your profile ({top_skills}): "
                "1) Review common questions for your target roles, "
                "2) Prepare STAR-format stories that showcase those exact skills, "
                "3) Practice technical questions with LeetCode or HackerRank, "
                "4) Research each company's culture and recent news, "
                "5) Run mock interviews with friends or platforms like Pramp, "
                "6) Prepare thoughtful questions to ask the interviewer."
            )
        return (
            "To prepare for interviews: 1) Review common questions for your target role, "
            "2) Prepare STAR-format stories from your experience, "
            "3) Practice technical questions with platforms like LeetCode or HackerRank, "
            "4) Research the company's culture and recent news, "
            "5) Do mock interviews with friends or platforms like Pramp, "
            "6) Prepare thoughtful questions to ask the interviewer."
        )
    if has_any(["salary", "pay", "earn", "compensation", "negotiate"]):
        if top_skills:
            return (
                f"For roles that use {top_skills}, salary ranges vary by location, "
                "experience, and industry. Use Glassdoor, Levels.fyi, and LinkedIn Salary "
                "to benchmark market rates for your target titles. Negotiate total "
                "compensation — base salary, equity, bonus, and benefits — not just the number."
            )
        return (
            "Salary ranges vary by location, experience, and industry. "
            "Use sites like Glassdoor, Levels.fyi, and LinkedIn Salary to research "
            "market rates for your target roles. Consider total compensation including "
            "benefits, equity, and bonuses."
        )
    if has_any(["resume", "cv", "ats", "achievement"]):
        if top_skills:
            return (
                f"To strengthen your resume around {top_skills}: 1) Add specific, "
                "quantifiable achievements that prove those skills, "
                "2) Mirror the keywords from target job descriptions, "
                "3) Put the strongest skills in a clear professional summary, "
                "4) Keep the layout clean and ATS-friendly (PDF recommended), "
                "5) Make sure your contact info (email, LinkedIn) is visible."
            )
        return (
            "To improve your resume: 1) Add specific, quantifiable achievements, "
            "2) Use keywords from target job descriptions, "
            "3) Include a professional summary section, "
            "4) Keep your format clean and ATS-friendly (PDF recommended), "
            "5) Ensure your contact info (email, LinkedIn) is clearly visible."
        )
    if has_any(["career", "path", "roadmap", "growth", "goal"]):
        if top_skills:
            return (
                f"Based on your skills ({top_skills}), here's a career map: "
                "1) Compare your skills against job postings to pick 2-3 target roles, "
                "2) List the skills each role asks for that you don't have yet, "
                "3) Follow a learning roadmap to close the biggest gaps first, "
                "4) Set 3-month and 12-month milestones with measurable outcomes, "
                "5) Re-check your progress after each milestone and adjust. "
                "Want me to suggest courses or roles to explore next?"
            )
        return (
            "Let's map out your career path: 1) Review the top role matches from your "
            "analysis report to see where your profile fits today, "
            "2) Identify the skills you'll need for your target role, "
            "3) Follow the learning roadmap in your report to close skill gaps, "
            "4) Set 3-month and 12-month goals with measurable milestones, "
            "5) Re-run your analysis after each milestone to track progress. "
            "Want me to suggest specific courses or roles to explore?"
        )
    if has_any(["job", "apply", "position", "hiring", "search", "role"]):
        if top_skills:
            return (
                f"For your job search, lead with your strongest skills ({top_skills}). "
                "Use them as search keywords for alerts and applications, tailor your "
                "resume summary to the target role, and track repeated requirements "
                "across 10 recent postings before you apply."
            )
        return (
            "For job searching, use your top role matches from the analysis as search keywords. "
            "Tailor your resume summary to highlight the skills most relevant to your target role. "
            "Consider setting up job alerts for your strongest matching positions."
        )
    if has_any(["skill", "learn", "study", "course", "improve"]):
        if top_skills:
            return (
                f"You already have {top_skills}. To grow further: 1) Compare a current "
                "job posting in your target field against these skills and note the gaps, "
                "2) Pick one missing skill and complete a short course on it this month, "
                "3) Practice with small projects so the skill sticks, "
                "4) Add the new skill to your resume once you've used it. "
                "Attach your resume and ask me which skill to prioritize next."
            )
        return (
            "Based on your resume analysis, I recommend focusing on skill development. "
            "Check the learning roadmap in your analysis report for personalized course recommendations. "
            "Start with the top suggested Coursera courses for your skill gaps."
        )
    if has_any(["hello", "hi", "hey", "help", "about"]):
        return (
            "Hi! I'm your AI career assistant. I can help with:\n"
            "• Skill development and learning recommendations\n"
            "• Job search strategies and career advice\n"
            "• Resume improvement tips\n"
            "• Interview preparation\n"
            "• Salary and compensation questions\n"
            "📎 Tip: click the paperclip to attach your resume (PDF, DOCX, or TXT) "
            "so my answers are personalized to your profile.\n"
            "What would you like to know?"
        )
    if top_skills:
        return (
            f"That's a good question. Looking at your profile, I can see skills like "
            f"{top_skills}. If you tell me your target role, I can suggest which of these "
            "to highlight and which to learn next. Try asking: 'What roles fit my skills?' "
            "or 'What should I learn next for a specific career?'"
        )
    return (
        "That's a great question! For more personalized advice, click the 📎 paperclip "
        "to attach your resume — I'll tailor my guidance to your skills and profile. "
        "You can also run a resume analysis first for a full role match and learning roadmap."
    )


# ════════════════════════════════════════════════════════════════════
# Career intelligence tools (deterministic, LLM-independent)
# ════════════════════════════════════════════════════════════════════

_ATS_ACTION_VERBS = {
    "led", "built", "created", "developed", "designed", "implemented", "managed",
    "launched", "increased", "reduced", "improved", "delivered", "achieved",
    "drove", "optimized", "optimised", "coordinated", "mentored", "spearheaded",
    "negotiated", "automated", "streamlined", "grew", "saved", "produced",
}


def _extract_skills_safe(resume_text: str) -> dict[str, Any]:
    """Extract skills without raising on malformed input."""
    try:
        return extract_skills_from_text(resume_text)
    except Exception:
        return {"all_skills": [], "by_category": {}, "count": 0, "categories_found": 0}


def compute_ats_score(resume_text: str) -> dict[str, Any]:
    """Heuristic ATS-compatibility score (0-100) with a checklist.

    Checks the dimensions ATS + recruiters actually scan for: contact info,
    required sections, keyword density, action verbs, quantified results,
    formatting friendliness and overall length.
    """
    text = clean_text(resume_text)
    score = 0
    checklist: list[dict[str, Any]] = []
    parsed = parse_resume_enhanced(text) if len(text) >= RESUME_MIN_CHARS else {}
    contact = extract_contact_info(text)
    skills = _extract_skills_safe(text)
    skill_list = skills.get("all_skills") or []

    def add(label: str, ok: bool, detail: str, points: int) -> None:
        nonlocal score
        if ok:
            score += points
        checklist.append({"label": label, "passed": ok, "detail": detail, "points": points if ok else 0})

    words = len(text.split())
    has_email = bool(contact.get("email"))
    has_phone = bool(contact.get("phone"))

    add("Contact info", has_email, "Email found" if has_email else "No email detected", 10)
    add("Phone number", has_phone, "Phone found" if has_phone else "No phone detected", 5)

    sections = [s.strip().lower() for s in (parsed.get("sections_found") or [])]
    for name, pts in [("summary", 10), ("experience", 15), ("education", 10), ("skills", 10)]:
        add(f"{name.title()} section", any(name in s for s in sections) or name in str(sections).lower(), f"'{name}' section detected" if (name in str(sections).lower()) else f"No '{name}' section found", pts)

    keyword_count = len(skill_list)
    add("Skill keywords", keyword_count >= 5, f"{keyword_count} skills detected", 10)
    add("Keyword density", keyword_count >= 1 and words > 30, f"{words} words total", 5)

    action_verb_hits = [v for v in _ATS_ACTION_VERBS if re.search(rf"\b{v}\w*\b", text, re.IGNORECASE)]
    add("Action verbs", len(action_verb_hits) >= 3, f"{len(action_verb_hits)} action verbs", 10)

    quantified = bool(re.search(r"\b\d{1,3}(?:[%,kK]|x)\b|\b\d{2,4}\b", text))
    add("Quantified results", quantified, "Numbers/metrics present" if quantified else "No metrics found", 5)

    # Length / formatting
    add("Length (200+ words)", words >= 200, f"{words} words", 5)
    add("No excessive whitespace", "\n\n\n" not in text, "Formatting looks clean", 5)

    # Files/scannable sections bonus
    add("Certifications", bool(parsed.get("certifications")), "Certifications found", 5)
    add("Projects", bool(parsed.get("projects")), "Projects found", 5)

    score = min(100, score)
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    suggestions = [
        item["detail"] for item in checklist if not item["passed"]
    ]
    return {
        "score": score,
        "grade": grade,
        "checklist": checklist,
        "suggestions": suggestions[:6],
        "contact": contact,
        "word_count": words,
    }


def skill_gap_analysis(resume_text: str, target_role: str) -> dict[str, Any]:
    """Compare the resume's skills against a target role's requirements."""
    if not target_role:
        return {"error": "A target role is required.", "available_roles": get_available_roles()}
    return analyze_skills_gap(resume_text, target_role)


def compare_with_job_description(resume_text: str, jd_text: str) -> dict[str, Any]:
    """Keyword-level comparison of a resume against a job description.

    Returns the matched skills, missing keywords, extras, and an overall
    match percentage — the backbone of the "compare resume with JD" feature.
    """
    resume_skills = set(s.lower() for s in (_extract_skills_safe(resume_text).get("all_skills") or []))
    jd_skills = set(s.lower() for s in (_extract_skills_safe(jd_text).get("all_skills") or []))

    # Also treat tokens (>=4 chars) shared between the two as keyword matches
    def tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z][a-z0-9+#.-]{3,}", text.lower()))

    resume_tokens = tokens(resume_text)
    jd_tokens = tokens(jd_text)

    matched = sorted(s for s in jd_skills if s in resume_skills)
    missing = sorted(s for s in jd_skills if s not in resume_skills)
    extra = sorted(s for s in resume_skills if s not in jd_skills)

    # Token-level overlap (excluding common words) for the percentage
    stop = {"with", "from", "that", "this", "your", "have", "will", "into", "about", "for", "and", "the", "are", "our", "you", "role", "work", "team"}
    shared = sorted(jd_tokens & resume_tokens - stop)
    percentage = round((len(matched) / len(jd_skills)) * 100, 1) if jd_skills else round((len(shared) / max(1, len(jd_tokens - stop))) * 100, 1)

    return {
        "match_percentage": percentage,
        "matched_skills": matched,
        "matched_count": len(matched),
        "missing_keywords": missing,
        "missing_count": len(missing),
        "extra_skills": extra[:15],
        "shared_keywords": shared[:25],
        "jd_keyword_count": len(jd_skills),
    }


def career_recommendations(resume_text: str) -> dict[str, Any]:
    """Career-path suggestions based on detected skills."""
    try:
        paths = suggest_career_paths(resume_text)
    except Exception:
        paths = []
    return {"paths": paths[:6], "total": len(paths)}


def learning_roadmap(resume_text: str) -> dict[str, Any]:
    """Generate a personalised learning roadmap."""
    try:
        roadmap = generate_learning_roadmap(resume_text)
    except Exception:
        roadmap = []
    total_weeks = sum(
        int(str(s.get("duration", "0")).split("-")[0] or "0")
        for area in roadmap for s in area.get("stages", [])
    )
    return {"roadmap": roadmap, "areas": len(roadmap), "total_weeks": total_weeks}


def interview_questions(resume_text: str) -> dict[str, Any]:
    """Generate role-relevant interview questions from the resume's skills."""
    skills = _extract_skills_safe(resume_text)
    skill_list = (skills.get("all_skills") or [])[:8]
    paths = career_recommendations(resume_text).get("paths", [])
    top_role = paths[0].get("role", "your target role") if paths else "your target role"

    general = [
        "Tell me about yourself and your background.",
        "Why are you interested in this role?",
        "Walk me through a project you are most proud of.",
        "Describe a time you faced a challenge and how you overcame it (STAR).",
        "Where do you see yourself in 3-5 years?",
    ]
    technical = [f"Explain how you have used {s} in a real project." for s in skill_list[:4]]
    role_specific = [
        f"What do you think are the most important skills for a {top_role}?",
        "How do you stay current with trends in your field?",
    ]
    return {
        "target_role": top_role,
        "general": general,
        "technical": technical,
        "role_specific": role_specific,
        "skills": skill_list,
    }


def cover_letter(resume_text: str, job_title: str = "", company: str = "") -> dict[str, Any]:
    """Draft a cover letter template grounded in the resume's content."""
    skills = _extract_skills_safe(resume_text)
    skill_list = (skills.get("all_skills") or [])[:5]
    contact = extract_contact_info(resume_text)
    name = contact.get("name") or "Your Name"
    role = job_title or "the position"
    org = company or "your company"
    skill_line = ", ".join(skill_list) if skill_list else "relevant skills"

    body = (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my strong interest in {role} at {org}. "
        f"With experience in {skill_line}, I believe I can contribute to your team from day one.\n\n"
        f"Throughout my work, I have focused on delivering measurable results. "
        f"I enjoy solving challenging problems, collaborating across teams, and continuously learning. "
        f"I would welcome the opportunity to bring my background to {org} and help your team succeed.\n\n"
        f"Thank you for considering my application. I look forward to the possibility of discussing "
        f"how my experience aligns with your needs.\n\n"
        f"Sincerely,\n{name}"
    )
    return {"name": name, "job_title": role, "company": org, "letter": body}


def resume_rewrite_suggestions(resume_text: str) -> dict[str, Any]:
    """Concrete rewrite advice derived from quality + ATS analysis."""
    parsed = parse_resume_enhanced(resume_text) if len(resume_text) >= RESUME_MIN_CHARS else {}
    quality = analyze_resume_quality(parsed)
    ats = compute_ats_score(resume_text)
    suggestions = list(quality.get("recommendations") or [])
    suggestions += [f"ATS: {s}" for s in ats.get("suggestions", [])]
    return {
        "quality_score": quality.get("completeness_score", 0),
        "grade": quality.get("grade", "N/A"),
        "ats_score": ats.get("score", 0),
        "strengths": (quality.get("strengths") or [])[:5],
        "suggestions": suggestions[:8],
        "missing_sections": quality.get("missing_sections", []),
    }


def salary_estimation(resume_text: str) -> dict[str, Any]:
    """Estimate salary ranges from the closest matching O*NET roles."""
    try:
        paths = suggest_career_paths(resume_text)[:3]
    except Exception:
        paths = []
    estimates = []
    for p in paths:
        estimates.append({
            "role": p.get("role"),
            "match": round(p.get("score", 0)),
            "salary_range": p.get("avg_salary") or p.get("salary") or "N/A",
            "demand": p.get("demand", "N/A"),
        })
    return {
        "estimates": estimates,
        "note": "Estimates are derived from O*NET occupation data and should be validated with local market research.",
    }


def analyze_resume_profile(resume_text: str, mode: str = "standard") -> dict[str, Any]:
    """Full resume analysis: ML risk, role matches, skills, quality, RIASEC."""
    return assess_resume(resume_text, mode=mode)


def available_roles() -> list[str]:
    """Roles the skill-gap analyser can compare against."""
    return get_available_roles()


# ════════════════════════════════════════════════════════════════════
# Markdown formatting helpers for tool results
# ════════════════════════════════════════════════════════════════════

def format_tool_result(tool: str, data: dict[str, Any]) -> str:
    """Render a structured tool result as markdown for the chat message."""
    if tool == "ats":
        return (
            f"### 📊 ATS Resume Score: **{data.get('score', 0)}/100** ({data.get('grade', '')})\n\n"
            + "\n".join(
                f"- {'✅' if c['passed'] else '❌'} **{c['label']}**: {c['detail']}"
                for c in data.get("checklist", [])
            )
        )
    if tool == "gap":
        if data.get("error"):
            return f"### 🧩 Skills Gap Analysis\n\n{data['error']}"
        return (
            f"### 🧩 Skills Gap: {data.get('target_role')}\n\n"
            f"**Match: {data.get('match_percentage', 0)}%** "
            f"({data.get('matched_count', 0)}/{data.get('total_required', 0)} skills)\n\n"
            f"**Matched:** {', '.join(data.get('matched_skills', [])) or 'none'}\n\n"
            f"**Missing:** {', '.join(data.get('missing_skills', [])) or 'none'}\n\n"
            f"**Recommended learning:**\n"
            + "\n".join(f"- {r.get('skill', r)}: {r.get('suggestion', '')}" for r in (data.get('recommendations') or []))
        )
    if tool == "compare":
        return (
            f"### ⚖️ Resume vs Job Description: **{data.get('match_percentage', 0)}% match**\n\n"
            f"**Matched skills:** {', '.join(data.get('matched_skills', [])) or 'none'}\n\n"
            f"**Missing keywords:** {', '.join(data.get('missing_keywords', [])) or 'none'}\n\n"
            f"**Skills you bring beyond the JD:** {', '.join(data.get('extra_skills', [])[:10]) or 'none'}"
        )
    if tool == "interview":
        q = data
        lines = []
        lines.append(f"### 🎯 Interview Questions — {q.get('target_role')}")
        for label, group in [("General", q.get("general", [])), ("Technical", q.get("technical", [])), ("Role-specific", q.get("role_specific", []))]:
            if group:
                lines.append(f"\n**{label}:**")
                lines += [f"{i + 1}. {item}" for i, item in enumerate(group)]
        return "\n".join(lines)
    if tool == "cover-letter":
        return f"### ✉️ Cover Letter — {data.get('job_title')}\n\n```text\n{data.get('letter', '')}\n```"
    if tool == "roadmap":
        lines = ["### 🗺️ Learning Roadmap"]
        for area in data.get("roadmap", []):
            lines.append(f"\n**{area.get('area', 'Focus area')}**")
            for stage in area.get("stages", []):
                lines.append(f"- {stage.get('skill', '')} ({stage.get('duration', '')}): {stage.get('recommendation', stage.get('suggestion', ''))}")
        lines.append(f"\n_{data.get('areas', 0)} focus areas · ~{data.get('total_weeks', 0)} weeks total_")
        return "\n".join(lines)
    if tool == "recommendations":
        lines = ["### 🚀 Recommended Career Paths"]
        for p in data.get("paths", []):
            lines.append(f"- **{p.get('role')}** — {p.get('score', 0):.0f}% match · salary {p.get('avg_salary', 'N/A')} · demand {p.get('demand', 'N/A')}")
        return "\n".join(lines)
    if tool == "rewrite":
        d = data
        return (
            f"### 📝 Resume Rewrite Suggestions\n\n"
            f"**Completeness:** {d.get('quality_score', 0)}/100 · **ATS:** {d.get('ats_score', 0)}/100\n\n"
            f"**Strengths:**\n" + "\n".join(f"- {s}" for s in d.get("strengths", []))
            + "\n\n**Suggestions:**\n" + "\n".join(f"- {s}" for s in d.get("suggestions", []))
        )
    if tool == "salary":
        lines = ["### 💰 Salary Estimates (from O*NET data)"]
        for e in data.get("estimates", []):
            lines.append(f"- **{e.get('role')}** — {e.get('salary_range')} · {e.get('demand')} demand · {e.get('match')}% match")
        lines.append(f"\n_{data.get('note', '')}_")
        return "\n".join(lines)
    return f"```json\n{data}\n```"


TOOL_HELP = {
    "ats": "Run an ATS score for the attached resume.",
    "gap": "Analyze skill gaps against a target role (send target_role).",
    "compare": "Compare the attached resume with a job description (send jd_text).",
    "interview": "Generate interview questions from the attached resume.",
    "cover-letter": "Draft a cover letter (optional job_title/company).",
    "roadmap": "Build a learning roadmap for the attached resume.",
    "recommendations": "Suggest career paths for the attached resume.",
    "rewrite": "Get resume rewrite suggestions.",
    "salary": "Estimate salaries for matching roles.",
}
