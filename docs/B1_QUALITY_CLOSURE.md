# B1 quality closure

Date: 2026-10-03. No Git commit or push. axe-core is **not** in the repo (`package.json` has Playwright only); it was not added.

## Baseline

- B0: session-bound confirm/select, 800∩benchmark allowlist, CSRF on those POSTs, fail-closed allowlist, no resume in session cookie.
- B1: `/workspace` loop plus `/api/career-goal`, evidence, `/api/workspace-loop`, `/api/actions/refresh`, `/api/actions/<id>`. All of those APIs use `@login_required` and `current_user.id` (no client user id).
- Playwright: `tests/test_browser_resume_workflow.py` and `tests/test_browser_workspace_loop.py` execute only with `--run-browser`.
- Protected hashes before this pass matched the B0 freeze list.

## Defects found and fixed

1. **GET `/api/workspace-loop` wrote ActionItem rows** when none existed. GET is now read-only; `POST /api/actions/refresh` persists.
2. **Skip link / main landmark** missing. Added `Skip to main content` → `#main-content`.
3. **Workspace live regions and control names** incomplete. Status/action use `aria-live`; evidence buttons have `aria-label`; form errors have `id` + `aria-describedby`.
4. Broken CSS insertion around `html { scroll-behavior }` while adding skip-link styles — repaired.

## CSRF

Flask-WTF remains enabled in production config. Workspace JS sends `X-CSRFToken` on POST/PATCH/DELETE. Tests cover missing/invalid/valid CSRF on career-goal, evidence correction, and action refresh.

## Auth

Unauthenticated GET/POST/PATCH/DELETE on B1 APIs returns 401.

## Accessibility / responsive

Partial closure: skip link, labelled fields, live regions, 44px evidence buttons, `prefers-reduced-motion` on loop cards, mobile grid collapse, Playwright 390px viewport. Not a full WCAG audit; axe-core not installed.

## Ollama

BLOCKED unless a local model is running. Not treated as a pass.

## Tests

- Default `pytest -q`: 205 passed, 3 skipped
- Focused CSRF/auth gate: `tests/test_b1_quality_gate.py` passed
- Live Playwright: resume **1 passed (executed)**; workspace **1 passed (executed)** including skip-link + 390px viewport
- axe-core: not installed; not added
- Ollama: BLOCKED

Protected hashes unchanged:

- `data/automation_risk.csv` `d28ca4cbc2ca746c9a033d1953d49d565c3e64a2d8ae54b6ce52bed1826a18f1`
- `ml_models/model.pkl` `cca7933cc2fca7b37d405c5d5d0f111a88ec071a69cea536315064d60944398c`
- public benchmark `bfc3b219d132449a17105dfc6efc2f0254a3dc613f6192405741c36be10d1299`
- 800 product file `26eeee1a06e4919eaf699f7a9da2d0a5f417e625f4d968326ef12daec93c4aa5`

## Deferred

Job tracker, E1 research, cloud LLM, React, full design-system/contrast audit.
