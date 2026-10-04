# Human-label experimental evaluation protocol

Do not run until `task_exposure_human_round1_trainable.csv` contains adjudicated human scores.

Required comparisons (occupation-grouped; test occupations frozen before training):

- training-fold global mean baseline
- training-fold global median baseline
- TF-IDF + Ridge
- at least one of TF-IDF + ElasticNet or linear SVR
- optional structured O*NET features and text + structured features

Report pooled and fold-level MAE, RMSE, and R². Report held-out **human-reviewed** test metrics **separately** from the 248-row AI weak-supervision experiment. Never average those tracks.

Subgroup metrics must include sample size. Do not rank occupations. Do not claim personal job-loss probability.

Use `python scripts/data_pipeline/evaluate_human_task_exposure_gate.py` to confirm the data gate.
