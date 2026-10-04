# Phase D — Minimal Application Action Tracking

Date: 2026-10-04. No Git commit or push.

## Scope

Close the product loop after Target Job Match by letting the authenticated owner **save a compared job** and record **their own next actions**.

This is **not** an ATS, not hiring/interview/employment prediction, and not scraping or auto-apply.

```text
target job comparison
→ save this job
→ status, note, follow-up, owned resume version
→ reopen comparison when it still exists
```

UI copy:

> This list records jobs you chose to track and what you did next. It is not an ATS score or a prediction that you will be hired.

## What is stored

| Record | Stored fields | Raw job description? |
| --- | --- | --- |
| `applications` | status, notes (max 4000), follow-up date, owned resume_version_id, optional target_job_match_id, job_posting_id, user_id | No |
| `job_postings` | title, company, source_url, **description_raw**, content hash, user_id | **Yes**, privately, for the saved job the user chose to track |
| List/GET application JSON | title, company, status, notes, dates, ids | **No** `description_raw` |

Full resume files are not copied into the application row. An optional **owned** resume version id may be attached.

## How long data remains

There is **no time-based retention period** in Phase D. Saved jobs and their privately stored job-posting text remain until the owner deletes the application row (and any leftover posting with no remaining applications), subject to the normal application database lifecycle.

**Archive is not implemented.** There is no archived/hidden state. A saved job is either an active application row or it has been deleted.

## What delete means

- **Delete Target Job Match:** removes that comparison and **its** stored job text. Applications that pointed at it keep their tracker row. `target_job_match_id` is set to **NULL**. `comparison_available` is false. Save-from-match with the old id returns 404. Deleted comparison text is not restored from the client.
- **Delete application** (`DELETE /api/applications/<id>`): removes that user’s tracker row (status, notes, follow-up, attachments). Cross-user delete returns 404.
- Account-level wipe of all job text is **not** implemented in Phase D.

## Logs

Create/reuse/delete logs record ids and content **hashes** only. Raw job descriptions, notes, and resume text must not appear in application logs.

## Uniqueness (database)

Duplicate **Save this job** cannot create a second active application for the same user and job posting.

Enforced by SQLite unique indexes (also declared on the SQLAlchemy models):

- `uq_applications_user_job` on `applications(user_id, job_posting_id)`
- `uq_job_postings_user_hash` on `job_postings(user_id, content_hash)`

Existing databases: `_ensure_sqlite_workspace_columns` adds `target_job_match_id` if missing, deduplicates leftover rows, then creates the unique indexes.

Python still looks up an existing row first; the unique index is the authoritative guard.

## Save path

`POST /api/target-job-match/<id>/save-application` copies title, company, and job text from the **owned** match. Client `user_id`, `owner_id`, `target_job_match_id`, and a pasted description in that request are ignored.

## Ownership

Every read/write/delete is scoped to `current_user.id`. Another user’s application id, resume version id, or match id returns **404**. CSRF is required on mutations. GET is read-only.

`/api/jobs/analyze` is **not** used on these pages. `export-apply` PDF is **not** shown.

## Limitations

- Not ATS scoring or ranking
- Not hiring, interview, employment, or job-loss probability
- No contacts, Kanban, LinkedIn, scraping, or automatic applications
- No PDF export, no archive, no account-level retention UI
- Conservative Target Job Match vocabulary is unchanged
