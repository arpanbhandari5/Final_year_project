# Round-1 stratified 250-task sample

Reproducible stratified sample from `onet_task_annotations_round_1.csv` (`random_state=42`).
All reviewer and adjudicated score fields are blank. Do not invent labels.

- Canonical sample: `project_data/task_exposure_labels/task_exposure_250_sample.csv`
- Reviewer 1 worksheet: `project_data/task_exposure_labels/annotation_reviewer1.csv`
- Reviewer 2 worksheet: `project_data/task_exposure_labels/annotation_reviewer2.csv`
- Tasks: 250
- SOC major groups: 22
- Occupations: 225
- SHA-256: `ee11175252ac6aac5a7808e6b5b2a4e9fcedff42d58b99e8bf6ce7395f642c40`

Reviewers must not share scores until all 250 rows are rated.
Run `scripts/data_pipeline/compute_annotation_agreement.py` only after both worksheets are complete.

