# Prayash Baseline Inventory

Date: 2026-09-29

## Scope

This baseline covers the active Flask application in `app.py`, persistence definitions in `storage.py`, resume/risk logic in `risk_assessor.py`, evaluation helpers in `evaluation.py`, the existing test suite, and the local SQLite database `prayash.db`.

The worktree already contained unrelated modified and untracked files. This document records the observed state without reverting those changes.

## Environment and Gates

Python environment: workspace `.venv`, Python 3.13.14.

| Gate | Command | Result |
|---|---|---|
| Compilation | `python -m compileall -q .` | Pass; zero compilation errors and no output |
| Tests | `pytest -q` | Pass; `7 passed, 13 warnings` |
| Dependency audit | `pip-audit` | Fail baseline gate; 2 findings for installed `pytest 8.4.2`, fixed in `9.0.3` |
| Static scan | `bandit -r . -x ./venv,./.venv` | Scan completed; 26 low-severity findings, 0 medium, 0 high |

The commands were executed through `.venv` using `python -m` equivalents where the executable was not on PATH. Pytest warnings are existing deprecations for `datetime.utcnow()` and SQLAlchemy `Query.get()`.

### Bandit baseline findings

The low-severity findings are concentrated in existing code:

- `bootstrap.py`: subprocess import and a checked subprocess invocation (`B404`, `B603`).
- `evaluation.py`: broad exception followed by `pass` (`B110`).
- `tests/test_overhaul.py`: test credentials and pytest `assert` statements (`B105`, `B101`).

No medium- or high-severity Bandit findings were reported.

### Dependency audit limitation

`pip-audit` was run against the complete configured environment, not only production requirements. The only reported issue is the installed test dependency `pytest 8.4.2`. The declared `requirements.txt` does not declare pytest.

## Active Flask Routes

Routes discovered in `app.py`:

- `GET /`: landing page.
- `GET, POST /login`: session login.
- `GET, POST /signup`: account creation.
- `POST /logout`: authenticated logout.
- `GET /workspace`: authenticated workspace.
- `GET /api/career-profile`: authenticated profile read.
- `PUT /api/career-profile`: authenticated intent and target-role save.
- `GET /methodology`: methodology page.
- `GET /privacy`: privacy page.
- `GET /insights`: insights page.
- `GET, POST /partnerships`: partnership request form.
- `GET /admin`: admin-only dashboard.
- `GET /admin/evaluation-access`: explicitly configured evaluation shortcut.
- `POST /admin/partnerships/<int:request_id>/reply`: admin partnership response.
- `POST /admin/logout`: authenticated admin logout.
- `GET /healthz`: health check.
- `POST /api/feedback`: feedback capture.
- `POST /api/upload`: resume upload and analysis.
- `POST /api/analyze`: resume analysis alias.

API routes that access user-owned profile data require Flask-Login authentication and filter through the authenticated `current_user.id`.

## Active SQLAlchemy Models

Defined in `storage.py`:

- `User`: credentials, role, active state, and creation timestamp.
- `CareerProfile`: one profile per user, storing intent, target role, source, confidence, and timestamps.
- `Upload`: resume metadata, analysis mode, risk band/score, reasoning, and optional user ownership.
- `Feedback`: optional user/upload association, rating, message, and timestamp.
- `PartnershipRequest`: organization contact, use case, status, notes, and response metadata.

The lightweight migration currently adds missing partnership response columns when needed. `db.create_all()` creates missing active model tables but does not remove or migrate unrelated existing tables.

## SQLite State

The inspected file is `prayash.db`. SQLite CLI was unavailable, so the schema was inspected with Python's standard-library `sqlite3` module.

Observed application tables:

- `users`
- `uploads`
- `feedback`
- `partnership_requests`
- `career_profiles`
- `password_reset_tokens`
- `oauth_accounts`
- `consent_records`
- `recommendation_feedback`
- `user_corrections`
- `audit_logs`

SQLite also contains indexes for usernames, timestamps, ownership fields, partnership status/contact, token hashes, and the unique `career_profiles.user_id` constraint.

The first five tables correspond to the active models in `storage.py`. The remaining six tables are present on disk but have no corresponding active model class in the inspected `storage.py`; they appear to be legacy or extended schema state and should be reconciled before future migrations.

## Ignore Rules

`.gitignore` now covers:

- `.venv/` and `venv/`
- Python caches: `__pycache__/`, `*.pyc`
- SQLite files: `*.db`, `*.sqlite`, `*.sqlite3`
- Model binaries: `ml_models/*.pkl`
- Test/build output and local logs already present in the repository

## Baseline Risks and Follow-up

- Upgrade the environment's pytest to `9.0.3` or later before treating `pip-audit` as clean.
- Reconcile the six on-disk legacy/extended tables with the active ORM and migration strategy.
- Review low-severity Bandit findings during the security-hardening phase.
- Existing test warnings indicate future compatibility work for timezone-aware datetimes and SQLAlchemy session-based lookup APIs.
