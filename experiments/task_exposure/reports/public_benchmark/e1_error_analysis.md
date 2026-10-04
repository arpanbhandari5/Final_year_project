# E1 error analysis (read-only)

Does not retrain the public-benchmark classifier. Does not invent labels.

## Test-set confusion (TF-IDF + Logistic Regression, preserved matrix)

- E1 support (test): 431
- E1 correct: 151
- E1 predicted as E0 (false negatives toward E0): 107
- E1 predicted as E2 (false negatives toward E2): 173
- E0 predicted as E1 (false positives from E0): 22
- E2 predicted as E1 (false positives from E2): 45
- E1 false negatives total: 280
- E1 false positives total: 67
- Logistic Regression E1 precision/recall/F1: 0.693 / 0.350 / 0.465

E1 performance is weaker than E0 and E2 in the reported evaluation. This is an observed metric pattern, not a causal claim.

## Class imbalance (full 19,265-row benchmark)

- E0: 10256
- E1: 2862
- E2: 6147

## Task length (characters, full benchmark)

- E0 mean/median: 96.2 / 92.0
- E1 mean/median: 98.5 / 93.0
- E2 mean/median: 100.3 / 96.0

- Duplicate task_text rows: 1273
- Duplicate normalized task_text rows: 1274

## SOC major groups with lowest preserved macro-F1

| soc_major_group | n_tasks | n_occupations | accuracy | macro_f1 |
|---|---|---|---|---|
| 45 | 22 | 1 | 0.409 | 0.258 |
| 37 | 10 | 1 | 0.800 | 0.296 |
| 23 | 51 | 3 | 0.529 | 0.316 |
| 21 | 19 | 1 | 0.368 | 0.321 |
| 47 | 218 | 11 | 0.917 | 0.469 |

## Limitation

Row-level test predictions were not archived next to the confusion matrix. Occupation-group E1 rates and example misclassified task strings cannot be listed without retraining. This analysis uses the preserved confusion matrix, per-class CSV, SOC-group metrics, and full benchmark text statistics only.

Recommended future experiments (not executed here): class weights; character n-grams; additional independent labels; calibration.
