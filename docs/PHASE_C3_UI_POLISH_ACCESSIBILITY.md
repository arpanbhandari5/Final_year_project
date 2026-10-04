# Phase C.3 — UI polish and accessibility expansion

Date: 2026-10-04. No Git commit or push.

## Scope

C.3 improves the existing Target Job Match experience and expands axe coverage on current user-facing pages. Matching, ownership, CSRF, and C.2 evidence semantics are unchanged. Phase D (application tracker) was not started.

## UI changes

- Visual order: target job → evidence source → requirements summary → what evidence supports → where evidence is incomplete → one next action.
- Source copy explains stored evidence vs a fresh file parse. Upload is the only file-parse path on this page.
- Empty, loading (`aria-live` status), and recoverable error states. Deleted resume versions are not silently substituted.
- Statuses `matched` / `partial` / `not evidenced` / `review` use a letter mark plus a text label. Border style differs by status so color is not the only cue.
- Not evidenced is phrased as missing evidence in the selected source, not absence of skill.
- Next action remains a single gap-grounded step.
- Mobile: 44px controls, wrapping excerpts, no extra design system.
- Keyboard: native radios, select, buttons; delete dialog closes with Escape and restores focus.
- Reduced motion: Target Job Match transitions disabled under `prefers-reduced-motion`.
- Auth recovery pages no longer nest a second `<main>` or a one-item `tablist`.

## Accessibility coverage

Axe (no rules disabled) was run on these **audited** pages and states:

- Login / expired-session login (`.auth-split__card`)
- Signup (`.auth-split__card`)
- Forgot password (`.auth-split__card`)
- Homepage hero (`.hero`)
- Methodology hero, privacy hero, insights hero, partnerships hero
- 404 hero
- Workspace empty/populated/mobile
- Resume upload, occupation confirmation, analysis error modal
- Target Job Match empty, source selector, mobile empty, results, evidence details, error, delete dialog

**Not claimed:** full WCAG conformance, admin UI, 500 page (hard to trigger), OTP/reset-password filled states, skills-gap page.

Accurate wording: **axe-clean across the audited current user-facing pages and states listed above.**

## C.2 regression checks

Covered in `tests/test_c3_c2_regression.py` plus existing `tests/test_target_job_match.py`.

- Deleted resume version: new match with that id is 404; it disappears from GET `/api/resume-versions`.
- Deleted match: GET by id 404; list has no `description_raw`; sentinel absent from Target Job Match, JobPosting, and AnalysisSnapshot rows.
- Logs: distinctive sentinel absent from application log records.
- Identical submissions: Option B reuse of the same user + hash + evidence source row (`created` is false on the second POST).
- GET list/detail/page/resume-versions: no new rows, no `updated_at` mutation, evidence JSON unchanged.
- Ownership: `current_user.id` only; client `user_id` / `owner_id` ignored; cross-user GET/PATCH/DELETE 404.
- Protected hashes: B1 freeze values for `data/automation_risk.csv` and `ml_models/model.pkl`; `train_model.py` and the pickle have empty git diff.

## Remaining limitations

- Not an ATS, hiring predictor, or job tracker.
- Conservative vocabulary; many phrases stay `review`.
- Profile comparison still uses stored extracted evidence, not a live file reparse.
- No match-level correction UI beyond the workspace evidence profile.
- Application-level delete does not claim wiping backups or disk remnants.
- Insights/partnerships scans cover the hero region only.
