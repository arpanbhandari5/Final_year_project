Provisional AI weak-supervision labels live here after
`scripts/data_pipeline/build_final_task_training_table.py`.

Do not invent scores. Do not copy `automation_risk_score` or Frey–Osborne probabilities.
Do not treat these files as human-validated ground truth or personal job-loss risk.

Canonical sample (scores blank): `task_exposure_250_sample.csv`
Source AI passes (do not overwrite): `ai_pass1_scores.jsonl`, `ai_pass2_scores.jsonl`
Training target table: `final_validated_task_training_table.csv`
Audit: `TASK_EXPOSURE_PIPELINE_AUDIT.md`
