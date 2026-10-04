# Public GPTs-are-GPTs classification experiment

**Research model:** GPTs-are-GPTs public benchmark — 923 occupations (`prayash-task-exposure-gpts-are-gpts-v1`, research-only).

**Product subset:** Prayash common-occupation coverage — 800 occupations. Not the training population.

Separate from the 248-row `baseline_provisional_ai_weak_supervision` experiment, the deferred Prayash human-review worksheets, the production model, and `evaluation.py`.

Human-review track status: `deferred_due_to_unavailable_independent_reviewers`

Five-level 0.00–1.00 rubric: `historical/deferred Prayash five-level rubric` (not validated by E0/E1/E2).

Primary target: `human_labels` in {E0, E1, E2}.
E0 = no direct LLM exposure; E1 = direct LLM exposure; E2 = exposure through an LLM-powered application.

See `ARCHITECTURE.md`, `MODEL_CARD.md`, `USER_FACING_COPY.md`, `CAREER_ACTION_LAYER.md`.

This experiment evaluates task-level classification against a published GPTs-are-GPTs exposure taxonomy using human-derived benchmark labels. The benchmark provides an external reference and does not constitute new human validation of Prayash's original 0-1 scoring rubric.

The released GPTs-are-GPTs benchmark contains 19,265 task rows with human-derived exposure labels under its published E0/E1/E2 taxonomy. Direct task-level independent review of every row is not recoverable from the released file.

E1 performance is weaker than E0 and E2 in the reported evaluation.

The model does not predict personal job-loss risk, employment probability, or individual displacement.
