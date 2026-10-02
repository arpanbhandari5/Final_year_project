from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import requests

from utils import RISK_LOW, RISK_MODERATE, clean_text, format_top_skills, risk_label, split_keywords

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "ml_models" / "model.pkl"
COURSES_PATH = BASE_DIR / "ml_models" / "courses.pkl"


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
    """Load model and course artifacts.

    Artifacts are expected to exist — callers (the startup script or
    ``ensure_model_artifacts()``) should prepare them before the server
    starts accepting requests.
    """
    return _safe_load_bundle(), _safe_load_courses()


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
    keywords = format_top_skills(split_keywords(resume_text), limit=12)
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
    label: str,
    top_roles: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    roadmap: list[dict[str, Any]],
    riasec: dict[str, Any],
) -> dict[str, Any]:
    detected_skills = format_top_skills(split_keywords(resume_text), limit=6)
    primary_role = top_roles[0] if top_roles else {}
    primary_cluster = clusters[0] if clusters else {}

    risk_drivers: list[str] = []
    if risk_score < RISK_LOW:
        risk_drivers.append("The resume uses role-specific language that maps to lower-risk, knowledge-heavy work.")
    elif risk_score < RISK_MODERATE:
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
        "summary": f"{label} risk based on resume language, role similarity, and occupational cluster overlap.",
        "risk_drivers": risk_drivers,
        "evidence": evidence,
        "skills_detected": detected_skills,
        "next_steps": recommendations,
        "confidence_note": "Explainability is derived from local TF-IDF similarity and rule-based feature tracing.",
    }


# ── Role Skills Database ──────────────────────────────────────────
# Maps career roles to required skills for skill gap analysis
# Extend this dictionary to add more roles

_ROLE_SKILLS_DATABASE: dict[str, list[str]] = {
    "Data Scientist": [
        "Python", "R", "SQL", "Machine Learning", "Statistics",
        "Data Visualization", "Deep Learning", "Feature Engineering",
        "A/B Testing", "Big Data Tools", "TensorFlow", "PyTorch"
    ],
    "Data Analyst": [
        "SQL", "Python", "Excel", "Data Visualization", "Statistical Analysis",
        "Tableau", "Power BI", "Data Cleaning", "Reporting", "Dashboarding"
    ],
    "Software Engineer": [
        "Programming", "Data Structures", "Algorithms", "System Design",
        "Version Control", "Testing", "CI/CD", "API Design",
        "Problem Solving", "Object-Oriented Programming"
    ],
    "Machine Learning Engineer": [
        "Python", "Machine Learning", "Deep Learning", "MLOps",
        "Data Engineering", "TensorFlow", "PyTorch", "Docker",
        "Kubernetes", "Feature Engineering", "Model Deployment"
    ],
    "Frontend Developer": [
        "HTML", "CSS", "JavaScript", "React", "TypeScript",
        "Responsive Design", "Web Performance", "Testing",
        "Version Control", "REST APIs"
    ],
    "Backend Developer": [
        "Python", "Node.js", "Java", "SQL", "NoSQL",
        "API Design", "Docker", "Cloud Services", "CI/CD",
        "Authentication", "Database Design"
    ],
    "Full Stack Developer": [
        "JavaScript", "HTML", "CSS", "React", "Node.js",
        "SQL", "NoSQL", "REST APIs", "Version Control",
        "Docker", "Cloud Services", "Testing"
    ],
    "DevOps Engineer": [
        "Linux", "Docker", "Kubernetes", "CI/CD", "Cloud Services",
        "Terraform", "Ansible", "Monitoring", "Scripting",
        "Networking", "Security", "Git"
    ],
    "Product Manager": [
        "Product Strategy", "User Research", "Data Analysis",
        "Leadership", "Agile/Scrum", "Communication",
        "Roadmapping", "Stakeholder Management", "A/B Testing",
        "Market Analysis"
    ],
    "UX Designer": [
        "User Research", "Wireframing", "Prototyping", "Figma",
        "Information Architecture", "Usability Testing",
        "Visual Design", "Interaction Design", "Design Systems"
    ],
    "Data Engineer": [
        "Python", "SQL", "ETL", "Data Warehousing", "Spark",
        "Airflow", "Cloud Services", "NoSQL", "Docker",
        "Data Modeling", "Big Data Tools"
    ],
    "AI Research Scientist": [
        "Python", "Machine Learning", "Deep Learning", "NLP",
        "Computer Vision", "Reinforcement Learning", "PyTorch",
        "TensorFlow", "Research", "Mathematics", "Statistics"
    ],
    "Business Intelligence Developer": [
        "SQL", "Data Warehousing", "ETL", "Tableau", "Power BI",
        "Data Modeling", "Reporting", "Dashboarding", "Python",
        "Analytics"
    ],
    "Cybersecurity Analyst": [
        "Network Security", "Vulnerability Assessment", "SIEM",
        "Security Tools", "Incident Response", "Risk Management",
        "Python", "Scripting", "Compliance", "Firewalls"
    ],
    "Cloud Architect": [
        "Cloud Services", "AWS", "Azure", "GCP", "Docker",
        "Kubernetes", "Networking", "Security", "Terraform",
        "Microservices", "System Design"
    ],
    "Mobile Developer": [
        "Kotlin", "Swift", "React Native", "Flutter", "Mobile UI",
        "REST APIs", "Version Control", "App Architecture",
        "Testing", "Performance Optimization"
    ],
    "Technical Writer": [
        "Technical Communication", "Documentation", "API Documentation",
        "Markdown", "Content Management", "Information Architecture",
        "Editing", "Research", "Subject Matter Expertise"
    ],
    "QA Engineer": [
        "Testing", "Automation", "Selenium", "Test Planning",
        "Python", "CI/CD", "Bug Tracking", "Performance Testing",
        "API Testing", "Agile/Scrum"
    ],
    "Project Manager": [
        "Agile/Scrum", "Project Planning", "Risk Management",
        "Stakeholder Management", "Budgeting", "Communication",
        "Leadership", "JIRA", "MS Project", "Team Management"
    ],
    "Database Administrator": [
        "SQL", "Database Design", "Performance Tuning", "Backup & Recovery",
        "Security", "NoSQL", "Cloud Databases", "Scripting",
        "Monitoring", "Migration"
    ],
}


def get_available_roles() -> list[str]:
    """Return the list of roles available for skill gap analysis."""
    return sorted(_ROLE_SKILLS_DATABASE.keys())


def get_role_skills(role: str) -> list[str]:
    """Get required skills for a specific role."""
    return _ROLE_SKILLS_DATABASE.get(role, [])


def _normalize_skill(skill: str) -> str:
    """Normalize a skill name for comparison."""
    return skill.strip().lower()


def analyze_skills_gap(resume_text: str, target_role: str) -> dict[str, Any]:
    """Analyze skills gap between resume and target role.

    Extracts skills from the resume text, compares them against the
    target role's requirements, and generates learning recommendations.

    Args:
        resume_text: The cleaned resume text.
        target_role: The target career role to analyze against.

    Returns:
        dict with current_skills, missing_skills, matched_skills,
        match_percentage, recommendations
    """
    required_skills = _ROLE_SKILLS_DATABASE.get(target_role, [])
    if not required_skills:
        return {
            "error": f"Unknown target role: {target_role}",
            "available_roles": get_available_roles(),
        }

    # Extract skills from resume using the same keyword extraction
    detected_keywords = set(split_keywords(resume_text))
    
    # Also check detected skills from the analysis pipeline
    detected_skills = set()
    for kw in detected_keywords:
        normalized = _normalize_skill(kw)
        detected_skills.add(normalized)
        # Add common variations
        detected_skills.add(kw.title())
        detected_skills.add(kw.upper())

    # Compare against role requirements
    matched_skills: list[str] = []
    missing_skills: list[str] = []

    for skill in required_skills:
        skill_normalized = _normalize_skill(skill)
        # Check various forms of the skill
        skill_variations = {skill_normalized, skill.lower(), skill.title()}
        # Also check partial matches for skills like "Python" matching "python"
        if any(
            v in detected_keywords or v in detected_skills
            for v in skill_variations
        ):
            matched_skills.append(skill)
        else:
            missing_skills.append(skill)

    match_percentage = round(
        (len(matched_skills) / len(required_skills)) * 100, 1
    ) if required_skills else 0.0

    # Generate recommendations for missing skills
    recommendations = _generate_gap_recommendations(missing_skills)

    return {
        "target_role": target_role,
        "total_required": len(required_skills),
        "matched_skills": sorted(matched_skills),
        "matched_count": len(matched_skills),
        "missing_skills": sorted(missing_skills),
        "missing_count": len(missing_skills),
        "match_percentage": match_percentage,
        "recommendations": recommendations,
    }



# ── Career Path Suggestion Engine ─────────────────────────────────

_CAREER_PATH_MAPPING: dict[str, dict[str, object]] = {
    "Data Scientist": {
        "keywords": ["python", "machine learning", "deep learning", "statistics", "sql", "tensorflow", "pytorch", "data", "nlp", "analytics", "ai"],
        "category": "Data & Analytics",
        "growing": True,
        "avg_salary": "$120K-$160K",
        "demand": "High",
        "description": "Use statistical methods and ML to extract insights from data",
        "skills_needed": ["Python", "Machine Learning", "SQL", "Statistics", "Data Visualization"],
    },
    "Data Analyst": {
        "keywords": ["sql", "excel", "tableau", "power bi", "analytics", "data", "python", "statistics", "reporting", "dashboard"],
        "category": "Data & Analytics",
        "growing": True,
        "avg_salary": "$65K-$95K",
        "demand": "High",
        "description": "Transform raw data into actionable business insights",
        "skills_needed": ["SQL", "Excel", "Data Visualization", "Statistics", "Python"],
    },
    "Software Engineer": {
        "keywords": ["python", "java", "javascript", "c++", "c#", "go", "rust", "programming", "algorithms", "data structures", "api", "backend", "frontend"],
        "category": "Software Development",
        "growing": True,
        "avg_salary": "$100K-$150K",
        "demand": "High",
        "description": "Design, build, and maintain software systems and applications",
        "skills_needed": ["Programming", "Data Structures", "Algorithms", "System Design", "Version Control"],
    },
    "Frontend Developer": {
        "keywords": ["html", "css", "javascript", "typescript", "react", "angular", "vue", "frontend", "web", "ui", "responsive"],
        "category": "Software Development",
        "growing": True,
        "avg_salary": "$90K-$135K",
        "demand": "High",
        "description": "Create responsive, accessible user interfaces for web applications",
        "skills_needed": ["HTML", "CSS", "JavaScript", "React", "TypeScript"],
    },
    "Backend Developer": {
        "keywords": ["python", "java", "node.js", "sql", "nosql", "api", "docker", "backend", "server", "database", "rest"],
        "category": "Software Development",
        "growing": True,
        "avg_salary": "$95K-$140K",
        "demand": "High",
        "description": "Build scalable server-side logic, APIs, and database systems",
        "skills_needed": ["Python", "Java", "SQL", "API Design", "Docker"],
    },
    "Full Stack Developer": {
        "keywords": ["javascript", "html", "css", "react", "node.js", "python", "sql", "mongodb", "full stack", "web", "api"],
        "category": "Software Development",
        "growing": True,
        "avg_salary": "$100K-$150K",
        "demand": "High",
        "description": "Work across both frontend and backend layers of web applications",
        "skills_needed": ["JavaScript", "HTML", "CSS", "React", "Node.js"],
    },
    "DevOps Engineer": {
        "keywords": ["docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "linux", "terraform", "ansible", "jenkins", "cloud", "devops"],
        "category": "Infrastructure & Cloud",
        "growing": True,
        "avg_salary": "$110K-$160K",
        "demand": "High",
        "description": "Bridge development and operations with automation and cloud infrastructure",
        "skills_needed": ["Docker", "Kubernetes", "CI/CD", "Cloud", "Linux"],
    },
    "Machine Learning Engineer": {
        "keywords": ["python", "machine learning", "deep learning", "tensorflow", "pytorch", "mlops", "docker", "kubernetes", "data", "model", "deployment"],
        "category": "Data & Analytics",
        "growing": True,
        "avg_salary": "$130K-$180K",
        "demand": "Very High",
        "description": "Build and deploy ML models into production systems",
        "skills_needed": ["Python", "Machine Learning", "Deep Learning", "MLOps", "Docker"],
    },
    "Product Manager": {
        "keywords": ["product", "strategy", "user research", "agile", "scrum", "roadmap", "stakeholder", "analytics", "a/b testing", "leadership"],
        "category": "Product & Management",
        "growing": True,
        "avg_salary": "$100K-$160K",
        "demand": "Moderate",
        "description": "Drive product vision, strategy, and execution across teams",
        "skills_needed": ["Product Strategy", "User Research", "Agile", "Data Analysis", "Leadership"],
    },
    "UX Designer": {
        "keywords": ["figma", "sketch", "adobe xd", "wireframing", "prototyping", "user research", "usability", "ui", "ux", "design", "interaction"],
        "category": "Design",
        "growing": True,
        "avg_salary": "$85K-$130K",
        "demand": "Moderate",
        "description": "Design intuitive, accessible user experiences for digital products",
        "skills_needed": ["Figma", "User Research", "Wireframing", "Prototyping", "Visual Design"],
    },
    "Data Engineer": {
        "keywords": ["etl", "spark", "kafka", "airflow", "sql", "python", "data warehouse", "bigquery", "snowflake", "pipeline", "hadoop"],
        "category": "Data & Analytics",
        "growing": True,
        "avg_salary": "$110K-$160K",
        "demand": "High",
        "description": "Build robust data pipelines and infrastructure for analytics",
        "skills_needed": ["Python", "SQL", "ETL", "Spark", "Data Warehousing"],
    },
    "Cybersecurity Analyst": {
        "keywords": ["security", "cybersecurity", "network security", "encryption", "authentication", "compliance", "gdpr", "hipaa", "risk", "vulnerability"],
        "category": "Security",
        "growing": True,
        "avg_salary": "$90K-$140K",
        "demand": "Very High",
        "description": "Protect organizational assets through security monitoring and analysis",
        "skills_needed": ["Network Security", "Vulnerability Assessment", "SIEM", "Risk Management", "Python"],
    },
    "Cloud Architect": {
        "keywords": ["aws", "azure", "gcp", "cloud", "docker", "kubernetes", "terraform", "microservices", "architecture", "serverless"],
        "category": "Infrastructure & Cloud",
        "growing": True,
        "avg_salary": "$140K-$190K",
        "demand": "High",
        "description": "Design and implement cloud-native infrastructure solutions",
        "skills_needed": ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform"],
    },
    "Mobile Developer": {
        "keywords": ["kotlin", "swift", "react native", "flutter", "dart", "android", "ios", "mobile", "app", "uikit"],
        "category": "Software Development",
        "growing": True,
        "avg_salary": "$95K-$145K",
        "demand": "Moderate",
        "description": "Build native or cross-platform mobile applications",
        "skills_needed": ["Kotlin", "Swift", "React Native", "Flutter", "Mobile UI"],
    },
    "AI Research Scientist": {
        "keywords": ["machine learning", "deep learning", "nlp", "computer vision", "reinforcement learning", "pytorch", "tensorflow", "research", "mathematics", "statistics"],
        "category": "Data & Analytics",
        "growing": True,
        "avg_salary": "$140K-$200K",
        "demand": "Moderate",
        "description": "Push the boundaries of AI through novel algorithms and models",
        "skills_needed": ["Python", "Machine Learning", "Deep Learning", "Research", "Mathematics"],
    },
    "Technical Writer": {
        "keywords": ["writing", "documentation", "technical communication", "editing", "markdown", "api documentation", "content", "research"],
        "category": "Content",
        "growing": False,
        "avg_salary": "$65K-$100K",
        "demand": "Moderate",
        "description": "Create clear, accurate technical documentation for diverse audiences",
        "skills_needed": ["Technical Communication", "Documentation", "Editing", "Research", "API Documentation"],
    },
    "QA Engineer": {
        "keywords": ["testing", "automation", "selenium", "pytest", "jest", "ci/cd", "quality", "bug", "test planning", "performance testing"],
        "category": "Software Development",
        "growing": False,
        "avg_salary": "$70K-$110K",
        "demand": "Moderate",
        "description": "Ensure software quality through systematic testing and automation",
        "skills_needed": ["Testing", "Automation", "Selenium", "Python", "CI/CD"],
    },
    "Project Manager": {
        "keywords": ["project management", "agile", "scrum", "jira", "leadership", "budgeting", "stakeholder", "risk", "planning", "team"],
        "category": "Product & Management",
        "growing": False,
        "avg_salary": "$80K-$130K",
        "demand": "Moderate",
        "description": "Plan, execute, and deliver projects on time and within budget",
        "skills_needed": ["Agile/Scrum", "Project Planning", "Risk Management", "Leadership", "Communication"],
    },
    "Database Administrator": {
        "keywords": ["sql", "database", "postgresql", "mysql", "oracle", "mongodb", "backup", "recovery", "performance tuning", "security"],
        "category": "Infrastructure & Cloud",
        "growing": False,
        "avg_salary": "$85K-$130K",
        "demand": "Moderate",
        "description": "Manage and optimize database systems for performance and reliability",
        "skills_needed": ["SQL", "Database Design", "Performance Tuning", "Backup & Recovery", "Security"],
    },
    "Business Intelligence Developer": {
        "keywords": ["sql", "etl", "tableau", "power bi", "data warehouse", "reporting", "dashboard", "analytics", "data modeling"],
        "category": "Data & Analytics",
        "growing": True,
        "avg_salary": "$80K-$120K",
        "demand": "Moderate",
        "description": "Create BI solutions enabling data-driven business decisions",
        "skills_needed": ["SQL", "Data Warehousing", "ETL", "Tableau", "Power BI"],
    },
}


def suggest_career_paths(resume_text: str) -> list[dict[str, object]]:
    """Suggest career paths based on resume skills and keywords.

    Analyzes resume text against a knowledge base of career paths,
    scoring each path by how many of its keywords match the resume.
    Returns up to 8 suggestions ranked by match score.
    """
    if not resume_text or len(resume_text.strip()) < 10:
        return []

    lower_text = resume_text.lower()
    scored: list[dict[str, object]] = []

    for role, info in _CAREER_PATH_MAPPING.items():
        keywords = info["keywords"]  # type: ignore
        matches = sum(1 for kw in keywords if kw in lower_text)
        if matches == 0:
            continue

        score = round(matches / len(keywords) * 100, 1)
        scored.append({
            "role": role,
            "score": score,
            "category": info["category"],
            "growing": info["growing"],
            "avg_salary": info["avg_salary"],
            "demand": info["demand"],
            "description": info["description"],
            "skills_needed": info["skills_needed"],
            "matched_keywords": matches,
            "total_keywords": len(keywords),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:8]


def generate_learning_roadmap(resume_text: str) -> list[dict[str, object]]:
    """Generate a structured learning roadmap based on resume skills.

    Analyzes detected skills and returns progressive learning paths
    organized by skill area with beginner/intermediate/advanced stages.
    """
    if not resume_text or len(resume_text.strip()) < 10:
        return []

    lower_text = resume_text.lower()
    detected: list[str] = []

    # Detect skill areas from the text
    skill_areas = {
        "Python": ["python", "django", "flask", "fastapi", "pandas", "numpy"],
        "JavaScript": ["javascript", "js", "node.js", "react", "angular", "vue", "typescript"],
        "Java": ["java", "spring", "kotlin", "jvm"],
        "Web Development": ["html", "css", "sass", "scss", "bootstrap", "tailwind", "webpack", "frontend", "backend"],
        "Data Science": ["machine learning", "deep learning", "nlp", "computer vision", "tensorflow", "pytorch", "scikit-learn", "data science"],
        "Databases": ["sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "cassandra", "nosql"],
        "Cloud & DevOps": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "ci/cd", "jenkins", "cloud"],
        "Data Engineering": ["etl", "spark", "kafka", "airflow", "data warehouse", "data pipeline", "big data"],
        "Mobile Development": ["android", "ios", "swift", "kotlin", "flutter", "react native"],
        "Security": ["security", "cybersecurity", "encryption", "authentication", "penetration testing", "network security"],
        "System Design": ["microservices", "system design", "architecture", "distributed systems", "api design"],
        "UI/UX Design": ["figma", "sketch", "adobe xd", "wireframing", "prototyping", "user research", "ux", "ui"],
        "Product Management": ["product", "agile", "scrum", "roadmap", "stakeholder", "product strategy"],
        "Testing": ["testing", "selenium", "pytest", "jest", "qa", "automation testing", "tdd"],
    }

    for area, keywords in skill_areas.items():
        if any(kw in lower_text for kw in keywords):
            detected.append(area)

    if not detected:
        return []

    # Generate roadmap entries
    roadmap: list[dict[str, object]] = []

    roadmap_templates = {
        "Python": {
            "icon": "\U0001f40d",
            "beginner": "Learn Python basics: syntax, data types, control flow, and functions",
            "intermediate": "Master OOP, decorators, generators, and popular libraries (pandas, requests)",
            "advanced": "Build projects with Django/Flask, async programming, and package development",
        },
        "JavaScript": {
            "icon": "\U0001f310",
            "beginner": "Learn JS fundamentals: variables, functions, DOM manipulation, ES6+ syntax",
            "intermediate": "Master async JS, promises, closures, and build with React or Node.js",
            "advanced": "Deep dive into TypeScript, testing frameworks, and full-stack application architecture",
        },
        "Java": {
            "icon": "\u2615",
            "beginner": "Learn Java fundamentals: OOP, collections, exception handling",
            "intermediate": "Master Spring Boot, JPA, REST APIs, and build microservices",
            "advanced": "Explore reactive programming, cloud-native Java, and performance optimization",
        },
        "Web Development": {
            "icon": "\U0001f578\ufe0f",
            "beginner": "Learn HTML5 semantics, CSS3 layouts (Flexbox/Grid), and responsive design",
            "intermediate": "Master a frontend framework (React/Vue), CSS preprocessors, and build tools",
            "advanced": "Build full-stack apps, PWAs, implement SSR/SSG, and optimize Core Web Vitals",
        },
        "Data Science": {
            "icon": "\U0001f4ca",
            "beginner": "Learn Python for data analysis: pandas, numpy, matplotlib, seaborn",
            "intermediate": "Master ML with scikit-learn: regression, classification, clustering, feature engineering",
            "advanced": "Deep dive into deep learning, NLP, and deploy models to production",
        },
        "Databases": {
            "icon": "\U0001f5c4\ufe0f",
            "beginner": "Learn SQL fundamentals: queries, joins, aggregations, and indexing",
            "intermediate": "Master database design, normalization, transactions, and ORM usage",
            "advanced": "Explore NoSQL databases, query optimization, sharding, and distributed databases",
        },
        "Cloud & DevOps": {
            "icon": "\u2601\ufe0f",
            "beginner": "Learn Linux basics, shell scripting, and version control with Git",
            "intermediate": "Master Docker containers, CI/CD pipelines, and infrastructure as code",
            "advanced": "Deep dive into Kubernetes orchestration, cloud architecture, and monitoring",
        },
        "Data Engineering": {
            "icon": "\U0001f4e1",
            "beginner": "Learn Python and SQL for data pipelines, file formats (CSV, Parquet, Avro)",
            "intermediate": "Master ETL tools (Airflow, dbt), data warehousing, and batch processing",
            "advanced": "Deep dive into streaming (Kafka, Flink), Spark optimization, and data lakehouse",
        },
        "Mobile Development": {
            "icon": "\U0001f4f1",
            "beginner": "Learn native (Swift/Kotlin) or cross-platform (Flutter/React Native) basics",
            "intermediate": "Master app architecture, state management, and REST API integration",
            "advanced": "Deep dive into performance optimization, native modules, and app store deployment",
        },
        "Security": {
            "icon": "\U0001f6e1\ufe0f",
            "beginner": "Learn security fundamentals: OWASP Top 10, network basics, cryptography basics",
            "intermediate": "Master penetration testing, SIEM tools, incident response procedures",
            "advanced": "Deep dive into zero-trust architecture, cloud security, and security automation",
        },
        "System Design": {
            "icon": "\U0001f3d7\ufe0f",
            "beginner": "Learn design patterns, SOLID principles, and UML basics",
            "intermediate": "Master microservices, API design, caching strategies, and load balancing",
            "advanced": "Deep dive into distributed systems, consensus algorithms, and event-driven architecture",
        },
        "UI/UX Design": {
            "icon": "\U0001f3a8",
            "beginner": "Learn design fundamentals: color theory, typography, layout principles",
            "intermediate": "Master Figma, prototyping, user research methods, and design systems",
            "advanced": "Deep dive into motion design, accessibility, design tokens, and design operations",
        },
        "Product Management": {
            "icon": "\U0001f4ad",
            "beginner": "Learn product lifecycle, user stories, backlog management, and agile ceremonies",
            "intermediate": "Master product strategy, OKRs, A/B testing, stakeholder management",
            "advanced": "Deep dive into growth strategy, platform thinking, and product-led growth",
        },
        "Testing": {
            "icon": "\u2705",
            "beginner": "Learn testing fundamentals: unit tests, test cases, bug reporting",
            "intermediate": "Master automation frameworks (Selenium, Cypress, pytest), CI/CD integration",
            "advanced": "Deep dive into performance testing, chaos engineering, and quality engineering",
        },
    }

    seen_areas: set[str] = set()
    for area in detected:
        if area in seen_areas or area not in roadmap_templates:
            continue
        seen_areas.add(area)
        tmpl = roadmap_templates[area]
        roadmap.append({
            "area": area,
            "icon": tmpl["icon"],
            "stages": [
                {"level": "Beginner", "description": tmpl["beginner"], "duration": "2-4 weeks"},
                {"level": "Intermediate", "description": tmpl["intermediate"], "duration": "4-8 weeks"},
                {"level": "Advanced", "description": tmpl["advanced"], "duration": "8-12 weeks"},
            ],
        })

    roadmap.sort(key=lambda x: detected.index(x["area"]))
    return roadmap


def _generate_gap_recommendations(missing_skills: list[str]) -> list[dict[str, str]]:
    """Generate learning recommendations for missing skills."""
    recommendations: list[dict[str, str]] = []

    resource_map: dict[str, list[str]] = {
        "python": [
            "Complete Python for Everybody on Coursera",
            "Practice on LeetCode or HackerRank",
            "Build projects with real-world datasets",
        ],
        "sql": [
            "Master SQL on Mode Analytics SQL Tutorial",
            "Practice on LeetCode SQL challenges",
            "Build a personal project with PostgreSQL",
        ],
        "machine learning": [
            "Take Andrew Ng's ML course on Coursera",
            "Build end-to-end ML projects",
            "Practice on Kaggle competitions",
        ],
        "deep learning": [
            "Follow fast.ai's Practical Deep Learning course",
            "Implement papers from arXiv",
            "Build projects with TensorFlow or PyTorch",
        ],
        "data visualization": [
            "Learn Tableau via Tableau Public tutorials",
            "Master Matplotlib & Seaborn in Python",
            "Build an interactive dashboard project",
        ],
        "docker": [
            "Follow Docker's official getting-started guide",
            "Containerize a web application",
            "Learn Docker Compose for multi-container apps",
        ],
        "kubernetes": [
            "Complete KodeKloud's Kubernetes course",
            "Set up a minikube cluster locally",
            "Deploy a microservices application",
        ],
        "aws": [
            "Study for AWS Solutions Architect certification",
            "Build serverless applications with Lambda",
            "Deploy applications using ECS or EKS",
        ],
        "cloud services": [
            "Start with AWS Free Tier or Google Cloud free credits",
            "Learn one cloud provider deeply first",
            "Build and deploy a scalable application",
        ],
        "react": [
            "Complete the official React tutorial",
            "Build a portfolio project with React",
            "Learn state management with Redux or Context API",
        ],
        "javascript": [
            "Master JavaScript on freeCodeCamp",
            "Build interactive web applications",
            "Learn modern ES6+ features",
        ],
        "typescript": [
            "Complete TypeScript handbook on the official site",
            "Convert a JavaScript project to TypeScript",
            "Learn advanced types and generics",
        ],
        "agile/scrum": [
            "Get Certified Scrum Master (CSM) certification",
            "Practice with JIRA or Trello",
            "Lead a sprint in your current team",
        ],
        "statistics": [
            "Complete Statistics on Khan Academy",
            "Take a university-level statistics course",
            "Apply statistical tests to real datasets",
        ],
        "etl": [
            "Learn Apache Airflow for workflow orchestration",
            "Build an ETL pipeline with Python",
            "Master data warehousing concepts",
        ],
        "testing": [
            "Learn pytest for Python or Jest for JavaScript",
            "Practice test-driven development (TDD)",
            "Write unit, integration, and end-to-end tests",
        ],
        "ci/cd": [
            "Set up GitHub Actions for a project",
            "Learn Jenkins or GitLab CI",
            "Automate testing and deployment pipelines",
        ],
    }

    for skill in missing_skills:
        skill_key = _normalize_skill(skill)
        # Look for matching resources
        resource_keys = [k for k in resource_map if k in skill_key or skill_key in k]
        
        if resource_keys:
            resources = resource_map[resource_keys[0]]
            recommendations.append({
                "skill": skill,
                "resources": resources,
                "priority": "High" if len(resource_keys) > 0 else "Medium",
            })
        else:
            # Generic recommendation
            recommendations.append({
                "skill": skill,
                "resources": [
                    f"Research online courses for {skill}",
                    f"Build a project using {skill}",
                    f"Practice {skill} with hands-on exercises",
                ],
                "priority": "Medium",
            })

    return recommendations


def analyze_resume(resume_text: str, mode: str = "standard") -> dict[str, Any]:
    bundle, courses = load_artifacts()
    if not bundle:
        raise RuntimeError("Model artifacts are missing. The bootstrap step could not prepare them.")

    model_bundle = dict(bundle)
    model_bundle["courses"] = courses

    cleaned_resume = clean_text(resume_text)
    if not cleaned_resume:
        raise ValueError("Resume text is required.")

    risk_score = _score_risk(model_bundle, cleaned_resume)
    top_roles = _top_matches(model_bundle, cleaned_resume)
    clusters = _skill_clusters(model_bundle, cleaned_resume)
    roadmap = _generate_roadmap(model_bundle, cleaned_resume, top_roles)
    riasec = _riasec_profile(clusters, cleaned_resume)
    reasoning = _build_reasoning(cleaned_resume, risk_score, risk_label(risk_score), top_roles, clusters, roadmap, riasec)

    # ── Rich skill extraction (SAHAY_AI-style categorized skills) ──
    rich_skills: dict[str, object] = {"by_category": {}, "all_skills": [], "count": 0, "categories_found": 0}
    try:
        from resume_parser import extract_skills_from_text as _rich_skills_fn
        rich_skills = _rich_skills_fn(cleaned_resume)
        all_skill_names = rich_skills.get("all_skills", [])
        if all_skill_names:
            reasoning["skills_detected"] = all_skill_names[:12]
    except Exception:
        pass

    analysis: dict[str, Any] = {
        "mode": mode,
        "risk_score": round(risk_score, 3),
        "risk_label": risk_label(risk_score),
        "top_roles": top_roles,
        "skill_clusters": clusters,
        "roadmap": roadmap,
        "riasec": riasec,
        "reasoning": reasoning,
        "skills": rich_skills,  # Rich categorized skills for frontend display
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