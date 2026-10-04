# Task-exposure labelling rubric (round-1 250-task sample)

Use this rubric only for the **task-level expert-review** track. Do not copy `automation_risk_score`. Do not paste Frey–Osborne occupation probabilities onto task rows.

Call the result a **contextual task-exposure estimate**. Do not call it personal job-loss risk or employment probability.

## Question

Given this O*NET task statement, how exposed is **the task** (not the person) to current computerisation or AI substitution, assuming typical tools available to U.S. workers in this occupation?

## Required discrete scores

Reviewers must use **only** these logical values. Do not write 0.00 unless the task truly has no exposure. A blank cell means unscored, not zero.

| Score | Meaning | Example |
|---|---|---|
| 0.00 | No exposure (physical / in-person dependent) | Operate welding machinery on structural steel. |
| 0.25 | Low exposure (AI assistive / minimal) | Inspect plumbing systems for leakages. |
| 0.50 | Partial exposure / augmentation | Draft commercial lease agreements. |
| 0.75 | High exposure (AI-dominant with human oversight) | Convert database schemas from SQL to PostgreSQL. |
| 1.00 | Full exposure / direct automation | Summarize standard meeting transcripts into bullet points. |

If both reviewers pick the same logical value, keep that value.
If they differ by 0.25 or less, store the mean and snap the stored `adjudicated_exposure_score` to the nearest logical value (ties keep the lower exposure).
Do not invent scores. Do not use 0.37, 0.6, or other off-grid numbers as reviewer scores.

| Score | Meaning | Example |
|---|---|---|
| 0.00 | No exposure (physical / in-person dependent) | Operate welding machinery on structural steel. |
| 0.25 | Low exposure (AI assistive / minimal) | Inspect plumbing systems for leakages. |
| 0.50 | Partial exposure / augmentation | Draft commercial lease agreements. |
| 0.75 | High exposure (AI-dominant with human oversight) | Convert database schemas from SQL to PostgreSQL. |
| 1.00 | Full exposure / direct automation | Summarize standard meeting transcripts into bullet points. |

Blank is not zero. Leave a cell empty only if the task cannot be scored from the statement.

## Blind review

1. Reviewer 1 uses only `annotation_reviewer1.csv`.
2. Reviewer 2 uses only `annotation_reviewer2.csv`.
3. Do not share or discuss scores until all 250 rows are complete.
4. Do not fill `adjudicated_exposure_score` during the blind pass.

## Agreement and adjudication (after both files are complete)

Run `scripts/data_pipeline/compute_annotation_agreement.py`.

- Discrepant: `|reviewer_1_score - reviewer_2_score| > 0.30`
- If quadratic weighted kappa ≥ 0.70: average non-discrepant rows; adjudicate remaining discrepant rows.
- If kappa < 0.70: adjudicate all discrepant rows, refine criteria, and re-score discordant tasks.

Non-discrepant rows:

- `adjudicated_exposure_score = (r1 + r2) / 2`
- `label_confidence = 1.0 - (score_diff * 0.5)`
- `label_source = human_consensus_average`

Discrepant rows after human discussion:

- Set one agreed `adjudicated_exposure_score`
- `label_confidence = 0.80` if consensus was quick, else `0.60`
- Write `label_notes`
- `label_source = human_adjudicated_consensus`

## Forbidden sources

- `data/automation_risk.csv` / `automation_risk_score`
- Silent fuzzy occupation matching
- Treating Frey–Osborne `prob` as a task label
- Invented or model-generated scores
