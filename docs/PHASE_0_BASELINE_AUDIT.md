# Phase 0 — Post-Phase-D baseline audit

Date: 2026-10-04. Read-only. No Git commit or push. No product, model, or API changes.

## Gate

Current-state matrix and next-phase recommendation are recorded below. **Next build phase is Phase 2**, not Phase 1, 3, or 4.

Product promise: Prayash helps users understand resume evidence and historical/contextual occupation exposure, compare a pasted job, identify explainable skill gaps, choose a next action, find learning resources, and track saved applications. It does not predict personal job loss, hiring success, or employment probability.

```text
home analyze → occupation confirm → workspace loop
workspace / home → Target Job Match → Save this job → Saved jobs
```

## User-facing routes

Auth: `/`, `/login`, `/signup`, `/verify-otp`, `/resend-otp`, `/forgot-password`, `/forgot-password/otp`, `/reset-password/<token>`, `/reset-password/otp`, `/logout`, OAuth Google/GitHub/LinkedIn.

Product: `/workspace`, `/workspace/job-match`, `/workspace/skills-gap`, `/workspace/applications`.

Reference/ops: `/methodology`, `/privacy`, `/insights`, `/partnerships`, `/admin`, `/healthz`.

Stable APIs (do not silently change JSON keys): `/api/upload`, `/api/analyze`, `/api/analyze-stream`, `/api/confirm-occupation`, `/api/select-occupation`, `/api/occupations/selectable`, `/api/occupations/search`, `/api/occupations/<code>`, `/api/occupations/<code>/compare`, `/api/career-profile`, `/api/career-goal`, `/api/evidence-profile` (+ `/correct`, `/import`), `/api/workspace-loop`, `/api/actions/*`, `/api/target-job-match*`, `/api/target-job-match/<id>/save-application`, `/api/resume-versions`, `/api/applications*`, `/api/jobs`, `/api/jobs/analyze` (legacy, unused by TJM/applications UI), `/api/skills-gap/*`, `/api/career-paths`, `/api/learning-roadmap`, `/api/career-chat*`, `/api/compare`, `/api/csrf-token`.

## Capability matrix

**Exists — do not rebuild:** resume upload/paste; occupation confirm/select; historical occupation reference via `ml_models/model.pkl`; Target Job Match C.1–C.3; skills-gap; keyword career paths; `courses.pkl` roadmap lookup; Phase D application tracker; workspace loop; Flask/Jinja/vanilla JS; C.3 a11y patterns on TJM/workspace/applications.

**Partial — extend later:** `CareerGoal` and `/api/career-goal`; `ResumeProfile` (analyze does not auto-fill; corrections overwrite the same JSON); TJM statuses `matched|partial|not evidenced|review` without Phase 4 summary contract or correction panel; privacy page claims resume is not stored while `ResumeVersion` and `TargetJobMatch` persist owned text; primary nav still includes research pages.

**Missing:** Phase 2 guided start (home `#start-here` is persona cards, not intent routing); `UserCorrection` / `EvidenceItem` / `SkillMention`; ordered learning progress (Phase 6); read-only job discovery (Phase 7); export/consent/account deletion (Phase 8).

**Out of scope:** personal job-loss, employment, hiring, or interview probability; ATS ranking; scraping; auto-apply; cloud LLM rewrite; React/Next; Kanban CRM; invented task labels; merging historical occupation scores with expert task labels.

## Data, security, tests

SQLite unique indexes `uq_applications_user_job` and `uq_job_postings_user_hash`. Ownership from `current_user.id`. CSRF required on mutations; unauthenticated application/TJM CSRF → 401. No time-based retention. Delete Target Job Match NULLs `target_job_match_id`.

Last recorded suite: 238 passed, 6 skipped. Live browser tests use `--run-browser`. Pytest uses a temp database (`tests/conftest.py`).

## Protected and dirty files

Protected: `data/automation_risk.csv`, `ml_models/model.pkl`, `train_model.py`. Already dirty, do not expand: `evaluation.py`, `risk_assessor.py`. Do not treat the whole dirty tree as Phase 0 cleanup.

`AGENTS.md` currently appends a Phase D prompt after the short rules. Do not rewrite it in this phase.

## Duplicates and unsafe rendering

Duplicate analyze/skills-gap/roadmap surfaces on Home, Insights, and `/workspace/skills-gap`. Two JD matchers: `job_match.py` vs `_job_skill_breakdown` / `POST /api/jobs/analyze`. Unescaped `innerHTML` on home skills-gap and Insights results. Do not migrate to React to fix this.

## Why not Phase 1, 3, or 4 next

Working-tree `evaluation.py` is a shim to `scripts/evaluate_historical_baseline.py`. Offline GroupKFold already exists under `experiments/historical_reference/`. Do not replace `model.pkl`. Occupation confirmation and CareerGoal already exist (Phase 3 is an extension). Target Job Match plus Save this job already exist (Phase 4 is an extension).

## Next phase

**Phase 2 — career-start navigation.** Plan only: [PHASE_2_CAREER_START_NAV.md](PHASE_2_CAREER_START_NAV.md). Do not implement until that plan is reviewed.

Allowed this phase: documentation only. Protected: production data, pickles, trainer, unrelated auth.
