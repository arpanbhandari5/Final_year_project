# ML Audit and Next Steps for Final_year_project

## Current repository verification

The connected checkout at commit `4786a98` does **not yet contain** the improvements described in the supplied audit. It still shows:

- `Ridge(alpha=1.2)` in `train_model.py` and `evaluation.py`
- `max_features=7000`
- No confirmed `RidgeCV`
- No confirmed model version, dataset hash, selected-alpha, or training metadata bundle
- The older TF-IDF-only risk scoring and role matching implementation

Therefore, the reported improvements should be treated as changes from another working copy or unpushed branch until they are committed and pushed to `arpanbhandari5/Final_year_project`.

## Verdict on the reported changes

The changes are **good engineering improvements**, especially the move from a single opaque risk score to a hybrid, evidence-based result. However, the reported metrics show that the automation-risk target is currently not learnable enough to support a predictive claim.

The most important finding is:

| Metric | Improved model | Mean baseline | Interpretation |
|---|---:|---:|---|
| MAE | 0.24793 | 0.24781 | Slightly worse than predicting the mean |
| RMSE | 0.28727 | 0.28693 | Slightly worse than predicting the mean |
| R² | -0.00241 | 0.00000 | Explains effectively none of the target variance |

This means increasing TF-IDF capacity or changing Ridge regularization is not the primary solution. The target, labels, and occupation mapping need improvement first.

## Improvements that should be retained

### 1. RidgeCV instead of fixed regularization

Recommended. Selecting `alpha` through cross-validation is better than hard-coding `alpha=1.2`.

Required safeguards:

- Fit vectorization and model selection inside each training fold.
- Use a `Pipeline` so preprocessing cannot leak across folds.
- Use an inner cross-validation loop for alpha selection when reporting final test performance.
- Report the selected alpha for each fold, not only the final alpha.
- Compare RidgeCV with the mean baseline and a structured-feature baseline.

### 2. Larger and better TF-IDF representation

The move to 12,000 features, bigrams, `min_df=2`, and sublinear TF weighting is reasonable. It improves representation capacity, but it cannot create signal that is absent from the target labels.

Retain the configuration only if it improves repeated out-of-sample results. Do not present the larger vocabulary as evidence of better prediction by itself.

### 3. Interpretable numeric buckets

Converting raw floating-point values into terms such as:

- `analytical_complexity_high`
- `task_repetition_low`
- `ai_maturity_medium`

is more explainable than placing arbitrary floating-point numbers into text. Still, bucket thresholds must be documented and tested for sensitivity.

Store the following metadata:

- Original field
- Original value
- Bucket name
- Bucket thresholds
- Dataset release
- Transformation version

### 4. Model and dataset versioning

Strongly recommended. The model artifact should include:

- Model version
- Training timestamp
- Git commit
- Dataset file names
- Dataset hashes
- Dataset row counts
- Feature configuration
- Selected alpha
- Target definition
- Train/test split seed
- Evaluation metrics
- Source and release dates
- Data transformation version

This is essential for reproducibility and for explaining why two users may receive different results after retraining.

### 5. Hybrid automation-exposure score

A hybrid score is more defensible than applying an occupation-trained text model directly to an entire resume. The API should distinguish:

- Resume-language estimate
- Closest-role evidence
- Skill-to-role similarity
- Confidence or evidence coverage
- Ranking margin

The final value should remain a **contextual estimate**, not a personal probability.

The combination weights must be learned or justified using held-out validation. They should not be chosen only because the resulting output looks plausible.

### 6. Role matching improvements

The following additions are useful:

- Canonical skill overlap
- Direct role-name evidence
- Duplicate occupation removal
- Rank
- Lexical similarity
- Semantic similarity
- Match confidence
- Supporting resume evidence

These make role matching more explainable. They are separate from proving that the automation-risk target is predictive.

### 7. Canonical aliases and word boundaries

The aliases are valuable:

- `JS` → `JavaScript`
- `ML` → `Machine Learning`
- `Node` → `Node.js`
- `RESTful APIs` → `REST APIs`
- `GitHub/GitLab` → `Version Control`

Use case-insensitive, word-boundary-aware matching and preserve the original evidence span. Add regression tests for false positives such as:

- `R` inside ordinary words
- `C` inside unrelated terms
- `Go` inside “Google”
- `SQL` inside a longer token
- `Java` inside “JavaScript” when the distinction matters

### 8. Course recommendation metadata

Provider, level, duration, match type, phrase matching, canonical aliases, target-role prioritization, and resume-skill fallback are all useful. The next improvement should be prerequisite-aware ordering rather than simply returning more courses.

## What the negative R² means

Negative R² is not a software failure. It is evidence that the current target is weak relative to the available predictors.

Likely causes include:

- Synthetic or noisy automation-risk labels
- Repeated or duplicated occupation rows
- Risk scores generated from overlapping random factors
- Weak alignment between job descriptions and resume text
- No stable O*NET-SOC mapping
- Mixed industries or geographies without normalization
- Target values that do not correspond to observable language features
- Leakage or mismatch between occupation-level labels and individual resume inputs
- A target definition that combines automation exposure with unrelated salary, maturity, or industry variables

The model should not be made more complex until these causes are investigated.

## Recommended next experiments

### Experiment 1 — Verify the baseline correctly

Report these baselines using identical folds:

1. Mean prediction
2. Median prediction
3. Industry-group mean
4. Role-group mean
5. RidgeCV on text
6. RidgeCV on structured numeric features
7. RidgeCV on text plus structured features

Use repeated cross-validation, not only one five-fold split. Report mean and standard deviation.

### Experiment 2 — Check duplicate and near-duplicate rows

Before training:

- Deduplicate exact rows.
- Check duplicate job roles.
- Check repeated role/industry combinations.
- Measure identical or near-identical text.
- Group splits by occupation or role when appropriate.
- Confirm that no version of the same occupation appears in both train and test.

### Experiment 3 — Test target reliability

For `automation_risk_score`, report:

- Distribution
- Number of unique values
- Missing values
- Extreme values
- Correlation with structured fields
- Correlation with duplicate rows
- Within-role variance
- Between-role variance
- Stability across dataset versions

If the target is synthetic, label it as a demonstration target and do not use it to make real-world career claims.

### Experiment 4 — Use a structured occupation model

For automation exposure, structured occupation features are more appropriate than resume language alone. Candidate inputs include:

- Task repetition
- Creativity requirement
- Physical labor
- Analytical complexity
- Social interaction
- AI tool availability
- AI maturity
- Communication requirement
- Domain-specific knowledge
- Team collaboration
- Current and future AI dependency
- Training hours
- Job demand

However, this is useful only if the target is independently sourced and conceptually aligned with those predictors. If the target is derived from the same fields, the result is descriptive rather than predictive and must be labeled accordingly.

### Experiment 5 — Add O*NET-SOC mapping and source provenance

Each occupation should have:

- Stable O*NET-SOC code
- Official occupation title
- Alternate titles
- Task source
- Skill source
- Technology source
- Release date
- Geography
- Data collection method
- Target definition

Then separate:

- Official occupational facts
- Local model estimates
- User resume evidence
- Generated narrative

### Experiment 6 — Evaluate confidence separately from correctness

A ranking margin is a useful heuristic, but it is not automatically a calibrated probability. Validate confidence using:

- Top-1 and Top-3 role accuracy
- Abstention or “insufficient evidence” rate
- Calibration curve
- Expected calibration error
- Coverage versus accuracy
- Performance by resume length and format

For weak matches, the correct output should be:

> “Insufficient evidence for a reliable role match.”

### Experiment 7 — Validate the hybrid risk score

Do not blend components solely by intuition. Compare:

- Resume-language score alone
- Closest-role score alone
- Skill overlap alone
- Equal-weight blend
- Validated-weight blend
- Rule-based descriptive exposure index

If no version beats a transparent baseline, retain the components as evidence cards instead of combining them into one score.

## Recommended API contract

The API should return a structure similar to:

```json
{
  "automation_exposure": {
    "value": 0.51,
    "label": "Contextual estimate",
    "interpretation": "Estimated exposure of tasks associated with the closest occupational evidence; not a personal probability.",
    "confidence": 0.34,
    "status": "low_evidence",
    "components": {
      "resume_language": 0.48,
      "closest_role_evidence": 0.56,
      "skill_role_similarity": 0.42
    },
    "model_version": "risk-v2",
    "dataset_version": "automation-2026-09",
    "dataset_hash": "...",
    "limitations": [
      "The current target is weakly predictive in validation.",
      "The score is not an individual employment or job-loss probability."
    ]
  }
}
```

## Additional evidence from `evaluation.json`

The supplied evaluation artifact makes the diagnosis more specific:

- The dataset has **3,000 rows but only 20 unique roles**, so the effective occupational diversity is limited.
- The risk target ranges from `0.00074` to `0.99962`, with mean `0.50132` and standard deviation `0.28693`. The baseline RMSE being almost exactly `0.28693` is expected when predicting the mean; it confirms that the model is not explaining meaningful variation.
- The model selects `alpha=100.0` on the full data. If 100 is the largest candidate value, RidgeCV is choosing the strongest available shrinkage, which is consistent with weak signal and a preference toward the mean. The alpha grid should be reported and expanded only as a diagnostic, not as a way to manufacture performance.
- All 20 role-level R² values are approximately zero or negative. The best values are only about `0.006`, while several roles are below `-0.01`. No role group shows useful predictive performance.
- Role-level MAE varies from approximately `0.216` to `0.270`, but this variation is not evidence of model quality; it is mainly target-distribution and noise variation until compared with role-specific baselines and uncertainty intervals.

This is stronger evidence than the aggregate metric alone that the current target should be treated as a noisy demonstration label or replaced with source-backed occupational data. The appropriate next step is not a deeper neural model. It is a target audit, stable O*NET-SOC mapping, source provenance, and a clearly separated descriptive exposure index.

The new focused tests are useful regression protection. They verify alias/boundary behavior, evidence returned for matched skills, hybrid explainability fields, model metadata, semantic role similarity, and role deduplication. They should be supplemented with tests for low-evidence abstention, confidence calibration, dataset/version mismatch, per-user authorization, and prevention of false positives for short skill names such as `R`, `C`, and `Go`.

## Final recommendation

The reported ML changes are worth merging, but they should be presented as improvements to **engineering quality and explainability**, not as proof of predictive accuracy.

The next major improvement should be:

1. Push and verify the new implementation in GitHub.
2. Add reproducible metadata and exact evaluation code.
3. Audit duplicates and target generation.
4. Establish stable O*NET-SOC occupation mappings.
5. Replace or clearly label the current synthetic/noisy target.
6. Validate the hybrid score against transparent baselines.
7. Add calibrated uncertainty and an abstention state.
8. Preserve the result as contextual automation/task exposure, never job-loss prediction.
