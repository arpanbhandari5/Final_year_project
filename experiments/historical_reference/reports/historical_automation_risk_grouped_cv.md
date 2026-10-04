# Historical automation-risk grouped CV (isolated)

Corrected, leakage-aware re-evaluation. **Not** a direct improvement claim over the original production model.

This is a corrected, leakage-aware re-evaluation of the historical occupation-level automation_risk_score. It is not a personal job-loss, unemployment, or replacement probability.

## Exact old metric reproducible

NO.

evaluation.py still imports missing train_model.build_risk_pipeline; ml_models/model.pkl has no out-of-fold predictions or split manifest (reports/data_quality/historical_baseline_reproducibility.json).

- Dataset: `C:\4th project\data\automation_risk.csv`
- SHA-256: `d28ca4cbc2ca746c9a033d1953d49d565c3e64a2d8ae54b6ce52bed1826a18f1`
- Rows: 3000
- Unique job_role: 20
- Target: `automation_risk_score`
- Grouping: `job_role` + GroupKFold(5)
- TF-IDF fitted inside sklearn Pipeline on training folds only.

This dataset is **not** the 618-row Frey–Osborne historical occupation table and **not** the GPTs-are-GPTs benchmark.

## Pooled out-of-fold metrics

| Model | MAE | RMSE | Pooled out-of-fold R² |
|---|---|---|---|
| Training-fold mean baseline | 0.2478 | 0.2869 | -0.0001 |
| Training-fold median baseline | 0.2479 | 0.2870 | -0.0008 |
| TF-IDF + Ridge (Pipeline) | 0.2478 | 0.2870 | -0.0002 |

## Mean fold metrics

| Model | Mean fold MAE | Mean fold RMSE | Mean fold R² |
|---|---|---|---|
| Training-fold mean baseline | 0.2478 | 0.2869 | -0.0002 |
| Training-fold median baseline | 0.2478 | 0.2870 | -0.0010 |
| TF-IDF + Ridge (Pipeline) | 0.2478 | 0.2869 | -0.0004 |

Do not treat pooled R² and mean fold R² as conflicting values; they answer different aggregations.
