from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import requests

from bootstrap import ensure_model_artifacts


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "ml_models" / "model.pkl"
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
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return {}


def _safe_load_courses() -> dict[str, list[dict[str, Any]]]:
    if COURSES_PATH.exists():
        return joblib.load(COURSES_PATH)
    return {}


@lru_cache(maxsize=1)
def load_artifacts() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if not MODEL_PATH.exists() or not COURSES_PATH.exists():
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


def _score_risk(model_bundle: dict[str, Any], resume_text: str) -> float:
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


def _generate_roadmap(model_bundle: dict[str, Any], resume_text: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    courses_index = model_bundle.get("courses", {})
    keywords = _format_top_skills(_split_keywords(resume_text), limit=12)
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
                roadmap.append(
                    {
                        "skill": skill,
                        "course": title,
                        "url": course.get("url") or course.get("Course URL") or course.get("URL"),
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
            roadmap.append(
                {
                    "skill": keyword,
                    "course": title,
                    "url": course.get("url") or course.get("Course URL") or course.get("URL"),
                    "reason": course.get("short_intro") or course.get("Course Short Intro") or course.get("What you learn") or "Aligned course recommendation",
                }
            )
            if len(roadmap) >= 6:
                return roadmap

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
            timeout=45,
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
        "summary": f"{risk_label} risk based on resume language, role similarity, and occupational cluster overlap.",
        "risk_drivers": risk_drivers,
        "evidence": evidence,
        "skills_detected": detected_skills,
        "next_steps": recommendations,
        "confidence_note": "Explainability is derived from local TF-IDF similarity and rule-based feature tracing.",
    }


def analyze_resume(resume_text: str, mode: str = "standard") -> dict[str, Any]:
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
    roadmap = _generate_roadmap(model_bundle, cleaned_resume, top_roles)
    riasec = _riasec_profile(clusters, cleaned_resume)
    reasoning = _build_reasoning(cleaned_resume, risk_score, "Low" if risk_score < 0.35 else "Moderate" if risk_score < 0.7 else "Elevated", top_roles, clusters, roadmap, riasec)

    analysis: dict[str, Any] = {
        "mode": mode,
        "risk_score": round(risk_score, 3),
        "risk_label": "Low" if risk_score < 0.35 else "Moderate" if risk_score < 0.7 else "Elevated",
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

    if mode == "advanced":
        narrative = _ollama_narrative(cleaned_resume, analysis)
        if narrative:
            analysis["cognitive_career_narrative"] = narrative
        else:
            analysis["cognitive_career_narrative"] = (
                f"The resume shows strongest alignment with {top_roles[0]['job_role'] if top_roles else 'knowledge work'} roles. "
                f"Local ML places the candidate in the {analysis['risk_label'].lower()} automation band."
            )
    else:
        analysis["cognitive_career_narrative"] = (
            f"Local ML identifies a {analysis['risk_label'].lower()} automation risk profile with immediate room to sharpen adjacent skills."
        )

    return analysis


# ── Role Skills Database ──────────────────────────────────────────
_ROLE_SKILLS_DATABASE: dict[str, list[str]] = {
    "Data Scientist": ["Python", "R", "SQL", "Machine Learning", "Statistics", "Data Visualization", "Deep Learning", "Feature Engineering", "A/B Testing", "Big Data Tools", "TensorFlow", "PyTorch"],
    "Data Analyst": ["SQL", "Python", "Excel", "Data Visualization", "Statistical Analysis", "Tableau", "Power BI", "Data Cleaning", "Reporting", "Dashboarding"],
    "Software Engineer": ["Programming", "Data Structures", "Algorithms", "System Design", "Version Control", "Testing", "CI/CD", "API Design", "Problem Solving", "Object-Oriented Programming"],
    "Machine Learning Engineer": ["Python", "Machine Learning", "Deep Learning", "MLOps", "Data Engineering", "TensorFlow", "PyTorch", "Docker", "Kubernetes", "Feature Engineering", "Model Deployment"],
    "Frontend Developer": ["HTML", "CSS", "JavaScript", "React", "TypeScript", "Responsive Design", "Web Performance", "Testing", "Version Control", "REST APIs"],
    "Backend Developer": ["Python", "Node.js", "Java", "SQL", "NoSQL", "API Design", "Docker", "Cloud Services", "CI/CD", "Authentication", "Database Design"],
    "Full Stack Developer": ["JavaScript", "HTML", "CSS", "React", "Node.js", "SQL", "NoSQL", "REST APIs", "Version Control", "Docker", "Cloud Services", "Testing"],
    "DevOps Engineer": ["Linux", "Docker", "Kubernetes", "CI/CD", "Cloud Services", "Terraform", "Ansible", "Monitoring", "Scripting", "Networking", "Security", "Git"],
    "Product Manager": ["Product Strategy", "User Research", "Data Analysis", "Leadership", "Agile/Scrum", "Communication", "Roadmapping", "Stakeholder Management", "A/B Testing", "Market Analysis"],
    "UX Designer": ["User Research", "Wireframing", "Prototyping", "Figma", "Information Architecture", "Usability Testing", "Visual Design", "Interaction Design", "Design Systems"],
    "Data Engineer": ["Python", "SQL", "ETL", "Data Warehousing", "Spark", "Airflow", "Cloud Services", "NoSQL", "Docker", "Data Modeling", "Big Data Tools"],
    "AI Research Scientist": ["Python", "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "Reinforcement Learning", "PyTorch", "TensorFlow", "Research", "Mathematics", "Statistics"],
    "Business Intelligence Developer": ["SQL", "Data Warehousing", "ETL", "Tableau", "Power BI", "Data Modeling", "Reporting", "Dashboarding", "Python", "Analytics"],
    "Cybersecurity Analyst": ["Network Security", "Vulnerability Assessment", "SIEM", "Security Tools", "Incident Response", "Risk Management", "Python", "Scripting", "Compliance", "Firewalls"],
    "Cloud Architect": ["Cloud Services", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Networking", "Security", "Terraform", "Microservices", "System Design"],
    "Mobile Developer": ["Kotlin", "Swift", "React Native", "Flutter", "Mobile UI", "REST APIs", "Version Control", "App Architecture", "Testing", "Performance Optimization"],
    "Technical Writer": ["Technical Communication", "Documentation", "API Documentation", "Markdown", "Content Management", "Information Architecture", "Editing", "Research", "Subject Matter Expertise"],
    "QA Engineer": ["Testing", "Automation", "Selenium", "Test Planning", "Python", "CI/CD", "Bug Tracking", "Performance Testing", "API Testing", "Agile/Scrum"],
    "Project Manager": ["Agile/Scrum", "Project Planning", "Risk Management", "Stakeholder Management", "Budgeting", "Communication", "Leadership", "JIRA", "MS Project", "Team Management"],
    "Database Administrator": ["SQL", "Database Design", "Performance Tuning", "Backup & Recovery", "Security", "NoSQL", "Cloud Databases", "Scripting", "Monitoring", "Migration"],
}


def get_available_roles() -> list[str]:
    return sorted(_ROLE_SKILLS_DATABASE.keys())


def get_role_skills(role: str) -> list[str]:
    return _ROLE_SKILLS_DATABASE.get(role, [])


def _normalize_skill(skill: str) -> str:
    return skill.strip().lower()


def analyze_skills_gap(resume_text: str, target_role: str) -> dict[str, Any]:
    required_skills = _ROLE_SKILLS_DATABASE.get(target_role, [])
    if not required_skills:
        return {"error": f"Unknown target role: {target_role}", "available_roles": get_available_roles()}

    detected_keywords = set(_split_keywords(resume_text))
    detected_skills = set()
    for kw in detected_keywords:
        normalized = _normalize_skill(kw)
        detected_skills.add(normalized)
        detected_skills.add(kw.title())
        detected_skills.add(kw.upper())

    matched_skills: list[str] = []
    missing_skills: list[str] = []
    for skill in required_skills:
        skill_normalized = _normalize_skill(skill)
        skill_variations = {skill_normalized, skill.lower(), skill.title()}
        if any(v in detected_keywords or v in detected_skills for v in skill_variations):
            matched_skills.append(skill)
        else:
            missing_skills.append(skill)

    match_percentage = round((len(matched_skills) / len(required_skills)) * 100, 1) if required_skills else 0.0

    _HIGH_PRIORITY = {
        "python", "sql", "programming", "data structures", "algorithms",
        "version control", "testing", "html", "css", "javascript",
        "api design", "problem solving", "object-oriented programming",
        "machine learning", "deep learning", "statistics", "docker", "linux", "git",
    }
    _MEDIUM_PRIORITY = {
        "system design", "ci/cd", "cloud services", "no sql", "nosql",
        "authentication", "database design", "react", "node.js",
        "java", "typescript", "kubernetes", "terraform",
        "data visualization", "etl", "data warehousing",
        "spark", "airflow", "figma", "user research",
        "agile/scrum", "project planning",
    }

    high_priority: list[str] = []
    medium_priority: list[str] = []
    low_priority: list[str] = []
    for skill in missing_skills:
        sl = skill.lower().strip()
        if sl in _HIGH_PRIORITY:
            high_priority.append(skill)
        elif sl in _MEDIUM_PRIORITY:
            medium_priority.append(skill)
        else:
            low_priority.append(skill)

    return {
        "target_role": target_role,
        "total_required": len(required_skills),
        "matched_skills": sorted(matched_skills),
        "matched_count": len(matched_skills),
        "missing_skills": sorted(missing_skills),
        "missing_count": len(missing_skills),
        "match_percentage": match_percentage,
        "high_priority": sorted(high_priority),
        "medium_priority": sorted(medium_priority),
        "low_priority": sorted(low_priority),
    }


def suggest_career_paths(resume_text: str) -> list[dict[str, Any]]:
    if not resume_text or len(resume_text.strip()) < 10:
        return []
    lower_text = resume_text.lower()
    import re as _re
    words_in_text = set(_re.findall(r"[a-z][a-z0-9+#.]+", lower_text))

    _CAREER_PATH_MAPPING: dict[str, dict[str, Any]] = {
        "Software Engineer": {"keywords": ["python", "java", "javascript", "c++", "programming", "algorithms", "data structures", "api", "backend", "frontend"], "category": "Software Development", "growing": True, "avg_salary": "$100K-$150K", "demand": "High", "description": "Design, build, and maintain software systems", "skills_needed": ["Programming", "Data Structures", "Algorithms", "System Design", "Version Control"]},
        "Data Scientist": {"keywords": ["python", "machine learning", "deep learning", "statistics", "sql", "tensorflow", "pytorch", "data", "nlp", "analytics", "ai"], "category": "Data & Analytics", "growing": True, "avg_salary": "$120K-$160K", "demand": "High", "description": "Use statistical methods and ML to extract insights from data", "skills_needed": ["Python", "Machine Learning", "SQL", "Statistics", "Data Visualization"]},
        "Data Analyst": {"keywords": ["sql", "excel", "tableau", "power bi", "analytics", "data", "python", "statistics", "reporting", "dashboard"], "category": "Data & Analytics", "growing": True, "avg_salary": "$65K-$95K", "demand": "High", "description": "Transform raw data into actionable business insights", "skills_needed": ["SQL", "Excel", "Data Visualization", "Statistics", "Python"]},
        "Frontend Developer": {"keywords": ["html", "css", "javascript", "typescript", "react", "angular", "vue", "frontend", "web", "ui", "responsive"], "category": "Software Development", "growing": True, "avg_salary": "$90K-$135K", "demand": "High", "description": "Create responsive, accessible user interfaces", "skills_needed": ["HTML", "CSS", "JavaScript", "React", "TypeScript"]},
        "Backend Developer": {"keywords": ["python", "java", "node.js", "sql", "nosql", "api", "docker", "backend", "server", "database", "rest"], "category": "Software Development", "growing": True, "avg_salary": "$95K-$140K", "demand": "High", "description": "Build scalable server-side logic, APIs, and databases", "skills_needed": ["Python", "Java", "SQL", "API Design", "Docker"]},
        "Full Stack Developer": {"keywords": ["javascript", "html", "css", "react", "node.js", "python", "sql", "mongodb", "full stack", "web", "api"], "category": "Software Development", "growing": True, "avg_salary": "$100K-$150K", "demand": "High", "description": "Work across both frontend and backend layers", "skills_needed": ["JavaScript", "HTML", "CSS", "React", "Node.js"]},
        "DevOps Engineer": {"keywords": ["docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "linux", "terraform", "ansible", "jenkins", "cloud", "devops"], "category": "Infrastructure & Cloud", "growing": True, "avg_salary": "$110K-$160K", "demand": "High", "description": "Bridge development and operations with automation", "skills_needed": ["Docker", "Kubernetes", "CI/CD", "Cloud", "Linux"]},
        "Machine Learning Engineer": {"keywords": ["python", "machine learning", "deep learning", "tensorflow", "pytorch", "mlops", "docker", "kubernetes", "data", "model", "deployment"], "category": "Data & Analytics", "growing": True, "avg_salary": "$130K-$180K", "demand": "Very High", "description": "Build and deploy ML models into production", "skills_needed": ["Python", "Machine Learning", "Deep Learning", "MLOps", "Docker"]},
    }

    scored: list[dict[str, Any]] = []
    for role, info in _CAREER_PATH_MAPPING.items():
        keywords = info["keywords"]
        matched_kws = [kw for kw in keywords if kw in lower_text or any(kw in w for w in words_in_text)]
        matches = len(matched_kws)
        if matches == 0:
            continue
        score = round(matches / len(keywords) * 100, 1)
        reasons = [f"Strong {kw.title()} skills detected" for kw in keywords if kw in lower_text][:6]
        missing = [kw.title() for kw in keywords if kw not in lower_text][:6]
        skills_analysis = [{"skill": skill, "status": "matched" if any(skill.lower() in kw or kw in skill.lower() for kw in matched_kws) else "missing"} for skill in info["skills_needed"]]
        scored.append({"role": role, "score": score, "category": info["category"], "growing": info["growing"], "avg_salary": info["avg_salary"], "demand": info["demand"], "description": info["description"], "skills_needed": info["skills_needed"], "matched_keywords": matches, "total_keywords": len(keywords), "reasons": reasons, "missing_for_role": missing, "skills_analysis": skills_analysis})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:8]


def generate_learning_roadmap(resume_text: str) -> list[dict[str, Any]]:
    if not resume_text or len(resume_text.strip()) < 10:
        return []
    lower_text = resume_text.lower()
    detected: list[str] = []
    skill_areas = {
        "Python": ["python", "django", "flask", "fastapi", "pandas", "numpy"],
        "JavaScript": ["javascript", "js", "node.js", "react", "angular", "vue", "typescript"],
        "Web Development": ["html", "css", "sass", "scss", "bootstrap", "tailwind", "webpack", "frontend", "backend"],
        "Data Science": ["machine learning", "deep learning", "nlp", "computer vision", "tensorflow", "pytorch", "scikit-learn", "data science"],
        "Databases": ["sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "nosql"],
        "Cloud & DevOps": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "ci/cd", "jenkins", "cloud"],
    }
    for area, keywords in skill_areas.items():
        if any(kw in lower_text for kw in keywords):
            detected.append(area)
    if not detected:
        return []
    roadmap: list[dict[str, Any]] = []
    roadmap_templates = {
        "Python": {"icon": "\U0001f40d", "beginner": "Learn Python basics", "intermediate": "Master OOP, decorators, generators", "advanced": "Build projects with Django/Flask"},
        "JavaScript": {"icon": "\U0001f310", "beginner": "Learn JS fundamentals", "intermediate": "Master async JS, React", "advanced": "TypeScript, testing, architecture"},
        "Web Development": {"icon": "\U0001f578\ufe0f", "beginner": "HTML5, CSS3, responsive design", "intermediate": "Frontend frameworks", "advanced": "Full-stack apps, PWAs"},
        "Data Science": {"icon": "\U0001f4ca", "beginner": "Python for data analysis", "intermediate": "ML with scikit-learn", "advanced": "Deep learning, NLP"},
        "Databases": {"icon": "\U0001f5c4\ufe0f", "beginner": "SQL fundamentals", "intermediate": "Database design, ORM", "advanced": "NoSQL, optimization"},
        "Cloud & DevOps": {"icon": "\u2601\ufe0f", "beginner": "Linux, Git", "intermediate": "Docker, CI/CD", "advanced": "Kubernetes, cloud architecture"},
    }
    seen_areas: set[str] = set()
    for area in detected:
        if area in seen_areas or area not in roadmap_templates:
            continue
        seen_areas.add(area)
        tmpl = roadmap_templates[area]
        roadmap.append({"area": area, "icon": tmpl["icon"], "stages": [
            {"level": "Beginner", "description": tmpl["beginner"], "duration": "2-4 weeks", "phase": 1},
            {"level": "Intermediate", "description": tmpl["intermediate"], "duration": "4-8 weeks", "phase": 2},
            {"level": "Advanced", "description": tmpl["advanced"], "duration": "8-12 weeks", "phase": 3},
            {"level": "Practical Project", "description": f"Build a portfolio project with {area}", "duration": "2-4 weeks", "phase": 4},
            {"level": "Job Ready", "description": f"Polish portfolio and apply for {area} roles", "duration": "1-2 weeks", "phase": 5},
        ]})
    return roadmap