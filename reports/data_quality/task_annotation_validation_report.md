# Task annotation validation report

Generated at: 2026-10-02T08:35:40.462556+00:00

Authoritative 250-task sample: `project_data/task_exposure_labels/task_exposure_250_sample.csv`.
Worksheets matched the sample on occupation_code, task_id, task_statement, and row order before scoring.
The original sample file was not modified.

| check | value |
| --- | --- |
| sample rows | 250 |
| SOC groups | 22 |
| occupations | 225 |
| duplicate task_id | 0 |
| pass1 rows | 250 |
| pass2 rows | 250 |
| blank pass1 | 0 |
| blank pass2 | 0 |
| invalid logical scores | 0 |
| format canonicalizations | 143 |
| sample sha256 | ee11175252ac6aac5a7808e6b5b2a4e9fcedff42d58b99e8bf6ce7395f642c40 |
| rubric sha256 | e6f1118e071dec3699de25692f76f5bb9659c1e5b2d3c1f1d3c8bf5061b0e057 |
| allowed-scores sha256 | fb650f11afbbb8cd8e0569b22f290ea7b7aa29561b8f6642c6c1283e3fdd1704 |

## Provenance

- Scoring date: 2026-10-02
- Pass 1: isolated Cursor subagent, inherit model (parent: Cursor Grok 4.6; exact subagent build unavailable)
- Pass 2: separate isolated Cursor subagent, inherit model; instructed not to read pass 1
- These are AI assessments, not human reviews.
- Format-only canonicalization: `0.0`/`0.5`/`1.0` written as `0.00`/`0.50`/`1.00`. Logical value unchanged. Not rounding of off-grid scores.

Format corrections: 143 (all equivalent Decimal values).

## Validation outcome

PASS. No unresolved invalid scores. Missing scores were not converted to 0.00.

