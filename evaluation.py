from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

from utils import build_job_text, build_resume_text, read_csv_any


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
