# AI-pilot score distribution (before any experimental training)

Source files: `task_exposure_250_sample.csv` + `task_exposure_adjudication.csv`.
Sample keys match both reviewer worksheets. 250 tasks, 22 SOC groups, 225 occupations, 0 duplicate `task_id`. Original sample left blank on adjudicated columns.

These counts are **provisional AI weak supervision**, not human-validated ground truth.

## Overall adjudicated scores

| Score | n |
|---|---|
| 0.00 | 87 |
| 0.25 | 67 |
| 0.50 | 81 |
| 0.75 | 15 |
| 1.00 | 0 |

Reviewer 2 assigned **three** `1.00` scores; after identical/mean-snap adjudication none remained at `1.00` (they were pulled down by a lower pass-1 score). The empty top bin is therefore partly **conservative snapping**, not only sample composition.

## By SOC major group (adjudicated)

Highest `0.00` counts: 51 (21), 47 (11), 49 (9), 29 (9). Highest `0.75` counts: 15 (3), 25 (3), 43 (3), 13 (2). Physical/production SOC groups dominate low scores; computer/math and education have more mid/high scores. That pattern is consistent with a conservative physical-vs-digital rubric, but it is not proof of real-world exposure.

## By task type

| task_type | 0.00 | 0.25 | 0.50 | 0.75 |
|---|---|---|---|---|
| Core | 61 | 56 | 63 | 13 |
| Supplemental | 26 | 11 | 16 | 2 |
| n/a | 0 | 0 | 2 | 0 |

## By adjudication status

| status | 0.00 | 0.25 | 0.50 | 0.75 |
|---|---|---|---|---|
| identical | 70 | 61 | 63 | 12 |
| deterministic_mean | 17 | 6 | 18 | 3 |

## Task length (characters)

Mean length is similar across scores (~87–104). Length does not explain the missing `1.00` bin.

## Reviewer distributions

- Pass 1: 0.00=86, 0.25=67, 0.50=81, 0.75=16, 1.00=0
- Pass 2: 0.00=71, 0.25=78, 0.50=69, 0.75=29, 1.00=3

Pass 2 used the top category; pass 1 never did. Combined labels inherit the more conservative pass.

## Source file

All rows come from `project_data/task_exposure_labels/task_exposure_250_sample.csv` (O*NET 31.0 task statements). No BLS or historical Frey–Osborne values were copied into these scores.
