# Project rules for Final_year_project

- Do not commit, push, tag, merge, or create pull requests unless the user explicitly asks.
- Do not delete or overwrite `data/automation_risk.csv`.
- Do not replace production model artifacts without explicit approval.
- Do not modify unrelated authentication, account, deployment, or resume files.
- Work phase by phase and stop after the current phase.
- Before editing, inspect files and list planned changes.
- Create reproducible scripts instead of manual transformations.
- Preserve dataset sources, versions, release dates, licences, and hashes.
- Never invent task-exposure labels.
- Never copy `automation_risk_score` into a new target.
- Never silently fuzzy-match occupation codes.
- Use scikit-learn Pipeline and leakage-safe validation.
- Group validation by occupation whenever task rows are used.
- Do not call output personal job-loss risk, employment probability, or probability that the user will lose their job.
- Until independently reviewed task-level labels exist and are evaluated, call the output a contextual occupational exposure estimate or a historical benchmark comparison.
- Do not mix Frey–Osborne occupation probabilities with O*NET task statements and present them as current task-level labels.
- Keep raw downloads, normalized data, human labels, experimental features, experimental models, reports, production data, and the production model in separate locations.
- Do not train replacement sources together in one CSV or dump them into `data/`.
- Run tests after every phase.
- Report all failures honestly.
- Show changed files and git status at the end.
- Do not run `muse init --force`; it can overwrite this file.

## Label tracks (do not merge)

1. External historical occupation benchmark: mapped Frey–Osborne `prob`/`probability`, `label_type=historical_occupation_computerisation_probability`, not current task ground truth.
2. Task-level expert-review template: one row per O*NET task with blank independent exposure fields for a written rubric and at least two reviewers.
