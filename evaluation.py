from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RepeatedKFold

from train_model import build_risk_pipeline

from utils import build_job_text, build_resume_text, read_csv_any


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
