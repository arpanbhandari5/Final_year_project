# Phase B1 product loop

Date: 2026-10-03. No Git commit or push.

## Correct B1 status

```text
B1 product loop and tested-region accessibility: complete
Full application accessibility: not yet complete
```

This is **not** a full WCAG audit.

## What shipped

Logged-in workspace loop: career goal → resume evidence → one skill gap → one next action.

## Accessibility

```text
Axe-clean for the tested B1 regions
```

- Axe version: `@axe-core/playwright` **4.13.0** (`package-lock.json` resolved `https://registry.npmjs.org/@axe-core/playwright/-/playwright-4.13.0.tgz`). Engine: `axe-core` **4.13.0** via `node_modules/axe-core/axe.min.js`.
- Reproducibility: Python Playwright tests inject that locked `axe.min.js` with the page CSP nonce (`tests/axe_helper.py`). `npm ci` was **not** run because `package.json` / `package-lock.json` already contain the intentional uncommitted axe addition; `npm ci` would reinstall from that lock (safe) but was skipped to avoid rewriting `node_modules` during this gate. Installed `node_modules/@axe-core/playwright/package.json` reports `4.13.0`.
- Regions: workspace `.page-hero` + `#career-goal`; resume `#analysis`; confirmation/error `[data-result-modal]`; expired session `.auth-split__card`; 390×844 mobile on workspace and confirmation.
- Not covered: homepage/marketing, open career-chat, admin, Insights, every modal/state.

### Findings

- **Fixed:** visible authentication labels (`<label for>`); nested main; mode-toggle contrast; occupation picker label; closed overlay `inert`; escaped analysis error HTML; file/compare labels.
- **Intentional exception:** none on included B1 regions (no global rule disables).
- **Not applicable:** marketing pages, career-chat (outside include), job-tracker UI.

### Auth labels

Visible labels were added for login, signup, forgot-password email, reset password, and a verification-code legend. `aria-label` remains only on icon-only controls (password reveal, social buttons already have visible text, OTP digits as “Digit n of 6” inside a labelled fieldset).

## Audit of the broad tracked diff (read-only)

The ~32-file / ~2500-line tracked diff is **not** an accessibility-only change. It carries **B0 occupation authorization + B1 product loop** plus later quality fixes.

### B1-related changes

- `templates/workspace.html`, `static/workspace-loop.js`, `next_action.py`, career-goal/action storage, skip-link/`#main-content`, loop CSS.
- `templates/auth.html` / `base.html` / `index.html` accessibility.
- `static/script.js` occupation confirm/select UI, escaped error rendering, shortcuts `inert`.
- `static/career-chat.js`: closed-panel `aria-hidden` / `inert` / `aria-modal` only. No API contract change. Safe to retain.
- `package.json` / `package-lock.json`: `@axe-core/playwright` ^4.13.0 only as the intended new devDependency.

### Unrelated-but-intentional changes (prior phases, retain)

- `app.py` / `storage.py` / `occupation_authorization.py`: B0 fail-closed occupation architecture.
- `risk_assessor.py` / `evaluation.py`: historical-reference wording and lookup plumbing from earlier methodology work. **Not modified in this label/Phase C pass.** `train_model.py` was not in the tracked diff. `ml_models/model.pkl` hash unchanged.
- Label/dataset docs, `replacement_data/*`, tests for OTP/auth/career-goal, README, `.gitignore`.
- Templates `methodology.html` / `report.html` / `admin.html`: disclaimer/copy from earlier phases.

### Unexpected changes requiring correction

- None found that required reverting. Career-chat behavior is closed-state accessibility only.

## Ollama

```text
Ollama fallback: verified
Live Ollama narrative: blocked
```

## Browser (separate live commands; skips are not passes)

Command group: `pytest --run-browser` on each file.

- Resume workflow (`tests/test_browser_resume_workflow.py --run-browser -rs`): 1 passed / 0 failed / 0 skipped (executed)
- Workspace workflow (`tests/test_browser_workspace_loop.py --run-browser`): 1 passed / 0 failed / 0 skipped (executed)
- Accessibility workflow (`tests/test_browser_accessibility.py --run-browser`): 1 passed / 0 failed / 0 skipped (executed)

Default `pytest -q` (no `--run-browser`): 209 passed, 5 skipped (four `browser_live` files plus one existing skip).

## Full pytest

`pytest -q`: 209 passed, 5 skipped

## Protected hashes (baseline)

- `data/automation_risk.csv` `d28ca4cbc2ca746c9a033d1953d49d565c3e64a2d8ae54b6ce52bed1826a18f1`
- `ml_models/model.pkl` `cca7933cc2fca7b37d405c5d5d0f111a88ec071a69cea536315064d60944398c`
- public benchmark `bfc3b219d132449a17105dfc6efc2f0254a3dc613f6192405741c36be10d1299`
- 800 product file `26eeee1a06e4919eaf699f7a9da2d0a5f417e625f4d968326ef12daec93c4aa5`
