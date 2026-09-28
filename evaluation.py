from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RepeatedKFold

from train_model import build_risk_pipeline


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


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    mse = mean_squared_error(actual, predicted)
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mse)),
        "r2": float(r2_score(actual, predicted)),
    }


def evaluate_repeated_cv(automation: pd.DataFrame, repeats: int = 3) -> dict[str, dict[str, float]]:
    texts = [build_job_text(row) for _, row in automation.iterrows()]
    targets = automation["automation_risk_score"].astype(float).clip(0.0, 1.0).to_numpy()
    roles = automation["job_role"].map(normalize_text).to_numpy()
    splitter = RepeatedKFold(n_splits=5, n_repeats=repeats, random_state=42)
    predictions: dict[str, list[float]] = {name: [] for name in ("Pipeline RidgeCV", "Mean Baseline", "Median Baseline", "Role-Group Mean Baseline")}
    actual_values: list[float] = []

    for train_index, test_index in splitter.split(texts):
        train_targets = targets[train_index]
        pipeline = build_risk_pipeline()
        pipeline.fit([texts[index] for index in train_index], train_targets)
        predictions["Pipeline RidgeCV"].extend(np.clip(pipeline.predict([texts[index] for index in test_index]), 0.0, 1.0))
        mean_value = float(np.mean(train_targets))
        median_value = float(np.median(train_targets))
        role_means = {
            role: float(np.mean(train_targets[roles[train_index] == role]))
            for role in set(roles[train_index])
        }
        predictions["Mean Baseline"].extend([mean_value] * len(test_index))
        predictions["Median Baseline"].extend([median_value] * len(test_index))
        predictions["Role-Group Mean Baseline"].extend([role_means.get(roles[index], mean_value) for index in test_index])
        actual_values.extend(targets[test_index])

    actual = np.asarray(actual_values)
    return {name: _metrics(actual, np.asarray(values)) for name, values in predictions.items()}


def main() -> None:
    automation = read_csv_any("automation_risk.csv")
    results = evaluate_repeated_cv(automation)
    print("Evaluation metrics (repeated 5-fold cross-validation, 3 repeats)")
    print("Model                         MAE      RMSE     R^2")
    for name, metrics in results.items():
        print(f"{name:<29} {metrics['mae']:.4f}   {metrics['rmse']:.4f}   {metrics['r2']:.4f}")


if __name__ == "__main__":
    main()
