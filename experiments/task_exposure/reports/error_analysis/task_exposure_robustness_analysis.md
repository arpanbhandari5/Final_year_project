# Task-exposure robustness and sensitivity analysis

Weak-supervision sensitivity analysis; labels are provisional AI-generated labels and not human-validated ground truth.

The target labels are provisional AI-generated weak supervision and are not human-validated ground truth, personal job-loss probabilities, or employment outcomes.

This experiment does not establish production readiness, personal job-loss probability, or employment outcomes.
Existing grouped-CV and error-analysis reports were not overwritten.

## Inspector

- `task_text` required; no `task_statement` fallback.
- grouping: `occupation_code`.
- TF-IDF inside sklearn Pipeline per training fold.
- grouped outer CV; grouped inner alpha on outer-train occupations only.
- baselines from outer training fold only.
- raw predictions preserved; clipping is a separate diagnostic.

## Verified source counts

- rows 248, occupations 224
- targets: {'0.00': 86, '0.25': 66, '0.50': 81, '0.75': 15, '1.00': 0}
- resolution_method: {'identical_scores': 205, 'deterministic_mean_snap': 43}
- exclude-snap rows/occ: 205/188
- identical_scores rows/occ: 205/188
- B and C identical: True
- occupations n=1: 201; n>=2: 23; multi-task rows: 47

## Multi-variant grouped CV (full dataset)

| variant | construction | folds | Ridge pooled MAE | RMSE | R² | mean fold MAE | std MAE | mean RMSE | std RMSE | mean R² | std R² | mean baseline MAE | median baseline MAE | Ridge-mean ΔMAE | Ridge-median ΔMAE | raw min | raw max | n<0 | n>1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gkf_noshuffle | GroupKFold shuffle=False random_state=None | 5 | 0.165027 | 0.199868 | 0.293873 | 0.165012 | 0.011801 | 0.199422 | 0.015692 | 0.290451 | 0.077592 | 0.204591 | 0.198589 | -0.039564 | -0.033562 | -0.0782 | 0.6387 | 7 | 0 |
| gkf_shuffle_rs0 | GroupKFold shuffle=True random_state=0 | 5 | 0.161653 | 0.197246 | 0.312280 | 0.161586 | 0.013256 | 0.196723 | 0.015201 | 0.310582 | 0.092933 | 0.204355 | 0.198589 | -0.042702 | -0.036936 | -0.0669 | 0.5985 | 6 | 0 |
| gkf_shuffle_rs1 | GroupKFold shuffle=True random_state=1 | 5 | 0.162363 | 0.195506 | 0.324361 | 0.162769 | 0.020093 | 0.194732 | 0.024932 | 0.308934 | 0.111428 | 0.205838 | 0.198589 | -0.043474 | -0.036226 | -0.0665 | 0.5613 | 5 | 0 |
| gkf_shuffle_rs2 | GroupKFold shuffle=True random_state=2 | 5 | 0.160739 | 0.196391 | 0.318231 | 0.160585 | 0.006344 | 0.195843 | 0.011262 | 0.310825 | 0.063490 | 0.205426 | 0.198589 | -0.044688 | -0.037850 | -0.0610 | 0.5840 | 5 | 0 |
| gkf_shuffle_rs3 | GroupKFold shuffle=True random_state=3 | 5 | 0.160775 | 0.196515 | 0.317372 | 0.161266 | 0.018004 | 0.195959 | 0.024086 | 0.321109 | 0.074502 | 0.204457 | 0.198589 | -0.043682 | -0.037814 | -0.0513 | 0.5917 | 5 | 0 |

Each variant is a separate OOF set. Predictions were not pooled across variants.
Every reported fold had empty train/test occupation intersection.

### Clipped diagnostic (reference gkf_noshuffle only, not a replacement for raw)

- raw metrics: MAE 0.165027, RMSE 0.199868, R² 0.293873
- clipped/display-safe metrics: MAE 0.163914, RMSE 0.199701, R² 0.295057

## Weak-label sensitivity

Weak-supervision sensitivity analysis; labels are provisional AI-generated labels and not human-validated ground truth.

- Full: 248 rows, 224 occupations, 5 folds, Ridge pooled MAE 0.165027, RMSE 0.199868, R² 0.293873
- identical_scores / exclude snap (same table): 205 rows, 188 occupations, 5 folds, Ridge pooled MAE 0.151025, RMSE 0.184787, R² 0.376362; ΔMAE vs mean -0.046313; ΔMAE vs median -0.040438
Better/worse subset MAE is not evidence that a label-generation method is objectively correct.

## Occupation-size sensitivity

- one-task occupations: 201 occupations, 201 rows; OOF slice MAE 0.164989, RMSE 0.201402, R² 0.301718
  These are not reliable occupation-level estimates.
- multi-task occupations: 23 occupations, 47 rows; OOF slice MAE 0.165186, RMSE 0.193172, R² 0.213083
- retrain CV on multi-task occupations only: 47 rows, 23 groups, 5 folds, Ridge pooled MAE 0.182432, RMSE 0.212483, R² 0.047883. Small-n design, not a production evaluator.

## Target-distribution findings

Verified counts: {'0.00': 86, '0.25': 66, '0.50': 81, '0.75': 15, '1.00': 0}
the model has no observed training examples at target 1.00
This is not a claim about real-world maximum automation exposure.
- fold 1: train ['0.00', '0.25', '0.50', '0.75']; test ['0.00', '0.25', '0.50', '0.75']
- fold 2: train ['0.00', '0.25', '0.50', '0.75']; test ['0.00', '0.25', '0.50', '0.75']
- fold 3: train ['0.00', '0.25', '0.50', '0.75']; test ['0.00', '0.25', '0.50', '0.75']
- fold 4: train ['0.00', '0.25', '0.50', '0.75']; test ['0.00', '0.25', '0.50', '0.75']
- fold 5: train ['0.00', '0.25', '0.50', '0.75']; test ['0.00', '0.25', '0.50', '0.75']

## Near-duplicate findings

- method: word/unigram-bigram TF-IDF cosine similarity on task_text (diagnostic only; not used in CV)
- preprocessing: sklearn TfidfVectorizer ngram_range=(1,2), stop_words=english, min_df=1; no source rewrite
- threshold: 0.85 (0.85 is a conservative lexical-overlap cutoff for high textual similarity, not a claim of semantic equivalence.)
- pairs scored: 30628; pairs >= threshold: 0
- exact task_text duplicate rows: 0; normalized duplicate rows: 0
- Distinction: exact duplicate / normalized duplicate / high textual similarity / semantic similarity (not claimed).

| sim | task_id_a | task_id_b | occ_a | occ_b | same_occ |
|---|---|---|---|---|---|
| 0.3956 | 13730 | 13884 | 49-2096.00 | 49-9095.00 | False |
| 0.2860 | 22469 | 6592 | 25-9042.00 | 25-2022.00 | False |
| 0.2642 | 1598 | 17532 | 21-1014.00 | 31-9099.01 | False |
| 0.2532 | 14099 | 22015 | 51-6042.00 | 17-3024.00 | False |
| 0.2387 | 16908 | 14680 | 19-3011.01 | 15-1299.08 | False |
| 0.2365 | 11788 | 23446 | 49-9012.00 | 47-2031.00 | False |
| 0.2349 | 22952 | 15126 | 33-1091.00 | 51-9195.05 | False |
| 0.2255 | 14099 | 14686 | 51-6042.00 | 15-1299.08 | False |
| 0.2242 | 17709 | 7572 | 15-2099.01 | 19-3032.00 | False |
| 0.2031 | 3327 | 1598 | 11-9021.00 | 21-1014.00 | False |
| 0.1924 | 23446 | 9922 | 47-2031.00 | 47-5032.00 | False |
| 0.1898 | 3245 | 9672 | 11-2011.00 | 41-1012.00 | False |
| 0.1892 | 10971 | 15126 | 25-9044.00 | 51-9195.05 | False |
| 0.1767 | 16849 | 18087 | 19-2041.01 | 47-4011.01 | False |
| 0.1718 | 3327 | 6895 | 11-9021.00 | 27-1014.00 | False |

## Descriptive uncertainty (not prediction intervals)

- fold MAE mean 0.165012 std 0.011801
- fold R² mean 0.290451 std 0.077592
- residual quantiles p10/p50/p90: {'p10': -0.2421750530646577, 'p50': 0.015676963574744185, 'p90': 0.27472501074076267}
- abs-error quantiles p10/p50/p90: {'p10': 0.03632585946469275, 'p50': 0.1551997450864584, 'p90': 0.3200941216087887}

## Robustness conclusions

- 1_ridge_vs_train_mean: **remained consistent**. On the reference split and all shuffle variants, Ridge pooled and per-fold MAE were lower than the training-fold global mean.
- 2_ridge_vs_train_median: **remained consistent**. On the reference split and all shuffle variants, Ridge pooled and per-fold MAE were lower than the training-fold global median.
- 3_fold_construction_variants: **remained consistent**. Direction vs both baselines held across GroupKFold shuffle=False and shuffle=True random_state 0-3. Magnitude of MAE still varies by fold assignment.
- 4_exclude_mean_snap: **remained consistent**. Excluding deterministic_mean_snap is the same 205-row table as identical_scores-only; one subset CV was run, not two independent tests.
- 5_identical_scores_subset: **same analysis as claim 4**. B and C are identical (205 rows, 188 occupations).
- 6_one_task_occupations: **sensitive to one-task occupations**. 201/224 occupations have n=1 (201 OOF rows). Full OOF Ridge MAE=0.1650; n=1 slice MAE=0.1650; n>=2 slice MAE=0.1652 on 47 rows / 23 occupations. Retraining grouped CV on the 47 multi-task rows only yielded Ridge pooled MAE 0.182 vs training-fold mean MAE 0.179 (Ridge did not have lower pooled MAE than the mean baseline in that small-n design).
- 7_near_duplicate_leakage: **insufficient evidence of exact-duplicate leakage**. Exact task_text duplicate rows=0; normalized duplicate rows=0; TF-IDF cosine pairs >=0.85: 0 of 30628. High cosine is textual similarity, not semantic equivalence.
- 8_raw_boundary: **does not materially replace the raw evaluation**. Reference raw min=-0.07821327172285225, max=0.6386714473460542, below0=7, above1=0. Clipped metrics are diagnostic only.

## Remaining blockers for shadow testing

- Labels remain provisional AI-generated weak supervision, not human-validated ground truth.
- No employment-outcome validation exists.
- 201/224 occupations contribute only a single task; occupation-level claims are not supported.
- No observed labels at 1.00; do not extrapolate to a maximum exposure class.
- Raw Ridge can predict below 0; that is unconstrained regression, not a display policy.

This phase stops before shadow testing, production review, training, or integration.
