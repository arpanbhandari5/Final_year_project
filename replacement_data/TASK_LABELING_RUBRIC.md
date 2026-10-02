# Task-exposure labelling rubric

Use this rubric only for the **task-level expert-review** track. Do not copy `automation_risk_score`. Do not paste Frey–Osborne occupation probabilities onto task rows.

## Question

Given this O*NET task statement, how exposed is **the task** (not the person) to current computerisation or AI substitution, assuming typical tools available to U.S. workers in this occupation?

Call the result a **contextual task-exposure estimate**. Do not call it personal job-loss risk or employment probability.

## Score bands

| Range | Band |
|---|---|
| 0.00–0.20 | Minimal exposure |
| 0.21–0.40 | Low exposure |
| 0.41–0.60 | Moderate exposure |
| 0.61–0.80 | High exposure |
| 0.81–1.00 | Very high exposure |

## Evidence requirements

Each non-blank score must cite:

- the task statement itself
- occupation code and title
- optional O*NET work-activity or work-context support
- a short note on why the band was chosen

Leave scores blank when evidence is insufficient. Blank is not zero.

## Review process

- At least two independent reviewers (`reviewer_1_id`, `reviewer_2_id`).
- Each records score, confidence (0.0–1.0), date, and `label_version`.
- If absolute disagreement is greater than 0.20, a third adjudicator sets `adjudicated_exposure_score` and records the rule used.
- If disagreement is 0.20 or less, adjudicated score is the mean of the two reviewer scores unless a documented override is required.

## Forbidden sources

- `data/automation_risk.csv` / `automation_risk_score`
- Silent fuzzy occupation matching
- Treating Frey–Osborne `prob` as a task label
- Invented or model-generated scores
