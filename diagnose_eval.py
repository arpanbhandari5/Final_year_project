"""Diagnostic script to understand why evaluation R² is negative."""
from __future__ import annotations
import re
import ast
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.lower() == "nan" else text


def read_csv_any(*relative_paths: str) -> pd.DataFrame:
    for relative_path in relative_paths:
        candidate = DATA_DIR / relative_path
        if candidate.exists():
            frame = pd.read_csv(candidate, sep=None, engine="python")
            frame.columns = [normalize_text(column) for column in frame.columns]
            return frame
    raise FileNotFoundError(f"None found: {', '.join(relative_paths)}")


def parse_listish(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return [normalize_text(item) for item in value if normalize_text(item)]
    text = normalize_text(value)
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [normalize_text(item) for item in parsed if normalize_text(item)]
    except Exception:
        pass
    parts = [part.strip(" []\"'") for part in re.split(r"[,;/|]", text)]
    return [p for p in parts if p]


def build_job_text(row: pd.Series) -> str:
    pieces = [
        row.get("job_role", ""), row.get("industry", ""), row.get("education_level", ""),
        f"experience {row.get('experience_required_years', '')}",
        f"salary {row.get('avg_salary_usd', '')}",
        f"repetition {row.get('task_repetition_level', '')}",
        f"creativity {row.get('creativity_requirement', '')}",
        f"physical {row.get('physical_labor_level', '')}",
        f"analysis {row.get('analytical_complexity', '')}",
        f"social {row.get('social_interaction_level', '')}",
        f"skills {row.get('skill_complexity_score', '')}",
        f"communication {row.get('communication_requirement', '')}",
        f"domain {row.get('domain_specific_knowledge_level', '')}",
        f"team {row.get('team_collaboration_level', '')}",
    ]
    return normalize_text(" ".join(map(str, pieces)))


def build_resume_text(row: pd.Series) -> str:
    pieces = [
        row.get("career_objective", ""),
        " ".join(parse_listish(row.get("skills", ""))),
        " ".join(parse_listish(row.get("related_skils_in_job", ""))),
        " ".join(parse_listish(row.get("responsibilities", ""))),
        " ".join(parse_listish(row.get("skills_required", ""))),
        " ".join(parse_listish(row.get("positions", ""))),
        " ".join(parse_listish(row.get("major_field_of_studies", ""))),
        " ".join(parse_listish(row.get("certification_skills", ""))),
    ]
    return normalize_text(" ".join(normalize_text(p) for p in pieces if normalize_text(p)))


def main() -> None:
    automation = read_csv_any("automation_risk.csv")
    resumes = read_csv_any("resume_corpus.csv")
    job_texts = [build_job_text(row) for _, row in automation.iterrows()]
    resume_texts = [build_resume_text(row) for _, row in resumes.iterrows()]

    corpus = [*job_texts, *resume_texts]
    vectorizer = TfidfVectorizer(max_features=7000, ngram_range=(1, 2), stop_words="english")
    vectors = vectorizer.fit_transform(corpus)
    job_vectors = vectors[: len(job_texts)]
    risk_targets = automation["automation_risk_score"].astype(float).clip(0.0, 1.0).to_numpy()

    print("=== DIAGNOSTIC ===")
    print(f"Target mean:   {np.mean(risk_targets):.4f}")
    print(f"Target std:    {np.std(risk_targets):.4f}")
    print(f"Target var:    {np.var(risk_targets):.6f}")
    print(f"Features:      {job_vectors.shape[1]}")
    print(f"Nonzero/row:   {job_vectors.nnz / job_vectors.shape[0]:.1f}")
    print(f"Corpus size:   {len(corpus)} (jobs={len(job_texts)}, resumes={len(resume_texts)})")

    X_train, X_test, y_train, y_test = train_test_split(
        job_vectors, risk_targets, test_size=0.2, random_state=42
    )
    model = Ridge(alpha=1.2)
    model.fit(X_train, y_train)
    train_pred = np.clip(model.predict(X_train), 0.0, 1.0)
    test_pred = np.clip(model.predict(X_test), 0.0, 1.0)

    print(f"\nTrain R2:  {r2_score(y_train, train_pred):.4f}")
    print(f"Test  R2:  {r2_score(y_test, test_pred):.4f}")
    print(f"Train MAE: {mean_absolute_error(y_train, train_pred):.4f}")
    print(f"Test  MAE: {mean_absolute_error(y_test, test_pred):.4f}")
    print(f"Coef range: [{model.coef_.min():.6f}, {model.coef_.max():.6f}]")
    print(f"Coef norm:  {np.linalg.norm(model.coef_):.4f}")

    # Check: are job_role texts unique enough?
    unique_roles = len(set(job_texts))
    print(f"\nUnique job text strings: {unique_roles} / {len(job_texts)}")

    # Check: same role, different risk?
    role_risk = automation.groupby("job_role")["automation_risk_score"]
    print(f"Unique job roles: {role_risk.ngroups}")
    print(f"Avg within-role risk std: {role_risk.std().mean():.4f}")

    # Try fitting on ONLY job texts (no resumes in corpus)
    vec2 = TfidfVectorizer(max_features=7000, ngram_range=(1, 2), stop_words="english")
    jv2 = vec2.fit_transform(job_texts)
    Xtr2, Xte2, ytr2, yte2 = train_test_split(jv2, risk_targets, test_size=0.2, random_state=42)
    m2 = Ridge(alpha=1.2)
    m2.fit(Xtr2, ytr2)
    p2 = np.clip(m2.predict(Xte2), 0.0, 1.0)
    print(f"\n=== WITHOUT RESUMES IN CORPUS ===")
    print(f"Train R2:  {r2_score(ytr2, np.clip(m2.predict(Xtr2), 0, 1)):.4f}")
    print(f"Test  R2:  {r2_score(yte2, p2):.4f}")
    print(f"Test  MAE: {mean_absolute_error(yte2, p2):.4f}")

    # Try a simpler model: use only numeric features directly
    numeric_cols = [
        "experience_required_years", "avg_salary_usd", "task_repetition_level",
        "creativity_requirement", "physical_labor_level", "analytical_complexity",
        "social_interaction_level", "skill_complexity_score", "communication_requirement",
        "domain_specific_knowledge_level", "team_collaboration_level",
    ]
    numeric_data = automation[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0).values
    Xtr3, Xte3, ytr3, yte3 = train_test_split(numeric_data, risk_targets, test_size=0.2, random_state=42)
    m3 = Ridge(alpha=1.2)
    m3.fit(Xtr3, ytr3)
    p3 = np.clip(m3.predict(Xte3), 0.0, 1.0)
    print(f"\n=== NUMERIC FEATURES ONLY ===")
    print(f"Train R2:  {r2_score(ytr3, np.clip(m3.predict(Xtr3), 0, 1)):.4f}")
    print(f"Test  R2:  {r2_score(yte3, p3):.4f}")
    print(f"Test  MAE: {mean_absolute_error(yte3, p3):.4f}")


if __name__ == "__main__":
    main()
