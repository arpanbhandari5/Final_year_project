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

## Cursor Cloud specific instructions

- Run the Flask app with `python app.py`. It listens on port 5000. Create `instance/` first (`mkdir -p instance`). SQLite will not create that directory, and startup fails with `unable to open database file` when it is missing. The base image provides `python3` only; setup links `/usr/local/bin/python` to it. Install dependencies with `python -m pip install -r requirements.txt` (user site under `~/.local`). Tests also need `python -m pip install "pytest>=9.0.3"`. The `package.json` dependencies are not required to run or test this app.
- Generate `ml_models/model.pkl` and `ml_models/courses.pkl` with `python train_model.py` when they are missing. `bootstrap.ensure_model_artifacts()` checks `ml_models/automation_model.pkl` and retrains on every `python app.py` launch if that file is absent, while training writes `model.pkl`. Link `automation_model.pkl` to `model.pkl` so startup does not retrain. Do not replace anything under `model_artifacts/production`.
- `GET /healthz` should report `ml_pipeline` as `ready`. The primary action is pasting resume text on `/#analysis` and choosing Run analysis, or `POST /api/analyze` with `resume_text` and a CSRF token from `GET /api/csrf-token`. Without a `.env` file the seeded accounts are student `student` / `Student@123` and admin `admin@prayash.local` / `prayash-admin`. OAuth, SMTP, and Ollama are optional. Leave mail credentials empty so OTP codes stay in the server log.
- The CI test command is `python -m pytest tests/ -v --tb=short` with `MAIL_USERNAME`, `MAIL_PASSWORD`, `SMTP_USERNAME`, and `SMTP_PASSWORD` empty. Collection currently fails in `tests/test_onet_engine.py` and `tests/test_overhaul.py` because those imports are missing from the app, and some other tests expect `app.config["ADMIN_EMAIL"]` plus routes that are not registered. Those failures are in the repository, not missing packages.

## Label tracks (do not merge)

1. External historical occupation benchmark: mapped Frey–Osborne `prob`/`probability`, `label_type=historical_occupation_computerisation_probability`, not current task ground truth.
2. Task-level expert-review template: one row per O*NET task with blank independent exposure fields for a written rubric and at least two reviewers.
