from __future__ import annotations

import json
import os
import re
from urllib.parse import quote_plus
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import requests

from bootstrap import ensure_model_artifacts


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "ml_models" / "model.pkl"
CANONICAL_MODEL_PATH = BASE_DIR / "ml_models" / "automation_model.pkl"
COURSES_PATH = BASE_DIR / "ml_models" / "courses.pkl"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.lower() == "nan" else text


def _safe_load_bundle() -> dict[str, Any]:
    model_path = CANONICAL_MODEL_PATH if CANONICAL_MODEL_PATH.exists() else MODEL_PATH
    if model_path.exists():
        return joblib.load(model_path)
    return {}


def _safe_load_courses() -> dict[str, list[dict[str, Any]]]:
    if COURSES_PATH.exists():
        return joblib.load(COURSES_PATH)
    return {}


@lru_cache(maxsize=1)
def load_artifacts() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if not CANONICAL_MODEL_PATH.exists() or not COURSES_PATH.exists():
        ensure_model_artifacts()
    return _safe_load_bundle(), _safe_load_courses()


def _split_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text.lower())
    stop_words = {
        "with",
        "from",
        "that",
        "this",
        "your",
        "have",
        "will",
        "into",
        "about",
        "for",
        "and",
        "the",
        "are",
        "our",
        "you",
        "role",
        "work",
        "team",
        "data",
        "skills",
        "career",
        "resume",
    }
    return [token for token in tokens if token not in stop_words]


def _format_top_skills(keywords: list[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for keyword in keywords:
        normalized = keyword.replace("_", " ").strip().title()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
        if len(output) >= limit:
            break
    return output


def _normalise_skill(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _extract_skills(text: str, extra_skills: list[str] | None = None) -> list[str]:
    """Extract repeatable, user-reviewable skill phrases without an external service."""
    known = {
        "python", "sql", "excel", "power bi", "tableau", "javascript", "typescript", "java", "c++",
        "machine learning", "data analysis", "data visualization", "project management", "agile", "scrum",
        "communication", "leadership", "stakeholder management", "customer service", "sales", "marketing",
        "cloud", "aws", "azure", "git", "docker", "flask", "react", "html", "css", "statistics",
        "research", "accounting", "financial analysis", "problem solving", "teamwork",
    }
    text_lower = text.lower()
    found = {skill for skill in known if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", text_lower)}
    found.update(_normalise_skill(skill) for skill in (extra_skills or []) if _normalise_skill(skill))
    return sorted(found)


def _resume_evidence(resume_text: str, skills: list[str]) -> list[dict[str, str]]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", resume_text)
    evidence: list[dict[str, str]] = []
    for skill in skills:
        context = next((sentence.strip() for sentence in sentences if skill.lower() in sentence.lower()), "")
        if context:
            evidence.append({"skill": skill, "context": context[:280]})
    return evidence


def build_jd_match(resume_text: str, job_description: str, confirmed_skills: list[str] | None = None) -> dict[str, Any]:
    resume_skills = _extract_skills(resume_text, confirmed_skills)
    jd_skills = _extract_skills(job_description)
    matched = sorted(set(resume_skills) & set(jd_skills))
    missing = sorted(set(jd_skills) - set(resume_skills))
    return {
        "resume_skills": resume_skills,
        "job_skills": jd_skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "match_percent": round(100 * len(matched) / len(jd_skills)) if jd_skills else 0,
        "evidence": _resume_evidence(resume_text, matched),
        "action_plan": [
            f"Add a truthful, outcome-focused bullet showing {skill.title()} where you have relevant experience."
            for skill in missing[:4]
        ] or ["Your identified skills overlap with the job description; tailor your strongest resume bullets to the job's wording."],
    }


def _score_risk(model_bundle: dict[str, Any], resume_text: str) -> float:
    risk_pipeline = model_bundle.get("risk_pipeline")
    if risk_pipeline is not None:
        raw_score = float(risk_pipeline.predict([resume_text])[0])
        return float(np.clip(raw_score, 0.0, 1.0))
    vectorizer = model_bundle.get("vectorizer")
    risk_model = model_bundle.get("risk_model")
    if vectorizer is None or risk_model is None:
        return 0.5
    vector = vectorizer.transform([resume_text])
    raw_score = float(risk_model.predict(vector)[0])
    return float(np.clip(raw_score, 0.0, 1.0))


def _top_matches(model_bundle: dict[str, Any], resume_text: str, limit: int = 5) -> list[dict[str, Any]]:
    vectorizer = model_bundle.get("vectorizer")
    job_vectors = model_bundle.get("job_vectors")
    job_profiles = model_bundle.get("job_profiles", [])
    if vectorizer is None or job_vectors is None or not job_profiles:
        return []

    resume_vector = vectorizer.transform([resume_text])
    similarities = (job_vectors @ resume_vector.T).toarray().ravel()
    ranked_indices = np.argsort(similarities)[::-1][:limit]

    matches: list[dict[str, Any]] = []
    for index in ranked_indices:
        profile = dict(job_profiles[index])
        profile["similarity"] = float(similarities[index])
        matches.append(profile)
    return matches


def _skill_clusters(model_bundle: dict[str, Any], resume_text: str, limit: int = 4) -> list[dict[str, Any]]:
    vectorizer = model_bundle.get("vectorizer")
    cluster_vectors = model_bundle.get("cluster_vectors")
    cluster_profiles = model_bundle.get("cluster_profiles", [])
    if vectorizer is None or cluster_vectors is None or not cluster_profiles:
        return []

    resume_vector = vectorizer.transform([resume_text])
    similarities = (cluster_vectors @ resume_vector.T).toarray().ravel()
    ranked_indices = np.argsort(similarities)[::-1][:limit]

    clusters: list[dict[str, Any]] = []
    for index in ranked_indices:
        profile = dict(cluster_profiles[index])
        profile["similarity"] = float(similarities[index])
        clusters.append(profile)
    return clusters


def _generate_roadmap(model_bundle: dict[str, Any], resume_text: str, matches: list[dict[str, Any]], focus_skills: list[str] | None = None) -> list[dict[str, Any]]:
    courses_index = model_bundle.get("courses", {})
    keywords = [*(_normalise_skill(skill).title() for skill in (focus_skills or [])), *_format_top_skills(_split_keywords(resume_text), limit=12)]
    roadmap: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for match in matches[:3]:
        for skill in match.get("skills", [])[:4]:
            normalized_skill = str(skill).strip().lower()
            for course in courses_index.get(normalized_skill, []):
                title = course.get("title") or course.get("Course Title") or course.get("Course")
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                url = course.get("url") or course.get("Course URL") or course.get("URL") or f"https://www.coursera.org/search?query={quote_plus(str(skill))}"
                roadmap.append(
                    {
                        "skill": skill,
                        "course": title,
                        "url": url,
                        "reason": course.get("short_intro") or course.get("Course Short Intro") or course.get("What you learn") or "Aligned course recommendation",
                    }
                )
                if len(roadmap) >= 6:
                    return roadmap

    for keyword in keywords:
        for course in courses_index.get(keyword.lower(), []):
            title = course.get("title") or course.get("Course Title") or course.get("Course")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            url = course.get("url") or course.get("Course URL") or course.get("URL") or f"https://www.coursera.org/search?query={quote_plus(str(keyword))}"
            roadmap.append(
                {
                    "skill": keyword,
                    "course": title,
                    "url": url,
                    "reason": course.get("short_intro") or course.get("Course Short Intro") or course.get("What you learn") or "Aligned course recommendation",
                }
            )
            if len(roadmap) >= 6:
                return roadmap

    if not roadmap:
        for skill in (focus_skills or [])[:4]:
            roadmap.append({"skill": skill.title(), "course": f"Learn {skill.title()}", "url": f"https://www.coursera.org/search?query={quote_plus(skill)}", "reason": "Direct search for this identified skill gap."})
    return roadmap


def _riasec_profile(clusters: list[dict[str, Any]], resume_text: str) -> dict[str, Any]:
    keyword_weights = {
        "Realistic": ["build", "maintain", "repair", "hands-on", "equipment", "physical", "operations"],
        "Investigative": ["analyze", "research", "model", "data", "ml", "python", "science", "sql", "statistics"],
        "Artistic": ["design", "creative", "visual", "ux", "story", "content", "brand"],
        "Social": ["support", "coach", "guide", "collaborat", "communication", "help", "training"],
        "Enterprising": ["lead", "influence", "business", "stakeholder", "sales", "strategy", "partnership"],
        "Conventional": ["process", "documentation", "organize", "compliance", "report", "workflow", "detail"],
    }

    scores = {key: 0.0 for key in keyword_weights}
    normalized_resume = resume_text.lower()

    for name, keywords in keyword_weights.items():
        for keyword in keywords:
            if keyword in normalized_resume:
                scores[name] += 1.0

    for cluster in clusters[:2]:
        for interest in cluster.get("interests", []):
            interest_name = str(interest).split("|")[0].strip()
            if interest_name in scores:
                scores[interest_name] += float(cluster.get("similarity", 0.0)) * 3.0

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return {
        "primary": ordered[0][0],
        "secondary": ordered[1][0],
        "tertiary": ordered[2][0],
        "scores": {name: round(score, 3) for name, score in ordered},
    }


def _ollama_narrative(resume_text: str, analysis: dict[str, Any]) -> str | None:
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model_name = os.environ.get("OLLAMA_MODEL", "llama3")
    prompt = f"""
You are generating a concise career intelligence narrative for Prayash.

Resume:
{resume_text}

Local ML risk score: {analysis['risk_score']:.2f}
Top matching roles: {json.dumps(analysis['top_roles'], ensure_ascii=False)}
RIASEC fit: {json.dumps(analysis['riasec'], ensure_ascii=False)}
Recommended learning roadmap: {json.dumps(analysis['roadmap'], ensure_ascii=False)}

Return a short structured response with two sections:
1. Cognitive Career Narrative
2. RIASEC Personality Fit
Keep it specific, actionable, and suitable for an executive dashboard.
""".strip()

    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.25}},
            timeout=4,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response")
    except Exception:
        return None


def _build_reasoning(
    resume_text: str,
    risk_score: float,
    risk_label: str,
    top_roles: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    roadmap: list[dict[str, Any]],
    riasec: dict[str, Any],
) -> dict[str, Any]:
    detected_skills = _format_top_skills(_split_keywords(resume_text), limit=6)
    primary_role = top_roles[0] if top_roles else {}
    primary_cluster = clusters[0] if clusters else {}

    risk_drivers: list[str] = []
    if risk_score < 0.35:
        risk_drivers.append("The resume uses role-specific language that maps to lower-risk, knowledge-heavy work.")
    elif risk_score < 0.7:
        risk_drivers.append("The profile mixes analytical signals with adjacent skills, producing a mid-band automation risk.")
    else:
        risk_drivers.append("The profile aligns with repeatable tasks that the local model treats as higher automation risk.")

    if primary_role.get("job_role"):
        risk_drivers.append(
            f"Top occupational alignment is with {primary_role['job_role']} at {round(float(primary_role.get('similarity', 0.0)) * 100)}% similarity."
        )
    if primary_cluster.get("title"):
        risk_drivers.append(
            f"Closest O*NET cluster is {primary_cluster['title']} with {round(float(primary_cluster.get('similarity', 0.0)) * 100)}% similarity."
        )

    evidence = []
    if primary_role:
        evidence.append(
            {
                "label": "Best matching role",
                "value": primary_role.get("job_role") or "Unspecified",
                "detail": f"Similarity {round(float(primary_role.get('similarity', 0.0)) * 100)}%",
            }
        )
    if primary_cluster:
        evidence.append(
            {
                "label": "Closest cluster",
                "value": primary_cluster.get("title") or "Unspecified",
                "detail": f"Similarity {round(float(primary_cluster.get('similarity', 0.0)) * 100)}%",
            }
        )
    if riasec.get("primary"):
        evidence.append(
            {
                "label": "RIASEC fit",
                "value": f"{riasec.get('primary')} / {riasec.get('secondary')}",
                "detail": "Preference profile derived from resume keywords and O*NET interests.",
            }
        )

    recommendations: list[str] = []
    for item in roadmap[:3]:
        course = item.get("course") or item.get("skill")
        if course and course not in recommendations:
            recommendations.append(str(course))

    return {
        "summary": f"{risk_label} task exposure estimate based on resume language, role similarity, and occupational cluster overlap.",
        "risk_drivers": risk_drivers,
        "evidence": evidence,
        "skills_detected": detected_skills,
        "next_steps": recommendations,
        "confidence_note": "Explainability is derived from local TF-IDF similarity and rule-based feature tracing.",
    }


def analyze_resume(resume_text: str, mode: str = "standard", job_description: str = "", confirmed_skills: list[str] | None = None) -> dict[str, Any]:
    bundle, courses = load_artifacts()
    if not bundle:
        raise RuntimeError("Model artifacts are missing. The bootstrap step could not prepare them.")

    model_bundle = dict(bundle)
    model_bundle["courses"] = courses

    cleaned_resume = _clean_text(resume_text)
    if not cleaned_resume:
        raise ValueError("Resume text is required.")

    risk_score = _score_risk(model_bundle, cleaned_resume)
    top_roles = _top_matches(model_bundle, cleaned_resume)
    clusters = _skill_clusters(model_bundle, cleaned_resume)
    jd_match = build_jd_match(cleaned_resume, job_description, confirmed_skills) if _clean_text(job_description) else None
    roadmap = _generate_roadmap(model_bundle, cleaned_resume, top_roles, jd_match["missing_skills"] if jd_match else None)
    riasec = _riasec_profile(clusters, cleaned_resume)
    reasoning = _build_reasoning(cleaned_resume, risk_score, "Low" if risk_score < 0.35 else "Moderate" if risk_score < 0.7 else "Elevated", top_roles, clusters, roadmap, riasec)
    skill_overlap = float((jd_match or {}).get("match_percent", 0)) / 100 if jd_match else min(1.0, len(_extract_skills(cleaned_resume)) / 10)
    closest_role_evidence = float(top_roles[0].get("similarity", 0.0)) if top_roles else 0.0
    resume_language = float(min(1.0, len(_split_keywords(cleaned_resume)) / 24))
    evidence_strength = np.mean([resume_language, closest_role_evidence, skill_overlap])
    confidence_score = float(np.clip(0.45 + (evidence_strength * 0.45) + (0.1 if jd_match else 0.0), 0.0, 0.95))
    metadata = model_bundle.get("metadata", {})

    analysis: dict[str, Any] = {
        "mode": mode,
        "risk_score": round(risk_score, 3),
        "risk_label": "Low" if risk_score < 0.35 else "Moderate" if risk_score < 0.7 else "Elevated",
        "task_exposure_estimate": {
            "score": round(risk_score, 3),
            "label": "Low" if risk_score < 0.35 else "Moderate" if risk_score < 0.7 else "Elevated",
            "unit": "local task exposure estimate",
        },
        "sub_scores": {
            "resume_language": round(resume_language, 3),
            "closest_role_evidence": round(closest_role_evidence, 3),
            "skill_overlap": round(skill_overlap, 3),
        },
        "confidence": {
            "score": round(confidence_score, 3),
            "label": "Higher" if confidence_score >= 0.75 else "Moderate" if confidence_score >= 0.55 else "Limited",
            "basis": "Resume language, closest role evidence, and skill overlap; job-description overlap increases evidence.",
        },
        "model_version": metadata.get("model_version", "risk-v1.0"),
        "limitations": [
            "This is a local educational estimate of task exposure, not a job-loss prediction or hiring assessment.",
            "Confidence depends on resume detail and the coverage of the occupational reference data.",
            "Role similarity and skill overlap are evidence signals, not causal forecasts.",
        ],
        "top_roles": top_roles,
        "skill_clusters": clusters,
        "roadmap": roadmap,
        "riasec": riasec,
        "reasoning": reasoning,
        "privacy": {
            "storage": "Ephemeral only",
            "resume_persistence": False,
            "database_written": False,
        },
    }
    if jd_match:
        analysis["jd_match"] = jd_match

    if mode == "advanced":
        narrative = _ollama_narrative(cleaned_resume, analysis)
        if narrative:
            analysis["cognitive_career_narrative"] = narrative
        else:
            analysis["cognitive_career_narrative"] = (
                f"Local advanced guidance is unavailable, so this is a structured local fallback. Your strongest alignment is "
                f"{top_roles[0]['job_role'] if top_roles else 'knowledge work'}; prioritize {', '.join((jd_match or {}).get('missing_skills', [])[:2]) or 'one adjacent skill'} next."
            )
    else:
        analysis["cognitive_career_narrative"] = (
            f"Local ML identifies a {analysis['risk_label'].lower()} task exposure estimate with immediate room to sharpen adjacent skills."
        )

    return analysis
