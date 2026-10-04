# Overall improvement (governed evaluation audit)

Date: 2026-10-03. Research evidence is separate from production behavior. No Git operations were performed for this audit.

This is **not** a claim that the original production Ridge was numerically improved. The original historical CV protocol is **not exactly reproducible**.

## 1. Original architecture

- Trainer: [`train_model.py`](../train_model.py) — corpus-wide TF-IDF (`max_features=7000`) fit on jobs + resumes + O*NET texts, then `Ridge(alpha=1.2)` on `automation_risk_score`. Writes `ml_models/model.pkl`.
- Evaluator: [`evaluation.py`](../evaluation.py) — still imports `train_model.build_risk_pipeline`, which **does not exist**. RepeatedKFold on rows. This file was **not repaired**.
- Target: occupation/job-row `automation_risk_score` in [`data/automation_risk.csv`](../data/automation_risk.csv) (3,000 rows, 20 unique `job_role` values). Not a task-level human label and not personal job-loss probability.
- Baseline inventory (2026-09-29): [`docs/BASELINE_INVENTORY.md`](BASELINE_INVENTORY.md) — pytest **7 passed, 13 warnings**; compile pass; Bandit 26 low; pip-audit fail on pytest version.

## 2. Current architecture (kept separate)

| Track | Role |
|---|---|
| Production historical reference | `ml_models/model.pkl` via [`risk_assessor.py`](../risk_assessor.py); UI copy is occupation-level reference, not personal job-loss |
| Production task exposure | Confirmed occupation → published E0/E1/E2 lookup ([`task_exposure_assessor.py`](../task_exposure_assessor.py)) |
| Isolated historical evaluator (this audit) | [`experiments/historical_reference/evaluate_historical_reference.py`](../experiments/historical_reference/evaluate_historical_reference.py) |
| 248-row weak supervision | Research Ridge only; not production |
| GPTs-are-GPTs classifier | Research-only E0/E1/E2 on **923** occupations |
| 800 product subset | Search/coverage; **not** the classifier training population |
| Five-level 0.00–1.00 rubric | `deferred_due_to_unavailable_independent_reviewers` |

## 3. Dataset changes (verified)

| Dataset | Size | Hash (SHA-256) |
|---|---|---|
| Historical automation-risk CSV | 3,000 rows | `d28ca4cbc2ca746c9a033d1953d49d565c3e64a2d8ae54b6ce52bed1826a18f1` |
| Historical Frey–Osborne occupation table | 618 occupations | `9f8c7cf38d487e19cd99f126dc03d6d6eaf77ec0aab406fe67f5a507b2e97e10` |
| 248-row provisional training table | 248 rows / 224 occupations | `f10ad444afcb24605314c2e09b59022effc5a7db247a22a8bfa95bb699a1152c` |
| Public GPTs-are-GPTs benchmark | 19,265 tasks / 923 occupations | `bfc3b219d132449a17105dfc6efc2f0254a3dc613f6192405741c36be10d1299` |
| 800 occupation product file | 800 occupations | `26eeee1a06e4919eaf699f7a9da2d0a5f417e625f4d968326ef12daec93c4aa5` |
| Production pickle `ml_models/model.pkl` | artifact | `cca7933cc2fca7b37d405c5d5d0f111a88ec071a69cea536315064d60944398c` |

`ml_models/automation_model.pkl` exists and currently has the **same** SHA-256 as `model.pkl`. Do not treat that as a second independent model.

The 618-row table is **not** joined to `automation_risk.csv` in this evaluator. Metrics are **not** pooled across those two files.

Public benchmark split ([`split_manifest.json`](../experiments/task_exposure/reports/public_benchmark/split_manifest.json)): 646 / 138 / 139 occupations; 13,453 / 2,941 / 2,871 tasks; empty occupation overlaps.

## 4. Historical evaluation (Outcome B)

**Exact old metric reproducible: NO.**

Reason: `evaluation.py` depends on removed `build_risk_pipeline`; the pickle has no OOF predictions or split manifest ([`historical_baseline_reproducibility.json`](../reports/data_quality/historical_baseline_reproducibility.json)).

Corrected isolated evaluation ([`historical_automation_risk_grouped_cv.md`](../experiments/historical_reference/reports/historical_automation_risk_grouped_cv.md)):

GroupKFold(5) on `job_role`; TF-IDF inside Pipeline; training-fold mean/median baselines.

| Model | Pooled MAE | Pooled RMSE | Pooled out-of-fold R² | Mean fold R² |
|---|---|---|---|---|
| Training-fold mean baseline | 0.2478 | 0.2869 | -0.0001 | -0.0002 |
| Training-fold median baseline | 0.2479 | 0.2870 | -0.0008 | -0.0010 |
| TF-IDF + Ridge (Pipeline) | 0.2478 | 0.2870 | -0.0002 | -0.0004 |

This is a **corrected, leakage-aware re-evaluation**. It is **not** a percent improvement over the original production model. Under occupation-grouped splits, Ridge did not outperform the training-fold mean baseline.

### 248-row research Ridge (separate experiment; not this dataset)

From [`task_exposure_grouped_cv.md`](../experiments/task_exposure/reports/model_evaluation/task_exposure_grouped_cv.md): mean baseline MAE 0.2046 / RMSE 0.2381 / R² -0.0101; TF-IDF+Ridge pooled MAE 0.1650, RMSE 0.1999, **pooled out-of-fold R² 0.2939**, **mean fold R² 0.2905**. Labels are provisional AI weak supervision.

## 5. Public benchmark evaluation (preserved; not retrained)

From [`model_evaluation.md`](../experiments/task_exposure/reports/public_benchmark/model_evaluation.md) generated 2026-10-03T04:35:55Z. Target: `human_labels` E0/E1/E2. GPT-4 fields not used as target.

| Model | Accuracy | Balanced accuracy | Macro-F1 | Weighted-F1 | MCC |
|---|---|---|---|---|---|
| Majority | 0.546 | 0.333 | 0.235 | 0.385 | 0.000 |
| Stratified dummy | 0.398 | 0.324 | 0.324 | 0.399 | −0.020 |
| TF-IDF + Logistic Regression (C=1.0) | 0.735 | 0.633 | 0.650 | 0.723 | 0.534 |
| TF-IDF + Linear SVM (C=1.0) | 0.726 | 0.640 | 0.652 | 0.719 | 0.522 |

Logistic Regression: log loss 0.634; multiclass ROC-AUC 0.866; E0 F1 0.835; **E1 F1 0.465**; E2 F1 0.650.

The released GPTs-are-GPTs benchmark contains 19,265 task rows with human-derived exposure labels under the published E0/E1/E2 taxonomy. The source methodology describes human annotation of detailed work activities and a subset of tasks, with aggregation to task and occupation levels. This is **not** independent direct human review of every released task, and **not** Prayash-created human validation.

## 6. E1 weakness (read-only)

See [`e1_error_analysis.md`](../experiments/task_exposure/reports/public_benchmark/e1_error_analysis.md).

Test-set E1 support 431. Confusion: 151 correct; 107 predicted E0; 173 predicted E2; false positives 22 from E0 and 45 from E2. Precision/recall/F1 0.693 / 0.350 / 0.465.

**E1 performance is weaker than E0 and E2 in the reported evaluation.** Full-set counts: E0 10,256; E1 2,862; E2 6,147. Duplicate `task_text` rows: 1,273. Row-level test predictions were not archived, so example misclassified strings were not reconstructed (that would require retraining).

Future experiments not run: class weights, character n-grams, extra independent labels, calibration.

## 7. Browser status

Live command: `pytest -q tests/test_browser_resume_workflow.py --run-browser -rs`

| Category | Count |
|---|---|
| Executed | 1 |
| Passed | 1 |
| Failed | 0 |
| Skipped (this command) | 0 |

Without `--run-browser`, the same test is skipped by design. Skip ≠ verification.

From [`BROWSER_VERIFICATION_RESULTS.json`](BROWSER_VERIFICATION_RESULTS.json) after this executed run: PDF/DOCX PASS; unresolved occupation PASS (candidate does not auto-verify); invalid/oversized/prompt-injection/CSRF PASS; Ollama enabled BLOCKED.

## 8. Ollama status

**Blocked/unavailable** in this environment (`http://localhost:11434/api/tags` failed). Advanced fallback PASS. Not recorded as a live-model PASS.

## 9. Provenance

Human-derived benchmark labels ≠ direct independent review of each of 19,265 tasks. Five-level Prayash scores are **not** validated by mapping E0/E1/E2 onto 0.00–1.00.

## 10. Limitations

- No personal job-loss, unemployment, or replacement probability.
- 923 research occupations ≠ 800 product coverage.
- Historical grouped Ridge on `automation_risk.csv` does not beat a mean baseline.
- 248-row Ridge learns provisional AI labels only.
- E1 is the weakest public-benchmark class.
- `train_model.py` remains a **legacy trainer** with corpus-wide TF-IDF (governance risk). Production loads `ml_models/model.pkl`. `bootstrap.ensure_model_artifacts` looks for `ml_models/automation_model.pkl` and may invoke `train_model.py` only if that file is missing.
- Production `risk_score` remains a legacy alias of the historical occupation reference (flagged; not rewritten in this audit).

## Claim boundary

Supported: contextual task exposure; benchmark task classification (research); task overlap; occupation summaries; general career-development guidance.

Not supported: personal job-loss prediction; unemployment probability; replacement probability; individual employment-risk scoring.

## 11. Occupation confirmation security (B0 freeze)

Production path: resume → server-issued candidate → confirm (`candidate_confirmation`) or supported select (`user_selected_occupation`) → 800 ∩ published benchmark → verified lookup. Client `verified_occupation_code`, titles, `confirmation_method`, and allowlist flags are ignored. Session pending records hold only ids, candidate code/title/score, expiry, consume flag, and ownership — not resume text or skills. Allowlist load fails closed (`allowlist_unavailable`) if the 800 file or benchmark is missing, unreadable, or missing required columns.

800 product coverage remains 800 occupations; 923 is the research population. 923-only codes are not selectable in the product flow.

Historical grouped Ridge on `automation_risk.csv` remains approximately mean-baseline (R² ≈ −0.0002). The 248-row R² ≈ 0.29 is a **separate** weak-supervision experiment and is not historical-model improvement. The public TF-IDF classifier stays research-only.

Protected hashes (unchanged by this freeze):

| File | SHA-256 |
|---|---|
| `data/automation_risk.csv` | `d28ca4cbc2ca746c9a033d1953d49d565c3e64a2d8ae54b6ce52bed1826a18f1` |
| `ml_models/model.pkl` | `cca7933cc2fca7b37d405c5d5d0f111a88ec071a69cea536315064d60944398c` |
| Public GPTs-are-GPTs benchmark | `bfc3b219d132449a17105dfc6efc2f0254a3dc613f6192405741c36be10d1299` |
| 800 occupation product file | `26eeee1a06e4919eaf699f7a9da2d0a5f417e625f4d968326ef12daec93c4aa5` |

Default `pytest -q` after B1 quality closure: **205 passed, 3 skipped**. Live Playwright and Ollama are recorded after `--run-browser`.

Remaining after B1 quality closure: job tracker UI, E1 research, human review of the 248-row table, live Ollama when a local model is available, full WCAG/axe audit, React migration.
