# Phase 2 — Career-start navigation (Plan)

Date: 2026-10-04. **Plan only. Do not implement until this document is reviewed and approved.**

Depends on [PHASE_0_BASELINE_AUDIT.md](PHASE_0_BASELINE_AUDIT.md). Does not rebuild Target Job Match, the application tracker, occupation confirmation, or the production model.

## Goal

Make existing capabilities easier to reach. Route four start intents into **current** pages. Tighten primary navigation. Keep Flask/Jinja/vanilla JavaScript, CSRF, occupation authorization, and existing API JSON keys.

## Current implementation to preserve

- `#start-here` on [templates/index.html](../templates/index.html) is four **persona** buttons (`student`, `job-seeker`, `career-switcher`, `new-workforce`) that only change copy via [static/script.js](../static/script.js). It does not route into workspace, Target Job Match, or analysis.
- Authenticated primary nav in [templates/base.html](../templates/base.html) includes Home, Start Here, Resources, Methodology, Privacy, Insights, Partnerships, Workspace, hash links, **Target Job Match**, **Saved jobs**.
- Workspace local nav: Career goal, Resume & evidence, Learning & actions, Target Job Match, Saved jobs ([templates/workspace.html](../templates/workspace.html)).
- Existing destinations:
  - Career goal: `/workspace#career-goal` (`/api/career-goal`, selectable occupations).
  - Resume: `/#analysis` (guest-capable) and `/workspace#resume-evidence`.
  - Job description: `/workspace/job-match` (login required).
  - Explore: `/workspace/skills-gap` and `/insights` (do not create a new recommendation engine).
  - Applications: `/workspace/applications` (keep URL).
  - Privacy: `/privacy` (do not build Phase 8 account controls).

## Existing behavior that must not change

- `POST /api/confirm-occupation`, `/api/select-occupation`, Target Job Match APIs, application save/list/patch/delete.
- Application uniqueness, CSRF, ownership, deleted-comparison NULL.
- Historical/contextual wording (not personal job-loss or hiring probability).
- Page URLs: `/workspace`, `/workspace/job-match`, `/workspace/applications`, `/workspace/skills-gap`, `/privacy`.

## Proposed build (after approval only)

### Guided start (`#start-here`)

Replace or add beside persona cards a four-choice group (links, not a new assessment product):

| Choice | Authenticated | Guest |
| --- | --- | --- |
| I know my target role | `/workspace#career-goal` | `/login?next=/workspace%23career-goal` |
| I have a job description | `/workspace/job-match` | `/login?next=/workspace/job-match` |
| I want to explore careers | `/workspace/skills-gap` | `/insights` (existing explore surface; login not required) |
| I want to understand my resume | `/#analysis` | `/#analysis` |

Keep `id="start-here"` so current nav/footer hashes still work. Persona cards may remain below as optional copy, or be removed only if tests prove they are unused duplicate UX — default: **keep** persona cards, add the intent links as the primary start row.

Hero “Start my assessment” already points at `#analysis`. Leave it.

### Primary navigation

Authenticated primary nav (order):

1. Home (`/`)
2. Career goal (`/workspace#career-goal`)
3. Resume & evidence (`/workspace#resume-evidence`)
4. Target jobs — **same URL** `/workspace/job-match`; visible label may stay “Target Job Match” or become “Target jobs” with the old phrase still on the page H1
5. Learning & actions (`/workspace#learning-actions`)
6. Applications — **same URL** `/workspace/applications`; primary-nav label “Applications”; page may still say “Saved jobs”
7. Privacy (`/privacy`)

Guest primary nav: Home, Start Here (`/#start-here`), Privacy, Login, Sign Up. Do not hide resume analysis on the home page.

Move Methodology, Insights, Partnerships, Resources out of the default primary list into the **footer** (already linked). Keep Admin when `admin_authenticated`. Keep Workspace as optional extra or drop if the hash links replace it — prefer **keep one Workspace** link to `/workspace` so B1 tests that look for Workspace do not break; if a test asserts exact nav HTML, update that test in this phase.

Do not add a fake Settings app. Privacy is the Phase 2 stand-in. Phase 8 owns retention/export.

### Compatibility

- Do not delete `/insights`, `/methodology`, `/partnerships`, `/workspace/skills-gap`.
- Do not add redirects unless a URL actually moves (none should move).
- Do not change `active_page` semantics except if a new `active_page` value is needed for Target jobs / applications highlighting.

### Design

Reuse C.3 tokens (`path-card`, `button`, `nav-link`, existing focus styles). No React/Next/Tailwind. One next-action emphasis on the start row. Keyboard: the four choices must be links or buttons inside a labelled group.

### XSS (only if those files are edited)

If [static/script.js](../static/script.js) or [templates/insights.html](../templates/insights.html) are opened for nav-related copy, escape skills-gap/Insights `innerHTML` interpolations. Do **not** open them solely to start a Phase 10 rewrite.

## Allowed files (Phase 2 build)

- `templates/base.html`
- `templates/index.html`
- `templates/workspace.html`
- `templates/applications.html` (label only, if nav says Applications)
- `static/styles.css` (spacing for start chooser only)
- `tests/test_phase_2_navigation.py` (new)
- `tests/test_browser_accessibility.py` or a small addition to `tests/test_browser_resume_workflow.py` / new `tests/test_browser_navigation.py` if live Flask is used
- `docs/PHASE_2_CAREER_START_NAV.md` (this file: mark complete after build)

Optional, only if a test currently hard-codes nav children: that test file.

**Do not edit:** `job_match.py`, `job_requirement_vocabulary.py`, application/TJM API handlers beyond zero-touch, `storage.py`, `risk_assessor.py`, `evaluation.py`, `train_model.py`, `data/automation_risk.csv`, `ml_models/model.pkl`, `occupation_authorization.py`, auth templates, `AGENTS.md`.

Prefer **not** editing `app.py`. If `active_page` highlighting needs a helper, a tiny template-only class is enough.

## Protected files

`data/automation_risk.csv`, `ml_models/model.pkl`, `train_model.py`, `evaluation.py`, `risk_assessor.py` (already dirty — do not expand).

## API / schema

None. No new tables. No JSON key changes.

## Security and privacy

- Login `next=` must stay an internal path (existing login already uses `next`). Do not introduce open redirects.
- Do not log resume or job text.
- Do not claim privacy page is now accurate about `ResumeVersion` storage (Phase 8).

## Test plan

- Guest home: four start choices present; Methodology not required in primary nav; `#analysis` still works.
- Authenticated: each intent URL returns 200; applications and job-match still login-gated.
- Hash links `#career-goal`, `#resume-evidence`, `#learning-actions` still exist on workspace.
- Keyboard: Tab to start choices; visible focus.
- Mobile: 390px nav toggle still opens links; no horizontal overflow on start row.
- Regression: `tests/test_c3_c2_regression.py`, `tests/test_browser_workspace_loop.py`, `tests/test_browser_job_match.py`, `tests/test_browser_applications.py`, `tests/test_occupation_confirmation_security.py`.
- Axe on `#start-here` and `nav[aria-label="Primary"]` when `--run-browser` and Flask are available; do not skip live tests silently if the server is up.
- Copy: no ATS score, hiring probability, or job-loss probability in the new start/nav strings.

## Migration / rollback

No database migration. Rollback is template/CSS revert.

## Out of scope

Phase 1 model work; Phase 3 evidence models; Phase 4 matcher/correction panel; Phase 5 transition comparison; Phase 6 course engine; Phase 7 job boards; Phase 8 export/delete; Phase 9 coaching; merging or deleting Insights/skills-gap backends; React; scraping; hiring prediction.

## Review checklist

- Does not rebuild TJM or applications.
- Does not change protected artifacts.
- Preserves Flask/Jinja/vanilla JS, CSRF, ownership.
- No probability claims.
- Stops after this phase once built.

## Status

Implemented 2026-10-04. No Git commit or push. No ML, schema, Target Job Match matcher, or application API changes.

## Follow-up (not Phase 2)

Privacy copy still says resumes are not stored, while `ResumeVersion.content_text` and Target Job Match/job posting text persist. Correct wording or storage in Phase 8. Do not treat `/privacy` as accurate until then.
Correction 1: Add explicit guest redirect assertions
The test plan says:
“Authenticated: each intent URL returns 200; applications and job-match still login-gated.”
Make the expected behavior more precise:
Authenticated /workspace/job-match → 200
Authenticated /workspace/applications → 200
Guest /workspace/job-match → redirect to /login?next=...
Guest /workspace/applications → redirect to login
Guest /#analysis → accessible
Guest /insights → accessible if that remains the selected explore surface
Do not expect protected pages to return 200 for guests.
Correction 2: Decide whether persona cards remain
The plan says persona cards may remain, with the new intent links added as the primary row. This is safe, but it may create duplicated choices.
My recommendation:
Keep the persona cards in Phase 2 if removing them risks breaking tests or existing UX.
Make the four intent links the clear primary action.
Reassess whether the persona cards should be removed in a later UI review.
Correction 3: Do not silently change “Saved jobs” everywhere
Changing the primary navigation label to Applications is reasonable, but the transition should be clear.
Recommended wording:
Navigation: Applications
Page heading: Saved jobs and applications
Helper text: “Track jobs you saved, applied to, and followed up on.”
This avoids confusing existing users.
Correction 4: Track the privacy mismatch separately
The plan correctly says not to build Phase 8 now. However, it also identifies that privacy copy says resumes are not stored while the database stores resume and job text.
Do not ignore this finding. Create a follow-up issue or Phase 0.5 task to:
Correct the privacy wording, or
Change the storage behavior
Do not claim the current privacy page is accurate until this is resolved.
Correction 5: Treat XSS remediation as conditional but important
The plan sensibly avoids a frontend rewrite. If the unsafe innerHTML paths are not touched in Phase 2, do not expand the phase unnecessarily.
However, if the new navigation work opens or modifies those files, fix the unsafe interpolation in the same focused change and add a regression test.
Allowed-file list
The proposed list is appropriate:
text
templates/base.html
templates/index.html
templates/workspace.html
templates/applications.html
static/styles.css
focused navigation tests
browser/accessibility tests
docs/PHASE_2_CAREER_START_NAV.md
The protected-file list is also correct. Cursor should not modify:
text
job_match.py
storage.py
risk_assessor.py
evaluation.py
train_model.py
occupation_authorization.py
AGENTS.md
ml_models/model.pkl
data/automation_risk.csv
Final recommendation
Approve this Phase 2 plan for implementation, with these small adjustments:
Add exact guest redirect assertions.
Correctly preserve /workspace/job-match.
Use a clear “Applications” versus “Saved jobs” transition.
Track the privacy-copy mismatch as a separate follow-up.
Keep XSS fixes conditional on touching the affected files.
The build should remain frontend/navigation-focused. After implementation, require:
text
pytest focused navigation tests
browser guest/authenticated tests
mobile and keyboard checks
axe checks
git diff --check
git status
No ML, database, Target Job Match, or application-tracker changes are needed for this phase.