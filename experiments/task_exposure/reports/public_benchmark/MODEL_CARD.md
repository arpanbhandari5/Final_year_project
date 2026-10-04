# Model card: prayash-task-exposure-gpts-are-gpts-v1

## Production vs research

Prayash currently implements production E0/E1/E2 task-exposure analysis as a verified benchmark lookup system. A matched occupation is resolved to a verified occupation/SOC code, its published task-level E0/E1/E2 labels are retrieved, and task-share distributions are calculated deterministically from those labels.

The current production system is not a generalizing E0/E1/E2 classifier.

The trained TF-IDF task-exposure classifier is retained as a separate research and model-development component. It is used for offline experimentation and evaluation of whether E0/E1/E2 task categories can be generalized to previously unseen task descriptions or occupations. Its predictions are not treated as published benchmark labels. Grouped-CV/test metrics below describe the **research classifier only**. They do not describe lookup accuracy, personal employment outcomes, or production performance.

Published benchmark label ≠ TF-IDF model prediction.

## Model identity

- Name: GPTs-are-GPTs public benchmark classifier
- Version id: `prayash-task-exposure-gpts-are-gpts-v1`
- Status: **research-only** (not a production employment-risk model)

## Population

- 923 occupations
- 19,265 task rows
- Source: `openai/GPTs-are-GPTs` commit `0471612fef3cc22b74fb884d27bff9dbd3770582`
- Source file SHA-256: `094378905e1f3349e50a9a83dc69643a2ef227954d611c8316a46da08cb3d8de`
- Derived dataset: `experiments/task_exposure/data/public_benchmark/public_gpts_are_gpts_benchmark.csv`
- Derived SHA-256: `bfc3b219d132449a17105dfc6efc2f0254a3dc613f6192405741c36be10d1299`

The 800-occupation file is a **product coverage subset**, not this model's training population.

## Target

- Field: `human_labels`
- Classes: E0 (no direct LLM exposure), E1 (direct LLM exposure), E2 (exposure through an LLM-powered application)
- Not used as target: `gpt4_exposure`, `gpt4_exposure_alt_rubric`, `gpt4_automation`
- Not converted to 0.00 / 0.25 / 0.50 / 0.75 / 1.00

## Data provenance

Human-derived benchmark labels are the published `human_labels` values.

They are **not** the same as:

- Prayash-created human labels
- independent direct human review of every released task row

The source methodology describes human annotation of detailed work activities and a subset of O*NET tasks, with aggregation to task and occupation levels. Direct task-level human annotation count: **not separately recoverable from the released file**.

## Evaluation

Occupation-held-out split (seed 202610031):

| Split | Occupations | Tasks |
|---|---|---|
| Train | 646 | 13,453 |
| Validation | 138 | 2,941 |
| Test | 139 | 2,871 |
| Total | 923 | 19,265 |

Occupation overlaps: train∩val = empty; train∩test = empty; val∩test = empty.

Hyperparameters (C) selected with GroupKFold on **training occupations only**.

Held-out test metrics (do not recompute here; from `model_evaluation.json` generated 2026-10-03T04:35:55Z):

| Model | Accuracy | Balanced acc | Macro-F1 | Weighted-F1 | MCC |
|---|---|---|---|---|---|
| Majority | 0.546 | 0.333 | 0.235 | 0.385 | 0.000 |
| Stratified dummy | 0.398 | 0.324 | 0.324 | 0.399 | −0.020 |
| TF-IDF + Logistic Regression (C=1.0) | 0.735 | 0.633 | 0.650 | 0.723 | 0.534 |
| TF-IDF + Linear SVM (C=1.0) | 0.726 | 0.640 | 0.652 | 0.719 | 0.522 |

Logistic Regression per-class F1: E0 0.835, E1 0.465, E2 0.650.

**E1 performance is weaker than E0 and E2 in the reported evaluation.**

Logistic Regression log loss 0.634; multiclass ROC-AUC 0.866. Linear SVM class probabilities are unavailable (not reported as zero). Confusion matrices: `confusion_matrix.csv`. Fold mean/std: `model_evaluation.json`.

Text features associated with predictions are **model-derived textual associations**, not causal drivers of employment outcomes.

Classifier `model_score` / `decision_score` values, when present, are uncalibrated decision scores for task-text classification. They are not calibrated probabilities and are not confidence that a worker will lose their job.

## Limitations

- The benchmark measures task-level/contextual exposure under the published taxonomy.
- It does not measure individual employment outcomes.
- It does not predict personal job loss.
- It does not establish causal effects of AI adoption.
- E1 is the weakest class in the reported evaluation.
- Human-label provenance is not independent direct review of every released row.
- Product 800 coverage is not the same as the 923 model population.
- Not integrated into production scoring.
