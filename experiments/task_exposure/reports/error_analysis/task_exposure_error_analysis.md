# Task-exposure experimental error analysis (read-only)

The target labels are provisional AI-generated weak supervision and are not human-validated ground truth, personal job-loss probabilities, or employment outcomes.

This analysis uses the existing grouped-CV report plus an in-memory reconstruction of
raw Ridge out-of-fold predictions. The reconstruction was checked against the stored
pooled OOF MAE and stored test-fold occupation membership. The original files
`task_exposure_grouped_cv.json` and `task_exposure_grouped_cv.md` were not rewritten.

Labels are not human-validated ground truth. There is no employment-outcome validation.
This experiment does not establish personal job-loss probability, individual employment
risk, or production readiness. Numerical differences below are observed facts under
these weak labels; they are not causal findings and are not a ranking of occupations.

## Dataset columns observed

`task_id, task_text, normalized_task_text, task_group_id, occupation_code, occupation_title, soc_code, reviewer_1_score, reviewer_2_score, adjudicated_exposure_score, label_confidence, resolution_method, adjudication_status, label_source, not_human_ground_truth, split_key, n_source_rows, occupation_codes_all, task_ids_all`

## 1. Per-fold performance (from stored report)

### Fold 1 (train rows 198 / test rows 50; train occ 179 / test occ 45)
- global mean: MAE 0.213030, RMSE 0.251922, R² -0.01543617998163449
- global median: MAE 0.210000, RMSE 0.254951, R² -0.040000000000000036
- TF-IDF + Ridge (raw): MAE 0.171868, RMSE 0.210525, R² 0.29086915672642444

### Fold 2 (train rows 198 / test rows 50; train occ 179 / test occ 45)
- global mean: MAE 0.196717, RMSE 0.237983, R² -0.0006381857623962706
- global median: MAE 0.190000, RMSE 0.239792, R² -0.01590106007067149
- TF-IDF + Ridge (raw): MAE 0.163475, RMSE 0.192280, R² 0.3467902681469387

### Fold 3 (train rows 198 / test rows 50; train occ 179 / test occ 45)
- global mean: MAE 0.209444, RMSE 0.231707, R² -0.003050380288430965
- global median: MAE 0.205000, RMSE 0.231840, R² -0.004203643157402848
- TF-IDF + Ridge (raw): MAE 0.163405, RMSE 0.184409, R² 0.3646579819285677

### Fold 4 (train rows 199 / test rows 49; train occ 180 / test occ 44)
- global mean: MAE 0.191237, RMSE 0.226153, R² -0.028685734441895594
- global median: MAE 0.178571, RMSE 0.223036, R² -0.0005235602094242342
- TF-IDF + Ridge (raw): MAE 0.147372, RMSE 0.188757, R² 0.28338413006234564

### Fold 5 (train rows 199 / test rows 49; train occ 179 / test occ 45)
- global mean: MAE 0.212414, RMSE 0.242580, R² -0.0029253762805725447
- global median: MAE 0.209184, RMSE 0.244845, R² -0.021739130434782705
- TF-IDF + Ridge (raw): MAE 0.178938, RMSE 0.221136, R² 0.16655134677512018



Fold-to-fold Ridge MAE ranged from 0.147372 to
0.178938 (spread
0.031565).
Ridge R² ranged from 0.166551 to
0.364658. That range is an observed property of
five occupation-grouped folds (test n ≈ 49–50 rows / 44–45 occupations). It is not
interpreted here as good or bad.

## 2. Fold mean / std / min / max

### global mean
- MAE: mean 0.204569, std 0.009954, min 0.191237, max 0.213030 (n=5 folds)
- RMSE: mean 0.238069, std 0.009934, min 0.226153, max 0.251922 (n=5 folds)
- R2: mean -0.010147, std 0.011881, min -0.028686, max -0.000638 (n=5 folds)

### global median
- MAE: mean 0.198551, std 0.013766, min 0.178571, max 0.210000 (n=5 folds)
- RMSE: mean 0.238893, std 0.012199, min 0.223036, max 0.254951 (n=5 folds)
- R2: mean -0.016473, std 0.015704, min -0.040000, max -0.000524 (n=5 folds)

### TF-IDF + Ridge (raw)
- MAE: mean 0.165012, std 0.011801, min 0.147372, max 0.178938 (n=5 folds)
- RMSE: mean 0.199422, std 0.015692, min 0.184409, max 0.221136 (n=5 folds)
- R2: mean 0.290451, std 0.077592, min 0.166551, max 0.364658 (n=5 folds)



Standard deviations use sample std (ddof=1), matching the evaluator report.

## 3. Baseline comparison (observed numerical differences)

Lower MAE/RMSE is numerically smaller error on these labels. Higher R² is numerically
more variance explained on these labels. That is not a claim of model success or
production usefulness.

### Ridge minus global mean (negative MAE/RMSE means Ridge lower error)
- fold 1: ΔMAE -0.041162, ΔRMSE -0.041397, ΔR² +0.306305
- fold 2: ΔMAE -0.033242, ΔRMSE -0.045703, ΔR² +0.347428
- fold 3: ΔMAE -0.046039, ΔRMSE -0.047298, ΔR² +0.367708
- fold 4: ΔMAE -0.043864, ΔRMSE -0.037395, ΔR² +0.312070
- fold 5: ΔMAE -0.033477, ΔRMSE -0.021444, ΔR² +0.169477
- pooled OOF: ΔMAE -0.039564, ΔRMSE -0.038396, ΔR² +0.297365

### Ridge minus global median (negative MAE/RMSE means Ridge lower error)
- fold 1: ΔMAE -0.038132, ΔRMSE -0.044426, ΔR² +0.330869
- fold 2: ΔMAE -0.026525, ΔRMSE -0.047511, ΔR² +0.362691
- fold 3: ΔMAE -0.041595, ΔRMSE -0.047431, ΔR² +0.368862
- fold 4: ΔMAE -0.031199, ΔRMSE -0.034278, ΔR² +0.283908
- fold 5: ΔMAE -0.030246, ΔRMSE -0.023708, ΔR² +0.188290
- pooled OOF: ΔMAE -0.033562, ΔRMSE -0.039313, ΔR² +0.305100



On every outer fold and in pooled OOF, Ridge MAE and RMSE were numerically lower than
both training-fold mean and median baselines, and Ridge R² was numerically higher.
Interpretation: the text model produced smaller average absolute and squared error than
constant train-fold summaries on this weak-label table. That does not imply the labels
are human-validated, that errors are small in an occupational sense, or that the model
is ready for application use.

Pooled OOF from the stored report:

- global mean: MAE 0.20459068722563617, RMSE 0.23826470729200908, R² -0.003491636464569181
- global median: MAE 0.19858870967741934, RMSE 0.23918123105779554, R² -0.011226670977708464
- TF-IDF + Ridge raw: MAE 0.16502665415756804, RMSE 0.1998684397174096, R² 0.2938730840632441
- TF-IDF + Ridge clipped diagnostic: MAE 0.16391393064826412, RMSE 0.19970076126760683, R² 0.2950573891026357

## 4. Prediction-error analysis (raw Ridge OOF)

The stored JSON did not contain per-row predictions. Rows below were reconstructed
in memory with the same Pipeline/GroupKFold/alpha path. Reconstructed pooled MAE
0.165026654158 matched the report MAE 0.165026654158.

### Largest absolute errors (n=15)

| fold | task_id | occupation_code | target | raw_pred | abs_error |
|---|---|---|---|---|---|
| 1 | 1224 | 13-1121.00 | 0.75 | 0.1738 | 0.5762 |
| 4 | 23315 | 43-9041.00 | 0.75 | 0.2157 | 0.5343 |
| 5 | 2795 | 43-6014.00 | 0.75 | 0.2300 | 0.5200 |
| 5 | 21660 | 15-1243.00 | 0.75 | 0.2321 | 0.5179 |
| 5 | 2281 | 35-3031.00 | 0.75 | 0.3095 | 0.4405 |
| 1 | 4056 | 27-4032.00 | 0.75 | 0.3263 | 0.4237 |
| 4 | 3245 | 11-2011.00 | 0.00 | 0.3966 | 0.3966 |
| 4 | 9672 | 41-1012.00 | 0.00 | 0.3872 | 0.3872 |
| 4 | 20329 | 13-1161.01 | 0.75 | 0.3784 | 0.3716 |
| 1 | 778 | 43-6013.00 | 0.75 | 0.3884 | 0.3616 |
| 2 | 6096 | 25-1067.00 | 0.75 | 0.3945 | 0.3555 |
| 2 | 6636 | 25-2023.00 | 0.00 | 0.3489 | 0.3489 |
| 1 | 3140 | 51-9111.00 | 0.00 | 0.3477 | 0.3477 |
| 2 | 5066 | 35-2011.00 | 0.00 | 0.3390 | 0.3390 |
| 4 | 18003 | 29-1141.04 | 0.00 | 0.3386 | 0.3386 |

### Smallest absolute errors (n=15)

| fold | task_id | occupation_code | target | raw_pred | abs_error |
|---|---|---|---|---|---|
| 4 | 17532 | 31-9099.01 | 0.25 | 0.2504 | 0.0004 |
| 1 | 20495 | 17-2072.00 | 0.50 | 0.4992 | 0.0008 |
| 4 | 3236 | 11-2011.00 | 0.25 | 0.2483 | 0.0017 |
| 5 | 10175 | 51-4072.00 | 0.00 | -0.0021 | 0.0021 |
| 3 | 7572 | 19-3032.00 | 0.50 | 0.5028 | 0.0028 |
| 1 | 13884 | 49-9095.00 | 0.25 | 0.2467 | 0.0033 |
| 2 | 20446 | 47-4011.00 | 0.25 | 0.2567 | 0.0067 |
| 1 | 2397 | 39-9032.00 | 0.25 | 0.2429 | 0.0071 |
| 2 | 7535 | 19-2011.00 | 0.25 | 0.2586 | 0.0086 |
| 5 | 6938 | 29-1021.00 | 0.00 | -0.0088 | 0.0088 |
| 2 | 951 | 11-2021.00 | 0.50 | 0.4862 | 0.0138 |
| 1 | 2569 | 43-3071.00 | 0.25 | 0.2341 | 0.0159 |
| 2 | 18384 | 29-1171.00 | 0.25 | 0.2333 | 0.0167 |
| 5 | 2478 | 43-3011.00 | 0.25 | 0.2728 | 0.0228 |
| 5 | 9875 | 47-2073.00 | 0.00 | -0.0228 | 0.0228 |

### Raw predictions below 0 (n=7)

Observed raw min -0.078213, raw max 0.638671.
Count below 0: 7. Count above 1: 0.
These are unconstrained Ridge outputs. Clipped diagnostics were not substituted.

| fold | task_id | occupation_code | target | raw_pred | abs_error |
|---|---|---|---|---|---|
| 3 | 9922 | 47-5032.00 | 0.00 | -0.0782 | 0.0782 |
| 3 | 23446 | 47-2031.00 | 0.00 | -0.0761 | 0.0761 |
| 4 | 4778 | 47-2021.00 | 0.00 | -0.0549 | 0.0549 |
| 4 | 15108 | 51-9071.06 | 0.00 | -0.0331 | 0.0331 |
| 5 | 9875 | 47-2073.00 | 0.00 | -0.0228 | 0.0228 |
| 5 | 6938 | 29-1021.00 | 0.00 | -0.0088 | 0.0088 |
| 5 | 10175 | 51-4072.00 | 0.00 | -0.0021 | 0.0021 |

A bounded-output model could be a later experimental direction. No production display
policy is recommended here.

## 5. Group-level performance

Occupation-level sample sizes: 224 occupation codes;
201 with n=1 task; 23 with n>1 task.
Occupation size histogram (tasks per occupation): {1: 201, 2: 22, 3: 1}.

Single-task occupation MAE equals that row's absolute error. It is not a stable
estimate of group generalization and is listed separately.

### Multi-task occupations with highest observed MAE (n>1 only)

occupation_code  n_tasks  single_task_group      mae     rmse        r2
     25-1067.00        2              False 0.306646 0.310506  0.314388
     31-9097.00        2              False 0.239383 0.239504 -2.671167
     51-4031.00        2              False 0.237856 0.240776       NaN
     49-3093.00        2              False 0.231623 0.243750       NaN
     17-3011.00        2              False 0.208936 0.210803       NaN
     25-9043.00        2              False 0.208851 0.243052 -2.780743
     25-9042.00        2              False 0.205874 0.206083  0.697989
     11-2011.00        2              False 0.199131 0.280438 -4.033298
     33-1091.00        2              False 0.198414 0.203012       NaN
     29-2031.00        2              False 0.180673 0.180743 -1.090758

### Multi-task occupations with lowest observed MAE (n>1 only)

occupation_code  n_tasks  single_task_group      mae     rmse        r2
     13-1031.00        2              False 0.044463 0.046629  0.860849
     47-4099.03        2              False 0.052054 0.053647       NaN
     11-3131.00        2              False 0.069721 0.070597  0.681028
     43-3011.00        2              False 0.084698 0.104924  0.295416
     21-1014.00        2              False 0.104182 0.112328       NaN
     49-9012.00        2              False 0.114452 0.125031 -0.000499
     49-2095.00        2              False 0.117556 0.145775  0.659994
     11-2022.00        2              False 0.137301 0.137301       NaN
     47-5032.00        2              False 0.160483 0.180341       NaN
     15-1299.08        2              False 0.167434 0.187029       NaN

High observed MAE with n=2 is still a small sample. No occupation is labeled worst or
best. No causal claim is made.

### Single-task occupations (unstable group estimates; largest abs error)

occupation_code  n_tasks  single_task_group      mae     rmse  r2
     13-1121.00        1               True 0.576181 0.576181 NaN
     43-9041.00        1               True 0.534278 0.534278 NaN
     43-6014.00        1               True 0.520016 0.520016 NaN
     15-1243.00        1               True 0.517935 0.517935 NaN
     35-3031.00        1               True 0.440490 0.440490 NaN
     27-4032.00        1               True 0.423721 0.423721 NaN
     41-1012.00        1               True 0.387222 0.387222 NaN
     13-1161.01        1               True 0.371593 0.371593 NaN
     43-6013.00        1               True 0.361593 0.361593 NaN
     25-2023.00        1               True 0.348888 0.348888 NaN

### SOC major group (`soc_code`)

| soc_code | n_tasks | n_occupations | MAE | RMSE | R² |
|---|---|---|---|---|---|
| 51 | 28 | 26 | 0.1795 | 0.2014 | -0.2377 |
| 29 | 23 | 21 | 0.1512 | 0.1869 | 0.2421 |
| 25 | 20 | 17 | 0.1542 | 0.1887 | 0.4233 |
| 17 | 16 | 15 | 0.1457 | 0.1704 | 0.0413 |
| 11 | 16 | 13 | 0.1446 | 0.1787 | -0.0295 |
| 19 | 16 | 16 | 0.1222 | 0.1423 | 0.3471 |
| 47 | 15 | 13 | 0.1276 | 0.1560 | -0.0948 |
| 49 | 14 | 11 | 0.1274 | 0.1539 | 0.0230 |
| 13 | 13 | 12 | 0.1931 | 0.2503 | -1.2885 |
| 43 | 13 | 12 | 0.2091 | 0.2680 | -0.1696 |
| 53 | 12 | 10 | 0.1762 | 0.2021 | -0.1758 |
| 27 | 11 | 11 | 0.1762 | 0.2078 | 0.2536 |
| 15 | 10 | 9 | 0.2097 | 0.2484 | -1.7423 |
| 39 | 8 | 8 | 0.1843 | 0.2173 | 0.3191 |
| 33 | 7 | 6 | 0.1983 | 0.2072 | 0.1586 |
| 41 | 6 | 6 | 0.1511 | 0.1988 | -0.3390 |
| 31 | 5 | 4 | 0.1613 | 0.1893 | -0.0238 |
| 35 | 4 | 4 | 0.2277 | 0.2818 | -0.0700 |
| 21 | 4 | 3 | 0.1317 | 0.1616 | -1.2294 |
| 45 | 3 | 3 | 0.2420 | 0.2461 | -3.3605 |
| 23 | 2 | 2 | 0.1998 | 0.2189 | -2.0679 |
| 37 | 2 | 2 | 0.2620 | 0.2621 | nan |

SOC groups also vary in n_tasks. Small n_tasks should not be read as a reliable
group-quality ranking.

## 6. Target distribution

Counts: {'0.00': 86, '0.25': 66, '0.50': 81, '0.75': 15, '1.00': 0}.
Min 0.00, max 0.75, missing 0.
Class `1.00` count is 0. That is an observed property of the current provisional-label
distribution, not a validation failure.
Counts are imbalanced (`0.00` 86 / `0.50` 81 / `0.25` 66 / `0.75` 15 / `1.00` 0).

## 7. Duplicate and near-duplicate text

- exact `task_text` duplicate groups: 0; affected rows: 0
- exact `normalized_task_text` duplicate groups: 0; affected rows: 0
- `task_group_id` values with more than one row: 0; affected rows: 0
- whitespace-collapsed lowercase duplicate groups: 0
- normalized-text groups spanning more than one occupation: 0
- those groups whose occupations were assigned to different outer *test* folds: 0

Details of occupation-crossing normalized duplicates: []
Details of test-fold-crossing normalized duplicates: []

No semantic near-duplicate detector was used.

Exact `task_id` duplicates in the training table: 0 (from the evaluator validation summary).

## 8. Source-row aggregation

{
  "n_source_rows_counts": {
    "1": 246,
    "2": 2
  },
  "n_source_rows_gt_1": 2
}

`split_key` equals `task_group_id` on this table when both columns exist; grouping in
the evaluator remains `occupation_code`, not `task_group_id`.

## 9. Label metadata

{
  "label_source": {
    "provisional_ai_weak_supervision": 248
  },
  "resolution_method": {
    "identical_scores": 205,
    "deterministic_mean_snap": 43
  },
  "label_confidence": {
    "1.0": 205,
    "0.85": 43
  },
  "adjudication_status": {
    "identical": 205,
    "deterministic_mean": 43
  },
  "not_human_ground_truth": {
    "True": 248
  }
}

## 10. Reliability limitations

- The target labels are provisional AI-generated weak supervision and are not human-validated ground truth, personal job-loss probabilities, or employment outcomes.
- Schema/pipeline checks do not imply human validation.
- There is no evidence in this analysis of independently reviewed human ground truth.
- There is no employment-outcome validation.
- Outputs are not personal job-loss probabilities or individual employment risk.
- This experiment does not establish production readiness.
- R² on weak labels is not model validity for real-world job outcomes.

## Reconstruction check

Selected alphas in reconstruction: [0.01, 0.01, 0.01, 0.01, 0.01] (report: [0.01, 0.01, 0.01, 0.01, 0.01]).
