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

## Cursor Cloud specific instructions

- Dependencies live in `.venv`. The default image needs `python3-venv` before `python3 -m venv .venv`. Use `.venv/bin/python` and `.venv/bin/pytest`.
- `ml_models/*.pkl` is gitignored. Generate missing `model.pkl` and `courses.pkl` with `.venv/bin/python train_model.py`. `python app.py` also calls `bootstrap.ensure_model_artifacts()`, which retrains when `ml_models/automation_model.pkl` is absent.
- Dev server: `.venv/bin/python app.py` on `0.0.0.0:5000`. `GET /healthz` should report `"ml_pipeline": "ready"`.
- Local defaults without `.env`: admin `admin@prayash.local` / `prayash-admin`. Ollama, OAuth, and SMTP are optional. With mail unset, OTP codes are printed in the server log.
- Pytest is not in `requirements.txt`. Install `pytest>=9.0.3`. CI-equivalent command: `DATABASE_URL=sqlite:///test_ci.db MAIL_USERNAME= MAIL_PASSWORD= SMTP_USERNAME= SMTP_PASSWORD= FLASK_SECRET_KEY=ci-test-secret-key-do-not-use-in-production .venv/bin/pytest tests/ -q --tb=short`.
- `npm test` is a stub. The UI is served from `templates/` and `static/` and does not need `npm install`.
