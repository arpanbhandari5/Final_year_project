# Final task-training table report

Generated at: 2026-10-02T09:31:09.498310+00:00

- Output: `project_data/task_exposure_labels/final_validated_task_training_table.csv`
- Occupation map: `project_data/task_exposure_labels/task_group_occupation_map.csv`
- SHA-256 final table: `a6cdd93505e7145dd37b5bc005af2e26a5c28ef04f5cd9520edd79793b832a4d`

| count | value |
| --- | --- |
| original tasks | 250 |
| unique normalized task groups | 248 |
| duplicate groups (size>1) | 2 |
| rows in duplicate groups | 4 |
| conflicting duplicate groups excluded | 0 |
| unresolved groups excluded | 0 |
| final eligible training rows (one per task group) | 248 |
| excluded source rows | 0 |

The target column is a **provisional AI weak-supervision score**, not human ground truth.
BLS Employment Projections 2025–35 are demand context only and are not in this table.

Future splits must keep all rows sharing `split_key` (`task_group_id`) in the same partition.
No train/test partitions were created. No model was trained.

