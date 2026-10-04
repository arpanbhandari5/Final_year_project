# Phase C / C.1 — Target Job Match

Date: 2026-10-03. No Git commit or push.

## Purpose

Compare a **manually pasted** job description with a **user-owned evidence source**.

Flow:

```text
career goal
→ occupation confirmation
→ resume evidence
→ skill gap
→ one next action
→ target job comparison
→ one next action for the target job
```

Target Job Match does **not** replace occupation confirmation, the 800-product allowlist, or verified benchmark lookup.

## Requirement extraction

Implementation uses a **dedicated deterministic vocabulary** in `job_requirement_vocabulary.py` plus conservative line parsing in `job_match.py`. It does **not** expand `risk_assessor._extract_skills` and does not claim complete job-description understanding.

Required vs preferred uses whole-line headings such as Required, Requirements, Must have, Minimum/Basic qualifications, Preferred, Nice to have, Preferred qualifications, Bonus, Plus. A requirement on the same line as those words is extracted from that line, not treated as a heading.

Ambiguous education/experience phrases that are not vocabulary-normalized remain **review**. Short tokens (`R`, `C`, `Go`) need programming context. `SQL` matches as a word, not as an unbounded substring.

Each extracted requirement includes requirement text, canonical name when normalized, category, required/preferred, later match state, source line, source section, and provenance. Source evidence is never invented.

## Evidence source

- **Current evidence profile:** default. Uses owned `ResumeProfile.extracted_skills`.
- **Choose an existing resume version:** lists `ResumeVersion` rows for the authenticated user only. Skills are derived from that version’s text with the same dedicated vocabulary.
- **Upload a different resume:** `POST /api/resume-versions` through the existing parser (`parse_resume_file`). Creates an owned resume version. Raw resume text is not stored in the Flask session.

Ownership: `resume_version_id` from another user returns 404. Deleted Target Job Match rows do not delete resume versions or the evidence profile.

The result page states: **This analysis used the following evidence source:** followed by `Current evidence profile` or `Resume: <name> · Version: <id> · <timestamp>`.

The current evidence profile option uses **stored extracted evidence**. It is **not** a fresh reparse of an uploaded resume file. Choosing a resume version uses text stored for that owned version after the existing parser has already run.

## Persistence

Table `target_job_matches` (owner `user_id`):

- optional title, company, location
- `description_raw` (owner-only reopen)
- `content_hash` (SHA-256 of stored text)
- evidence source type/key/label and optional `resume_version_id`
- `result_json` (normalized requirements and comparison)
- timestamps

```text
Storage:
Job descriptions are stored privately with the Target Job Match so the user can reopen the analysis.

Ownership:
Only the owning authenticated user may access the stored job description/match.

Deletion:
Deleting the Target Job Match deletes the stored job description associated with that match. Resume versions and the evidence profile are not deleted.

Export:
Export is not currently implemented. export_supported: false

Retention:
The current phase does not implement a time-based retention period. Stored job text remains until the match is deleted, subject to the application's storage lifecycle.

Maximum storage:
The application enforces a maximum accepted job-description input size of 20,000 characters (MAX_TARGET_JOB_DESCRIPTION).

Logging:
Raw job descriptions must not be written to application logs. Create/reuse logs record id, length, and content hash only.
```

**Duplicate behavior (Option B):** the same user, same description hash, and same evidence source key reuse the existing row (`created: false`, HTTP 200). A different evidence source creates a new row. GET never creates a row.

Unauthenticated `/api/target-job-match` GET/POST/PATCH/DELETE return **401**. Authenticated requests with missing or invalid CSRF return **400**. CSRF remains enabled.

## Matching semantics

- **matched:** confirmed/user-added excerpt supports the canonical requirement (including conservative aliases such as Postgres → PostgreSQL).
- **partial:** related or unconfirmed evidence.
- **not evidenced:** no supporting excerpt in the **selected** source. This is **not** “the user does not have the skill.”
- **review:** could not normalize/compare confidently.

## Next action

One recommendation from the first actionable required gap (`not evidenced` → `review` → `partial`). It does not overwrite workspace `ActionItem` or change confirmed occupation.

## ATS limitation

Target Job Match is **not a complete ATS analysis**. It does not score layout, tables, columns, headers/footers, fonts, dates, section structure, keyword stuffing, or hiring/interview probability. Possible future work may be labeled **Resume quality checks**, not a complete ATS scan.

## Security

- `@login_required`; unauthenticated `/api/target-job-match` GET/POST/PATCH/DELETE return **401**
- Authenticated POST/PATCH/DELETE with missing or invalid CSRF return **400**; CSRF remains enabled
- GET `/api/target-job-match` and GET `/api/target-job-match/<id>` are read-only
- Client HTML is stored as text and rendered with `textContent` / DOM APIs in `job-match.js`
- Prompt-injection wording is ordinary job text (no LLM interprets it)
- Does not call occupation confirm/select or benchmark lookup

## Accessibility

Live: `tests/test_browser_job_match.py --run-browser`.

When that suite passes with no axe violations on the tested regions:

```text
Axe-clean for the tested Target Job Match regions
```

This is not a claim of full WCAG compliance.
