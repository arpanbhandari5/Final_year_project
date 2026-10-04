"""Dedicated Target Job Match vocabulary.

Not used by risk_assessor or production occupation lookup. Aliases are
conservative: short tokens (R, C, Go) require explicit programming context.
"""

from __future__ import annotations

# canonical_name is the stored requirement label. aliases are extra phrases.
# short_context: if True, aliases shorter than 3 chars (or "go") need extra regex.

VOCABULARY: list[dict[str, object]] = [
    {"canonical_name": "Python", "aliases": ("python", "python programming"), "category": "tool/technology"},
    {"canonical_name": "JavaScript", "aliases": ("javascript", "javascript programming", "js"), "category": "tool/technology"},
    {"canonical_name": "TypeScript", "aliases": ("typescript",), "category": "tool/technology"},
    {"canonical_name": "Java", "aliases": ("java",), "category": "tool/technology"},
    {"canonical_name": "C++", "aliases": ("c++", "cpp"), "category": "tool/technology"},
    {"canonical_name": "SQL", "aliases": ("sql", "t-sql", "tsql"), "category": "tool/technology", "require_word": True},
    {"canonical_name": "PostgreSQL", "aliases": ("postgresql", "postgres"), "category": "tool/technology"},
    {"canonical_name": "Excel", "aliases": ("excel", "microsoft excel"), "category": "tool/technology"},
    {"canonical_name": "Power BI", "aliases": ("power bi", "powerbi"), "category": "tool/technology"},
    {"canonical_name": "Tableau", "aliases": ("tableau",), "category": "tool/technology"},
    {"canonical_name": "Git", "aliases": ("git",), "category": "tool/technology", "require_word": True},
    {"canonical_name": "Docker", "aliases": ("docker",), "category": "tool/technology"},
    {"canonical_name": "Kubernetes", "aliases": ("kubernetes", "k8s"), "category": "tool/technology"},
    {"canonical_name": "AWS", "aliases": ("aws", "amazon web services"), "category": "tool/technology"},
    {"canonical_name": "Azure", "aliases": ("azure",), "category": "tool/technology"},
    {"canonical_name": "Flask", "aliases": ("flask",), "category": "tool/technology"},
    {"canonical_name": "React", "aliases": ("react",), "category": "tool/technology"},
    {"canonical_name": "HTML", "aliases": ("html",), "category": "tool/technology"},
    {"canonical_name": "CSS", "aliases": ("css",), "category": "tool/technology"},
    {"canonical_name": "machine learning", "aliases": ("machine learning", "ml models"), "category": "skill"},
    {"canonical_name": "data analysis", "aliases": ("data analysis", "data analytics"), "category": "skill"},
    {"canonical_name": "data visualization", "aliases": ("data visualization",), "category": "skill"},
    {"canonical_name": "project management", "aliases": ("project management",), "category": "skill"},
    {"canonical_name": "Agile", "aliases": ("agile",), "category": "skill"},
    {"canonical_name": "Scrum", "aliases": ("scrum",), "category": "skill"},
    {"canonical_name": "communication", "aliases": ("communication",), "category": "communication/behavioral"},
    {"canonical_name": "leadership", "aliases": ("leadership",), "category": "communication/behavioral"},
    {"canonical_name": "stakeholder management", "aliases": ("stakeholder management",), "category": "communication/behavioral"},
    {"canonical_name": "customer service", "aliases": ("customer service",), "category": "communication/behavioral"},
    {"canonical_name": "teamwork", "aliases": ("teamwork",), "category": "communication/behavioral"},
    {"canonical_name": "sales", "aliases": ("sales",), "category": "domain knowledge"},
    {"canonical_name": "marketing", "aliases": ("marketing",), "category": "domain knowledge"},
    {"canonical_name": "accounting", "aliases": ("accounting",), "category": "domain knowledge"},
    {"canonical_name": "financial analysis", "aliases": ("financial analysis",), "category": "domain knowledge"},
    {"canonical_name": "research", "aliases": ("research",), "category": "skill"},
    {"canonical_name": "cloud", "aliases": ("cloud",), "category": "domain knowledge"},
    {"canonical_name": "statistics", "aliases": ("statistics",), "category": "skill"},
    {"canonical_name": "problem solving", "aliases": ("problem solving",), "category": "skill"},
    {
        "canonical_name": "R",
        "aliases": ("r programming", "r language", "rstudio", "r studio"),
        "category": "tool/technology",
        "context_patterns": (r"\bexperience with r\b", r"\br programming\b", r"\br language\b", r"\brstudio\b"),
    },
    {
        "canonical_name": "C",
        "aliases": ("c programming", "c language"),
        "category": "tool/technology",
        "context_patterns": (r"\bc programming\b", r"\bc language\b"),
    },
    {
        "canonical_name": "Go",
        "aliases": ("golang", "go programming", "go language"),
        "category": "tool/technology",
        "context_patterns": (r"\bgolang\b", r"\bgo programming\b", r"\bgo language\b"),
    },
]

REQUIRED_HEADINGS = (
    "required",
    "requirements",
    "must have",
    "minimum qualifications",
    "basic qualifications",
    "qualifications",
)
PREFERRED_HEADINGS = (
    "preferred",
    "nice to have",
    "preferred qualifications",
    "bonus",
    "plus",
    "desired",
)
