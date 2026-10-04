# Human task-exposure track status

Conceptual status of the existing 248-row table:

`baseline_provisional_ai_weak_supervision`

That file was **not renamed**. Keep using `task_exposure_training.csv` for pipeline, leakage, and error-analysis demonstrations only.

Do not mix it silently with human-reviewed rows. Do not claim human ground truth. Do not use it for production risk scoring or personal job-loss prediction.

The 250-row one-task-per-occupation worksheets remain a separate earlier sample geometry. The human-v2 track uses 3–5 tasks per occupation.

Assigned reviewer IDs: `HUMAN_REVIEWER_A`, `HUMAN_REVIEWER_B`, `HUMAN_REVIEWER_C`. Confidence values, when entered by humans, must be exactly `high`, `medium`, or `low`. `third_reviewer_score` stays separate from `adjudicated_exposure_score`.

Project-specific human review status: `deferred_due_to_unavailable_independent_reviewers`. Do not fill the Round 1 worksheets with public GPTs-are-GPTs labels.

The active external-benchmark model is `prayash-task-exposure-gpts-are-gpts-v1` on **923 occupations**. The **800-occupation** file is product coverage only. The five-level 0.00–1.00 rubric is historical/deferred and is not validated by E0/E1/E2.

Evaluator and experimental reports under `experiments/task_exposure/reports/model_evaluation/` and `error_analysis/` remain the 248-row demonstration track. New architecture docs live under `experiments/task_exposure/reports/public_benchmark/`.
