# Human task-exposure rubric (human-task-exposure-v2.0)

Use this rubric **only** for the independent human-review track. Do not copy `automation_risk_score`. Do not paste Frey–Osborne occupation probabilities onto task rows. Do not treat provisional AI weak-supervision scores as human ground truth.

Call the result a **contextual task-exposure estimate**. It is not personal job-loss risk, employment probability, or the probability that a person will lose their job.

`rubric_version`: `human-task-exposure-v2.0`

Score the **O\*NET task statement**, not the occupation title alone.

## Allowed scores

Reviewers must use **only** these logical values. A blank cell means unscored, not zero.

| Score | Meaning |
|---|---|
| 0.00 | Primarily physical, interpersonal, situational, or judgment-heavy work with little realistic automation exposure |
| 0.25 | Some routine or information-processing components, but substantial human context remains necessary |
| 0.50 | A meaningful mixture of automatable and human-dependent components |
| 0.75 | Mostly structured, repetitive, or digitally mediated work that could be substantially assisted or transformed |
| 1.00 | Highly structured, repeatable, digitally accessible task with limited context dependence and strong potential for automation assistance |

Do not invent off-grid values. Do not convert blank to `0.00`. If no human reviewer assigns `1.00`, document that the upper category is unobserved. Do not fabricate `1.00` labels.

## Reviewer identifiers

Assigned project IDs (do not invent personal names):

- Reviewer 1: `HUMAN_REVIEWER_A`
- Reviewer 2: `HUMAN_REVIEWER_B`
- Third reviewer: `HUMAN_REVIEWER_C`

Do not use `AI_1`, `unknown`, `reviewer`, or `test`.

## Reviewer confidence

Store exactly one of these lowercase values (blank until the row is scored):

| Value | Meaning |
|---|---|
| `high` | The task wording clearly supports the selected score. |
| `medium` | The task is reasonably interpretable but contains some uncertainty. |
| `low` | The task is ambiguous, underspecified, or needs adjudication. |

Do not use `1-5`, `1/2/3`, `High`/`Medium`/`Low`, or `certain`/`uncertain`. When confidence is `low`, explain the uncertainty in `reviewer_notes`.

## Required considerations

For every task, consider (do not output extra numeric sub-scores unless a later template asks):

- routine / repetitive nature
- digital accessibility
- rule-based structure
- need for physical presence
- need for empathy / interpersonal interaction
- contextual judgment
- responsibility / accountability
- exception handling
- consequence of errors
- availability of digital tools

## Blind independent review

1. Reviewer 1 (`HUMAN_REVIEWER_A`) independently scores the Reviewer 1 worksheet.
2. Reviewer 2 (`HUMAN_REVIEWER_B`) independently scores the same tasks without seeing Reviewer 1's scores.
3. The third reviewer (`HUMAN_REVIEWER_C`) independently scores the designated 60-task subset without seeing either reviewer's scores.
4. All independent scores are locked and preserved (`reviewer_score` on each worksheet; later `reviewer_1_score`, `reviewer_2_score`, `third_reviewer_score`).
5. Only after independent scoring is complete may the adjudication view be used.
6. Do not fill `adjudicated_exposure_score` during the blind pass.
7. Worksheets must not add, delete, duplicate, or reorder rows. Do not change `task_id`, occupation fields, `soc_code`, `soc_major_group`, `task_text`, split, or source metadata.

## Adjudication (after all independent scores exist)

- Exact agreement (difference `0`): keep the shared Reviewer 1 / Reviewer 2 score.
- Difference of `0.25`: mean, then snap to the nearest allowed value; ties keep the **lower** exposure.
- Difference of `0.50` or more: third / senior reviewer may participate in adjudication.
- Ambiguous tasks: mark `uncertain` / `needs_adjudication`. Do not auto-convert every disagreement into a score.
- Unresolved rows are excluded from training.

`third_reviewer_score` is the third reviewer's original independent score. It must **never** be overwritten by `adjudicated_exposure_score`. Keep those fields distinct.

Record `reviewer_1_score`, `reviewer_2_score`, `third_reviewer_score`, `adjudicated_exposure_score`, `adjudication_reason`, `agreement_status`.

Quadratic weighted kappa between **AI passes** is not human inter-rater reliability.

Do not import BLS employment values, Frey–Osborne occupation probabilities, AI-generated scores, or other external automation estimates as human labels.
