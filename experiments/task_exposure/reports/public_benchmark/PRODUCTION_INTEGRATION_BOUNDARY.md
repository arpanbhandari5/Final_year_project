# Production integration boundary

Production E0/E1/E2 is a **verified benchmark lookup**, not the TF-IDF classifier.

- Lookup service: `task_exposure_assessor.lookup_verified_task_exposure`
- Research classifier interface (not used by production routes): `experiments/task_exposure/research_task_classifier.py`
- Offline grouped evaluation: `experiments/task_exposure/evaluate_public_gpts_benchmark.py`

The 248-row provisional AI weak-supervision table (`task_exposure_training.csv` / `final_validated_task_training_table.csv`) is archived for reproducibility. It is **not** loaded by production lookup, the public-benchmark research evaluator, or resume analysis.

`risk_score` / `risk_label` remain legacy aliases of `historical_occupation_reference` only. They are not personal job-loss probabilities.

Do not swap classifier predictions into `contextual_task_exposure`.

## Occupation data contract

Matcher output is a **candidate** (`candidate_code`, `candidate_title`, uncalibrated `matcher_score`). It does not authorize benchmark lookup.

Allowed transitions to a **confirmed** occupation (`verified_occupation_code`):

1. `user_confirmation` — the user confirms a suggested occupation in the UI (`POST /api/confirm-occupation`).
2. `explicit_occupation_code` — a caller supplies an O*NET SOC to `resolve_occupation(occupation_code=...)`, not a cluster candidate.

There is no documented rule that lets a cluster `candidate_code` skip confirmation and become a verified task profile.

`lookup_verified_task_exposure` accepts `ConfirmedOccupation` only. `OccupationCandidate` and legacy `{status: matched, code: ...}` payloads are refused with `candidate_occupation_does_not_authorize_benchmark_lookup`.
