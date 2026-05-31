from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def read_csv_any(*relative_paths: str) -> pd.DataFrame:
    for relative_path in relative_paths:
        candidate = DATA_DIR / relative_path
        if candidate.exists():
            frame = pd.read_csv(candidate, sep=None, engine="python")
            frame.columns = [normalize_text(column) for column in frame.columns]
            return frame
    raise FileNotFoundError(f"None of the expected files were found: {', '.join(relative_paths)}")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.lower() == "nan" else text


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
    return [part for part in parts if part]


def build_job_text(row: pd.Series) -> str:
    pieces = [
        row.get("job_role", ""),
        row.get("industry", ""),
        row.get("education_level", ""),
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
        " ".join(parse_listish(row.get("skills"))),
        " ".join(parse_listish(row.get("related_skils_in_job"))),
        " ".join(parse_listish(row.get("responsibilities"))),
        " ".join(parse_listish(row.get("responsibilities.1"))),
        " ".join(parse_listish(row.get("skills_required"))),
        " ".join(parse_listish(row.get("professional_company_names"))),
        " ".join(parse_listish(row.get("positions"))),
        " ".join(parse_listish(row.get("role_positions"))),
        " ".join(parse_listish(row.get("major_field_of_studies"))),
        " ".join(parse_listish(row.get("certification_skills"))),
    ]
    return normalize_text(" ".join(normalize_text(piece) for piece in pieces if normalize_text(piece)))


def build_training_frame() -> tuple[list[str], np.ndarray]:
    automation = read_csv_any("automation_risk.csv")
    resumes = read_csv_any("resume_corpus.csv")
    job_texts = [build_job_text(row) for _, row in automation.iterrows()]
    resume_texts = [build_resume_text(row) for _, row in resumes.iterrows()]
    corpus = [*job_texts, *resume_texts]
    vectorizer = TfidfVectorizer(max_features=7000, ngram_range=(1, 2), stop_words="english")
    vectorizer.fit(corpus)
    return job_texts, vectorizer


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

    kfold = KFold(n_splits=5, shuffle=True, random_state=42)
    metrics = []
    for train_index, test_index in kfold.split(job_vectors):
        X_train, X_test = job_vectors[train_index], job_vectors[test_index]
        y_train, y_test = risk_targets[train_index], risk_targets[test_index]
        model = Ridge(alpha=1.2)
        model.fit(X_train, y_train)
        predictions = np.clip(model.predict(X_test), 0.0, 1.0)
        mse = mean_squared_error(y_test, predictions)
        metrics.append(
            {
                "mae": mean_absolute_error(y_test, predictions),
                "rmse": float(np.sqrt(mse)),
                "r2": r2_score(y_test, predictions),
            }
        )

    print("Evaluation metrics (5-fold cross-validation)")
    print(f"MAE:  {np.mean([row['mae'] for row in metrics]):.4f}")
    print(f"RMSE: {np.mean([row['rmse'] for row in metrics]):.4f}")
    print(f"R^2:  {np.mean([row['r2'] for row in metrics]):.4f}")


if __name__ == "__main__":
    main()
