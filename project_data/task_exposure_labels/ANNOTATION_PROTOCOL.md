# Round-1 250-task annotation protocol

Do not train. Do not invent scores. Do not copy production `automation_risk_score`.

## Phase 1 — blind annotation

Worksheets (scores currently empty):

- `project_data/task_exposure_labels/task_exposure_250_sample.csv`
- `project_data/task_exposure_labels/annotation_reviewer1.csv`
- `project_data/task_exposure_labels/annotation_reviewer2.csv`

Each reviewer scores only their file using these **logical values only**: `0.00`, `0.25`, `0.50`, `0.75`, `1.00`.

- Blank means “not yet scored”. Blank is not `0.00`.
- Do not invent or auto-fill scores.
- After both files are complete, consensus keeps a logical rubric value (exact match, or nearest allowed value if the two scores differ by ≤ 0.30).

## Phase 2 — agreement (only after 250/250 paired scores)

```text
python scripts/data_pipeline/compute_annotation_agreement.py
```

That script exits without metrics if scores are still blank.

Outputs after a real completed pass:

- `task_exposure_250_ratings_merged.csv`
- `discrepant_tasks_for_adjudication.csv`
- `reports/data_quality/task_exposure_250_agreement_report.md`

Then humans adjudicate discrepant rows and save:

- `task_exposure_250_human_ground_truth.csv`

Do not write that ground-truth file until adjudication is finished.
