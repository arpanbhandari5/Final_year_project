"""Isolated product-copy and architecture constants.

Not imported by app.py, risk_assessor.py, or production scoring.
"""

from __future__ import annotations

MODEL_ID = "prayash-task-exposure-gpts-are-gpts-v1"
MODEL_LAYER = "GPTs-are-GPTs public benchmark — 923 occupations"
PRODUCT_LAYER = "Prayash common-occupation coverage — 800 occupations"
TARGET = "human_labels"
CLASSES = ("E0", "E1", "E2")
HISTORICAL_RUBRIC_STATUS = "historical/deferred Prayash five-level rubric"
HUMAN_REVIEW_STATUS = "deferred_due_to_unavailable_independent_reviewers"
AI248_STATUS = "baseline_provisional_ai_weak_supervision"
PRODUCTION_STATUS = "research-only"

PROHIBITED_CLAIMS = (
    "job-loss probability",
    "unemployment probability",
    "replacement probability",
    "personal job loss",
    "chance of unemployment",
    "AI-proof job",
    "safe job",
    "unsafe job",
)

TASK_ANALYSIS_COPY = (
    "This analysis classifies task-level exposure under the published "
    "GPTs-are-GPTs E0/E1/E2 taxonomy. It describes contextual task exposure. "
    "It is not a prediction of personal job loss, unemployment, employment "
    "probability, or worker replacement."
)

OCCUPATION_COPY = (
    "Contextual task exposure. This occupation contains tasks represented "
    "across the E0, E1, and E2 categories in the published GPTs-are-GPTs "
    "taxonomy. These categories describe task-level exposure context and "
    "should not be interpreted as a prediction of what will happen to an "
    "individual worker."
)

RESUME_COPY = (
    "Task overlap. Your resume contains evidence related to tasks represented "
    "in different exposure categories. This describes task context and overlap "
    "with the benchmark taxonomy. It does not estimate your personal "
    "probability of job loss."
)

MODEL_CONFIDENCE_COPY = "Model confidence for this task classification"
FEATURE_EXPLANATION_LABEL = "model-derived textual associations"

CAREER_ACTIONS = (
    "Strengthen complementary skills.",
    "Document measurable work outcomes.",
    "Build evidence of domain knowledge.",
    "Develop stakeholder communication skills.",
    "Develop verification and quality-control practices.",
    "Build responsible AI-use capabilities.",
    "Strengthen judgment and exception-handling capabilities.",
)

CAREER_ACTION_DISCLAIMER = (
    "These recommendations are general career-development guidance. "
    "They are not predictions derived from an individual's probability of job loss. "
    "No skill listed here guarantees employment."
)

PROVENANCE_SHORT = (
    "The released GPTs-are-GPTs benchmark contains 19,265 task rows with "
    "human-derived exposure labels under its published E0/E1/E2 taxonomy."
)

PROVENANCE_METHOD = (
    "The source methodology describes human annotation of detailed work "
    "activities and a subset of tasks, with labels aggregated to task and "
    "occupation levels."
)

DIRECT_REVIEW_LIMITATION = (
    "Direct task-level human annotation count: not separately recoverable "
    "from the released file. Do not equate 19,265 labelled rows with 19,265 "
    "independent direct human reviews."
)
