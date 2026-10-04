# Human Round-1 300-task sample (3 tasks per occupation)

rubric_version `human-task-exposure-v2.0`. Scores are blank. Do not invent labels.

Assigned reviewer IDs:

- Reviewer 1: `HUMAN_REVIEWER_A` (`task_exposure_human_round1_reviewer1.csv`)
- Reviewer 2: `HUMAN_REVIEWER_B` (`task_exposure_human_round1_reviewer2.csv`; must not see reviewer 1 scores)
- Third reviewer: `HUMAN_REVIEWER_C` (`task_exposure_human_round1_third_reviewer.csv`, 60-task independent subset)

Confidence, when a human later scores a row, must be exactly `high`, `medium`, or `low`.

`third_reviewer_score` is stored separately from `adjudicated_exposure_score`. Do not overwrite independent third-reviewer scores during adjudication.

Row identity and order are frozen in `task_exposure_human_round1_identity_lock.json` (`task_id` plus occupation/SOC/task text/split). Do not add, delete, duplicate, or reorder rows.

- sample: `task_exposure_human_round1_sample.csv` (300 rows, 100 occupations, 22 SOC major groups)
- frozen occupation splits: `task_exposure_human_round1_occupation_splits.csv` {'train': 70, 'validation': 15, 'test': 15}

No occupation appears in more than one split.
Unresolved or blank scores are excluded from training.
Do not import BLS, Frey–Osborne, AI, or other external estimates as human labels.
