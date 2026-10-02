from __future__ import annotations

import re
from typing import Any

from storage import CanonicalSkill, SkillAlias, SkillPrerequisite, db

BASE_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go", "R", "Rust", "Ruby", "PHP", "Kotlin", "Swift",
    "Node.js", "React", "Vue", "Angular", "HTML", "CSS", "SQL", "NoSQL", "PostgreSQL", "MySQL", "MongoDB", "Redis",
    "Git", "Docker", "Kubernetes", "Linux", "AWS", "Azure", "Google Cloud", "Terraform", "Jenkins", "GitHub Actions",
    "Machine Learning", "Deep Learning", "Natural Language Processing", "Computer Vision", "Data Analysis", "Data Visualization", "Statistics", "Linear Algebra", "Calculus", "Experiment Design",
    "Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch", "Jupyter", "Spark", "Hadoop", "Airflow", "dbt", "Tableau", "Power BI", "Excel",
    "System Design", "API Design", "Microservices", "Distributed Systems", "Event-Driven Architecture", "Software Testing", "Test Automation", "Agile", "Scrum", "Project Management", "Product Management",
    "Communication", "Written Communication", "Presentation", "Public Speaking", "Stakeholder Management", "Leadership", "Mentoring", "Teamwork", "Collaboration", "Problem Solving", "Critical Thinking", "Time Management", "Adaptability", "Negotiation", "Conflict Resolution", "Customer Service", "Decision Making", "Creativity", "Research", "Documentation",
]

DOMAINS = [
    "Programming", "Data Engineering", "Cloud Computing", "Cybersecurity", "DevOps", "Frontend Development", "Backend Development", "Mobile Development", "Database Administration", "Data Science", "Analytics", "Machine Learning Operations", "Quality Assurance", "Technical Writing", "Product Strategy", "Business Analysis", "User Research", "Design Thinking", "Operations", "Digital Marketing", "Sales Engineering", "People Management", "Career Coaching", "Financial Analysis", "Risk Management", "Compliance", "Privacy", "Accessibility", "Open Source", "Research Methods",
]
LEVELS = ["Fundamentals", "Applied Practice", "Advanced Practice", "Architecture", "Best Practices", "Troubleshooting", "Automation", "Evaluation", "Planning", "Delivery", "Governance", "Optimization", "Security", "Documentation", "Communication", "Leadership"]
ALIASES = {"js": "JavaScript", "javascript": "JavaScript", "py": "Python", "node": "Node.js", "nodejs": "Node.js", "reactjs": "React", "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "powerbi": "Power BI", "ml": "Machine Learning", "nlp": "Natural Language Processing"}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def seed_skill_registry() -> int:
    names = list(dict.fromkeys(BASE_SKILLS + [f"{domain} {level}" for domain in DOMAINS for level in LEVELS]))
    with db.session.no_autoflush:
        for name in names:
            skill = CanonicalSkill.query.filter_by(slug=slugify(name)).first()
            if skill is None:
                skill = CanonicalSkill(name=name, slug=slugify(name), category="soft" if name in BASE_SKILLS[-30:] else "technical")
                db.session.add(skill)
                db.session.flush()
            alias_values = {name, name.lower()}
            for alias, canonical in ALIASES.items():
                if canonical == name:
                    alias_values.add(alias)
            for alias in alias_values:
                normalized = normalize_alias(alias)
                if not SkillAlias.query.filter_by(normalized_alias=normalized).first():
                    db.session.add(SkillAlias(canonical_skill_id=skill.id, alias=alias, normalized_alias=normalized))
    db.session.commit()
    return len(names)


def resolve_skill_names(text: str) -> list[str]:
    normalized = text or ""
    aliases = SkillAlias.query.order_by(db.func.length(SkillAlias.normalized_alias).desc()).all()
    matches: list[str] = []
    for item in aliases:
        escaped = re.escape(item.normalized_alias)
        if re.search(rf"(?<![A-Za-z0-9+#.]){escaped}(?![A-Za-z0-9+#.])", normalized.lower()):
            skill = db.session.get(CanonicalSkill, item.canonical_skill_id)
            if skill and skill.name not in matches:
                matches.append(skill.name)
    return matches
