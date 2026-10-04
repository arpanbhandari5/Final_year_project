# Prayash task-exposure architecture

This document records the isolated research/product split. It does not change production scoring.

```text
                    ┌─────────────────────────────┐
                    │ GPTs-are-GPTs benchmark     │
                    │ 19,265 tasks / 923 jobs     │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Task Exposure Classifier    │
                    │ E0 / E1 / E2               │
                    │ Occupation-held-out eval   │
                    │ prayash-task-exposure-      │
                    │ gpts-are-gpts-v1            │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          ┌──────────────────┐          ┌──────────────────┐
          │ 923 research     │          │ 800 common-job  │
          │ benchmark scope  │          │ product subset   │
          └──────────────────┘          └────────┬─────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │ Contextual task         │
                                    │ exposure / overlap      │
                                    │ + career-action guidance│
                                    └────────────────────────┘
```

Separate:

```text
Historical 0–1 rubric  →  deferred_due_to_unavailable_independent_reviewers
248-row AI experiment  →  baseline_provisional_ai_weak_supervision
Individual employment-outcome prediction  →  future research only
```

## Layers

| Layer | Population | Role |
|---|---|---|
| MODEL / RESEARCH | 923 occupations, 19,265 tasks | Train/evaluate E0/E1/E2 classifier |
| PRODUCT COVERAGE | 800 occupations | Search, UI coverage, dashboards, summaries |
| USER-FACING | contextual copy | Task exposure, overlap, career-action guidance |

The 800 selection was **not** the training population. Absence from the 800 subset does not mean absence from the 923-occupation model. Absence from both: do not fabricate a classification.

## Supported vs unsupported

Supported: contextual task exposure; task overlap; general career-development guidance.

Unsupported: personal job-loss prediction; unemployment probability; replacement probability; individual employment-risk score; occupational disappearance; “safe/unsafe/AI-proof job” as model conclusions.

## Production

`prayash-task-exposure-gpts-are-gpts-v1` is **research-only**. It is not wired into `app.py`, `risk_assessor.py`, `storage.py`, `train_model.py`, or `evaluation.py`.
