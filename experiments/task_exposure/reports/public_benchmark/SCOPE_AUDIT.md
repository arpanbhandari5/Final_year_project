# Read-only scope audit (2026-10-03)

No retraining. Existing experiment artifacts were not overwritten.

## Confirmed

1. The classifier used **all 923** labelled occupations (646+138+139).
2. Split is **646 / 138 / 139** occupations and **13,453 / 2,941 / 2,871** tasks.
3. The 800-occupation selection was **not** the training set. It appears only in coverage comparison.
4. 800-occupation path: `project_data/occupation_selection/occupation_master_800.csv` (SHA-256 `26eeee1a06e4919eaf699f7a9da2d0a5f417e625f4d968326ef12daec93c4aa5`)
5. Public benchmark used by the model: `experiments/task_exposure/data/public_benchmark/public_gpts_are_gpts_benchmark.csv` (SHA-256 `bfc3b219d132449a17105dfc6efc2f0254a3dc613f6192405741c36be10d1299`; raw `full_labelset.tsv` SHA-256 `094378905e1f3349e50a9a83dc69643a2ef227954d611c8316a46da08cb3d8de`).
6. Occupation overlaps in `split_manifest.json` are empty.
7. Held-out metrics in `model_evaluation.json` are for 139 test occupations / 2,871 tasks from the 923-occupation population.
8. Reports do **not** name the experiment an 800-occupation model; coverage text mentioned 800 matches. This architecture pass labels 800 as product subset only.
9. The 800 subset can be used for product summaries without overwriting the 923 experiment.

Formal name: **GPTs-are-GPTs public benchmark — 923 occupations**.
