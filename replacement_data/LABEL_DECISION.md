# Replacement Dataset Sources and Label Decision

This file records the approved sources and the two-track label policy. It does not train a model and does not invent task scores.

## O*NET 31.0

- Database page: https://www.onetcenter.org/database.html
- Occupation dictionary: https://www.onetcenter.org/dictionary/31.0/csv/occupation_data.html
- Official text archive: https://www.onetcenter.org/dl_files/database/db_31_0_text.zip
- Local raw file: `external_data/raw/onet_31_0/onet_31_0_text.zip`
- Extracted folder: `external_data/raw/onet_31_0/db_31_0_text/`
- Licence: CC BY 4.0 (O*NET 31.0 Database)
- Join key: `O*NET-SOC Code` (never title-only joins)
- Expected occupation dictionary size: 1,016 rows (`O*NET-SOC Code`, `Title`, `Description`)
- Expected task statements: 18,838 rows

Required attribution:

> This product includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA. The project modified or aggregated some of this information. USDOL/ETA has not approved, endorsed, or tested these modifications.

## External historical occupation label

- Methodology: Frey, C. B., & Osborne, M. A. (2013/2017), *The Future of Employment: How Susceptible Are Jobs to Computerisation?*
- Oxford Martin source page: https://www.oxfordmartin.ox.ac.uk/publications/the-future-of-employment
- Public 702-row table: https://raw.githubusercontent.com/plotly/datasets/master/job-automation-probability.csv
- Local raw file: `external_data/raw/historical_benchmark/frey_osborne_historical_702_occupations.csv`

Exact mapping rule only:

1. Read the Plotly table `soc` (or equivalent SOC-like) codes.
2. Append `.00`.
3. Join to O*NET 31.0 `O*NET-SOC Code`.
4. Keep unmatched rows in a separate file.
5. Do not silently fuzzy-match the remaining codes.

Expected split: 618 exact mappings, 84 unmatched. Recount from the files; do not assume.

Metadata for this track:

- `label_type=historical_occupation_computerisation_probability`
- `label_source=Frey_Osborne`
- `label_year=2013/2017`
- `source_artifact=plotly_public_mirror`
- `not_current_task_ground_truth=true`

This is an older occupation-level computerisation estimate. It is not a personal probability, not current task-level ground truth, and not a replacement for `data/automation_risk.csv` as a new production target.

## OECD caution

- https://www.oecd.org/en/publications/the-risk-of-automation-for-jobs-in-oecd-countries_5jlz9h56dvq7-en.html

Occupation-based estimates can overestimate automatability because occupations contain heterogeneous tasks. Frey–Osborne labels must not be copied onto O*NET task statements and presented as current task-level labels.

## Two label tracks (keep separate)

1. **Historical occupation benchmark** — mapped Frey–Osborne probability for external comparison only.
2. **Task-level expert-review template** — one row per O*NET task with blank independent exposure fields, completed later with a written rubric and at least two reviewers.

Until track 2 is completed and evaluated, application wording must describe a **contextual occupational exposure estimate** or a **historical benchmark comparison**, never a validated automation prediction, personal job-loss risk, or employment probability.

## Active external-benchmark track (research-only)

A third, isolated track uses the published GPTs-are-GPTs `human_labels` (E0/E1/E2) on 923 occupations. That taxonomy does **not** validate track 2's five-level rubric. See `experiments/task_exposure/reports/public_benchmark/ARCHITECTURE.md`.
