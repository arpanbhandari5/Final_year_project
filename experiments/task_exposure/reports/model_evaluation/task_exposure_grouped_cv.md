# Task-exposure grouped cross-validation (experimental)

This report is produced by an isolated experimental evaluator. It is not a
production automation-risk evaluation and does not replace production models.

The target labels are provisional AI-generated weak supervision and are not human-validated ground truth, personal job-loss probabilities, or employment outcomes.

Schema and pipeline checks do not imply human validation. The table is a
schema-validated provisional AI weak-label / deduplicated task-exposure
training table.

## Dataset

- path: `C:\4th project\project_data\task_exposure_labels\task_exposure_training.csv`
- rows: 248
- unique occupations: 224
- unique tasks: 248
- outer folds: 5
- text column: `task_text`
- not_human_ground_truth all True: 1

## Target distribution

- `0.00`: 86
- `0.25`: 66
- `0.50`: 81
- `0.75`: 15
- `1.00`: 0

## Label source

- `provisional_ai_weak_supervision`: 248

## Resolution method

- `identical_scores`: 205
- `deterministic_mean_snap`: 43

Absence of the `1.00` class, if observed, is a distribution fact rather than a
validation failure.

## Configuration

- evaluator version: 1.1.0
- schema version: 1.1.0
- alpha candidates: [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
- TF-IDF: {"ngram_range": [1, 2], "min_df": 1, "sublinear_tf": 1, "max_features": 12000, "stop_words": "english"}
- model: {"estimator": "Ridge", "fit_intercept": 1}
- splitter: GroupKFold(n_splits=5, shuffle=False)

## Fold results

### Fold 1

- train rows: 198; test rows: 50
- train occupations: 179; test occupations: 45
- occupation intersection: []
- inner splits: 3; selected alpha: 0.01
- global mean MAE/RMSE/R²: 0.213030 / 0.251922 / -0.01543617998163449
- global median MAE/RMSE/R²: 0.210000 / 0.254951 / -0.040000000000000036
- TF-IDF+Ridge (raw) MAE/RMSE/R²: 0.171868 / 0.210525 / 0.29086915672642444
### Fold 2

- train rows: 198; test rows: 50
- train occupations: 179; test occupations: 45
- occupation intersection: []
- inner splits: 3; selected alpha: 0.01
- global mean MAE/RMSE/R²: 0.196717 / 0.237983 / -0.0006381857623962706
- global median MAE/RMSE/R²: 0.190000 / 0.239792 / -0.01590106007067149
- TF-IDF+Ridge (raw) MAE/RMSE/R²: 0.163475 / 0.192280 / 0.3467902681469387
### Fold 3

- train rows: 198; test rows: 50
- train occupations: 179; test occupations: 45
- occupation intersection: []
- inner splits: 3; selected alpha: 0.01
- global mean MAE/RMSE/R²: 0.209444 / 0.231707 / -0.003050380288430965
- global median MAE/RMSE/R²: 0.205000 / 0.231840 / -0.004203643157402848
- TF-IDF+Ridge (raw) MAE/RMSE/R²: 0.163405 / 0.184409 / 0.3646579819285677
### Fold 4

- train rows: 199; test rows: 49
- train occupations: 180; test occupations: 44
- occupation intersection: []
- inner splits: 3; selected alpha: 0.01
- global mean MAE/RMSE/R²: 0.191237 / 0.226153 / -0.028685734441895594
- global median MAE/RMSE/R²: 0.178571 / 0.223036 / -0.0005235602094242342
- TF-IDF+Ridge (raw) MAE/RMSE/R²: 0.147372 / 0.188757 / 0.28338413006234564
### Fold 5

- train rows: 199; test rows: 49
- train occupations: 179; test occupations: 45
- occupation intersection: []
- inner splits: 3; selected alpha: 0.01
- global mean MAE/RMSE/R²: 0.212414 / 0.242580 / -0.0029253762805725447
- global median MAE/RMSE/R²: 0.209184 / 0.244845 / -0.021739130434782705
- TF-IDF+Ridge (raw) MAE/RMSE/R²: 0.178938 / 0.221136 / 0.16655134677512018


## Fold statistics (mean / std across outer folds)

### Global mean baseline

- MAE: mean=0.20456856535822796, std=0.009953746077086245 (n=5)
- RMSE: mean=0.2380691584655318, std=0.009933954739869848 (n=5)
- R²: mean=-0.010147171350985973, std=0.011880567201519946 (n=5)

### Global median baseline

- MAE: mean=0.19855102040816325, std=0.013766134375469455 (n=5)
- RMSE: mean=0.23889269283795816, std=0.012199222251493143 (n=5)
- R²: mean=-0.016473478774456263, std=0.015704304504314804 (n=5)

### TF-IDF + Ridge (raw)

- MAE: mean=0.165011680721419, std=0.011800625299587185 (n=5)
- RMSE: mean=0.19942154567568302, std=0.015691708913680755 (n=5)
- R²: mean=0.2904505767278794, std=0.07759192753823152 (n=5)

### TF-IDF + Ridge (clipped diagnostic)

- MAE: mean=0.16389792678221862, std=0.012431445972429648 (n=5)
- RMSE: mean=0.1992421979897294, std=0.01587590327024159 (n=5)
- R²: mean=0.29171944475192546, std=0.0785510877046461 (n=5)

R² means ignore undefined (null) folds; they are not replaced with zero.

## Pooled out-of-fold statistics

### Global mean

- MAE: 0.20459068722563617
- RMSE: 0.23826470729200908
- R²: -0.003491636464569181

### Global median

- MAE: 0.19858870967741934
- RMSE: 0.23918123105779554
- R²: -0.011226670977708464

### TF-IDF + Ridge (raw)

- MAE: 0.16502665415756804
- RMSE: 0.1998684397174096
- R²: 0.2938730840632441

### TF-IDF + Ridge (clipped diagnostic)

- MAE: 0.16391393064826412
- RMSE: 0.19970076126760683
- R²: 0.2950573891026357

Metrics are reported without ranking a method as successful from a single score.

## Prediction-range diagnostics (raw Ridge OOF)

- min: -0.07821327172285225
- max: 0.6386714473460542
- below 0: 7
- above 1: 0

Raw predictions are not clipped for the primary metrics.

## Warnings

- Target value 1.00 is absent. This is a distribution observation, not a validation failure.
- All current labels are provisional AI-generated weak supervision. Schema and pipeline checks do not imply human validation.
- The target labels are provisional AI-generated weak supervision and are not human-validated ground truth, personal job-loss probabilities, or employment outcomes.

## Limitations

- The target labels are provisional AI-generated weak supervision and are not human-validated ground truth, personal job-loss probabilities, or employment outcomes.
- Schema and grouped-CV pipeline validation do not imply human validation.
- Outputs are contextual occupational task-exposure estimates, not personal job-loss risk, employment probability, or the probability that a user will lose their job.
- Ridge predictions are unconstrained; values outside [0, 1] are reported rather than silently clipped.
