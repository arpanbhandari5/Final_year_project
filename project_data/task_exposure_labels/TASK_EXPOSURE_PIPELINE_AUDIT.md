# Task-exposure pipeline audit

Generated at: 2026-10-02T09:31:09.518267+00:00
Backup of previous derived outputs: `project_data/task_exposure_labels/_backups/20261002T093101Z`

## Verified facts vs assumptions

- **Verified:** sample has 250 rows, 22 SOC groups, 225 occupations, 0 duplicate task_id, 0 empty task statements, all sample score fields blank.
- **Verified:** two JSONL pass files exist, each 250 task_ids matching the sample, all scores on the permitted grid, 0 blanks. Pass 1 stores scores as strings; pass 2 as JSON numbers.
- **Verified:** reviewer CSVs match JSONL logical scores and sample task identity. Reviewer IDs are `ai_pass_1` / `ai_pass_2`. Adjudicated columns in reviewer worksheets remain blank.
- **Assumption (not re-verified here):** the JSONL files were produced by two isolated Cursor subagents instructed not to read each other. Files alone cannot prove process isolation.
- **Verified:** these are AI labels. They are **not** human-validated ground truth.

## Input files

| file | sha256 | bytes |
| --- | --- | --- |
| project_data/task_exposure_labels/task_exposure_250_sample.csv | ee11175252ac6aac5a7808e6b5b2a4e9fcedff42d58b99e8bf6ce7395f642c40 | 51600 |
| project_data/task_exposure_labels/ai_pass1_scores.jsonl | f75e3752f450865c255ac5d1f2687afd1099846d55cf9d18d5f39e68565da777 | 66344 |
| project_data/task_exposure_labels/ai_pass2_scores.jsonl | 1c98d2305559b27a1d10fd9f5c2a0d65842f5de85595b652165b7c8294d7267b | 62039 |
| project_data/task_exposure_labels/annotation_reviewer1.csv | 75a5eb548ddc125b2b915bd8c131e8513f95b6df02da510055ebc0c2ec8ad8ea | 92756 |
| project_data/task_exposure_labels/annotation_reviewer2.csv | badbdb57cb982a29b02a319aa79db221cdb831f6046339783383c4bf07f27959 | 89652 |
| replacement_data/TASK_LABELING_RUBRIC.md | 86652f977755b49aa815aeaf46e347478b37b5eaeb188840d393c3bee95a3353 | 3517 |

## Agreement (same 250 complete pairs for every metric)

| metric | value |
| --- | --- |
| paired complete | 250 |
| exact agreement | 0.8240 |
| MAD | 0.0440 |
| quadratic weighted kappa | 0.9120 |
| Gwet AC1 (nominal) | 0.7854 |
| threshold (quadratic kappa >= 0.70) | met |
| |r1-r2| > 0.30 | 0 |

Threshold used: quadratic weighted kappa. Meeting 0.70 does not validate labels.
Case C independent adjudication was not required (0 pairs with |diff| > 0.30).

## Resolution counts

| method | n |
| --- | --- |
| identical | 206 |
| deterministic_mean_snap | 44 |
| ai_adjudicated | 0 |
| unresolved/incomplete | 0 |

## Deduplication

| item | n |
| --- | --- |
| task groups | 248 |
| duplicate groups | 2 |
| conflicts excluded | 0 |
| unresolved groups excluded | 0 |
| final training rows | 248 |
| occupation-map rows | 250 |
| excluded source rows | 0 |

## BLS demand sidecar (not a label)

| item | value |
| --- | --- |
| status | written |
| rows | 1117 |
| path | external_data/normalized/bls_employment_projections/bls_occupation_demand_features_2025_2035.csv |

## Validation

PASS

Source annotation files were not modified. Blanks were not converted to 0.00. No model was trained. No git operations were performed.

## Rerun

```
python scripts/data_pipeline/build_final_task_training_table.py
python scripts/data_pipeline/build_final_task_training_table.py --validate-only
python -m pytest tests/test_task_exposure_pipeline.py
```

