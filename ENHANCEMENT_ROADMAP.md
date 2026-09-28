# Final_year_project Enhancement Roadmap

## Purpose and decision summary

This roadmap answers **what to add next without replacing what already works**. The project already has a strong resume-to-career foundation: multi-format resume extraction, structured evidence extraction, normalized skills, TF-IDF role matching, skill-gap analysis, interest exploration, a local learning roadmap, conversational support, and meaningful application/security foundations. The next product step is **not another opaque score**. It is a traceable workflow that connects a user’s resume evidence to a saved job, a targeted resume version, a transparent gap analysis, an application plan, and source-backed career intelligence.

> **Recommended product position:** an explainable, privacy-conscious career and job-search workspace. It should help a person organize evidence and decisions; it must not predict hiring, ATS acceptance, employability, or job loss.

The existing local score should be called **automation exposure** or **task exposure**—a local, educational estimate of how exposed the described role tasks may be to automation—not “job-loss prediction.” Every result should show uncertainty, calibration status, source/version, and a statement that it does not make an employment decision.

### Evidence and boundaries

This document uses only the repository capability inventory and benchmark findings supplied for this task. The project checkout was not source-code audited in the benchmark environment. Therefore, **“Already implemented” means listed in the supplied repository inventory, not independently verified line by line**. Do not claim a feature is live until the team verifies its route, schema, UI, tests, and deployment behavior.

The supplied benchmark runs for Jobscan and LinkedIn Skills Match failed; they are **not used as evidence or comparison targets** here. Teal, LinkedIn Learning, and Lightcast capability descriptions are vendor statements that establish scope, not independent proof of outcomes.

---

## 1. Current strengths to preserve

| Strength | Status | What is already present | Preserve it by… |
|---|---|---|---|
| Resume intake and evidence extraction | **Already implemented** | PDF, DOCX, and TXT extraction; PyMuPDF layout/section parsing; contact, education, experience, projects, certifications, and achievements extraction. | Keeping raw span/location references alongside extracted records, allowing correction, and retaining parser regression fixtures. |
| Skill and role foundation | **Already implemented** | Normalized skill extraction across 34+ categories, TF-IDF cosine role matching, O*NET-style clusters, and hard-coded-role skill-gap analysis. | Keeping transparent lexical matching as a baseline even if embeddings or LLMs are added. |
| Career exploration | **Already implemented** | RIASEC-style keyword/O*NET interest profile, career-path suggestions/comparison, and a local Coursera learning roadmap. | Labeling local heuristic outputs accurately; grounding them in versioned occupational data over time. |
| Resume quality support | **Already implemented** | Completeness/quality scoring. | Exposing score components and missing evidence instead of presenting a single unexplained number. |
| Conversational support | **Already implemented** | Lightweight TF-IDF RAG career chat with SSE streaming and optional local Ollama narratives. | Making all generated guidance source-linked, controllable, and reproducible rather than replacing the local stack. |
| Platform and security baseline | **Already implemented** | SQLite metadata-only uploads; authentication, OAuth, OTP, password reset, admin and feedback flows; rate limiting, CSRF, CSP, PWA/offline support, tests, and a five-fold evaluation script. | Building new user data behind per-user authorization, audit events, retention controls, and automated tests. |
| Automation-exposure estimate | **Already implemented** | A local TF-IDF/Ridge estimate explicitly described as an estimate. | Renaming/displaying it as *automation exposure/task exposure*, separating it from occupation matching, and adding calibration and uncertainty. |

### Strengths that are useful but not yet production-complete

| Capability | Status | Why it needs hardening |
|---|---|---|
| Keyword normalization | **Partial/needs hardening** | It is a good baseline, but it is not yet a market-maintained canonical skill-ID layer with aliases, confidence, source/version, correction, and measured precision/recall. |
| TF-IDF role matching | **Partial/needs hardening** | It supports transparent similarity but does not yet provide job-specific requirements, evidence spans, confidence, occupation IDs, or calibrated multi-signal ranking. |
| RIASEC-style profile | **Partial/needs hardening** | Resume-keyword inference is not equivalent to the official O*NET Interest Profiler. Keep it as a non-diagnostic approximation unless an authorized official integration is used. |
| Local role/course records | **Partial/needs hardening** | Hard-coded content is appropriate for an offline/demo fallback, but needs source provenance, versioning, coverage/freshness labels, and adapters for permitted data sources. |
| Five-fold evaluation | **Partial/needs hardening** | It is a valuable start, but text-similarity cross-validation alone does not establish skill-linking accuracy, rank quality, calibration, safety, fairness, or user usefulness. |

---

## 2. Benchmark comparison matrix

| Capability area | Current project | Teal benchmark | Lightcast Skills Taxonomy benchmark | O*NET OnLine / My Next Move benchmark | Learning / coaching benchmark | Roadmap response |
|---|---|---|---|---|---|---|
| Resume parsing and structured evidence | **Already implemented** multi-format parsing and section extraction. | Resume Builder and targeted versions. | Skill standardization entry point. | Occupation reports consume structured requirements, not resumes. | Uses learner/account context. | Preserve parsers; introduce evidence provenance and editable canonical profile. |
| Job/application workflow | **Recommended addition**; no supplied evidence of a first-class job/application domain. | Tracker, pipeline, saved jobs, job-linked resume workflow. | Not its primary purpose. | Supports exploration, not application management. | Learning-plan context. | Build JobPosting, Application, ResumeVersion, tasks, contacts, and snapshots first. |
| Per-job match explanation | **Partial/needs hardening**; current global role similarity/gaps. | Job-description match, keyword/skill recommendations. | Canonical skills and relationships. | Tasks, skills, abilities, alternate titles. | Grounded recommendations. | Add per-(resume version, job posting) analysis with matched evidence, missing requirements, score components, confidence, and version. |
| Canonical skills/taxonomy | **Partial/needs hardening**; 34+ normalized keyword categories. | Product-specific matching scope. | 34,000+ proprietary canonical skill IDs and relationship layer. | Public O*NET elements and occupation links. | Proprietary provider libraries. | Create an internal canonical registry seeded with permitted public data; design an optional licensed Lightcast adapter without copying its data. |
| Occupation intelligence | **Partial/needs hardening**; local roles, clusters, paths. | Broad job-search workflow. | Skills ↔ title/occupation/labor-market connections. | Tasks, skills, knowledge, abilities, technology, interests, Job Zones, related occupations. | Role/skill learning guidance. | Import a pinned O*NET snapshot and show source-backed, versioned occupation reports. |
| Interest and preferences | **Partial/needs hardening** RIASEC-style keyword profile. | Not central. | Not central. | Official Interest Profiler and occupational interests. | Coaching around user goals. | Separate inferred interest from self-reported assessment; use authorized official profiler integration or clearly label a local questionnaire. |
| Learning plan and evidence | **Partial/needs hardening** local Coursera roadmap. | Resume/job execution, not a learning ledger. | Skill relationships can support pathways. | Education/Job Zone information. | Course paths, practice, coaching. | Add provider-neutral plan/progress/project/credential records, external links, and evidence-led gap closure. |
| Coaching and practice | **Partial/needs hardening** RAG chat and optional local narratives. | Notes/templates, not a coaching benchmark. | Not primary. | Guided exploration. | Grounded coaching and role-play pattern. | Add cited, goal-aware coaching and text-first role play with rubric feedback; defer voice. |
| Labor-market data | **Recommended addition** beyond local content. | Job-board context, subject to terms. | Commercial supply/demand/LMI products. | U.S. occupation content plus external wage/outlook links. | Provider catalog data. | Start with permitted public O*NET/BLS-linked data and explicit dates/geography; add Lightcast only under contract. |
| Privacy/governance | **Partial/needs hardening** baseline auth/security exists. | Resume/application data are sensitive. | Commercial credentials and profile data require controls. | Assessment and occupation data need source/licence discipline. | Coaching data needs retention/admin controls. | Add consent, export/delete, retention, encryption, auditability, data minimization, and model governance. |

**Interpretation:** Teal highlights the missing job-search execution loop; Lightcast highlights the missing canonical/provenance-rich skill layer; O*NET and My Next Move highlight the missing official occupation/interest evidence; learning/coaching benchmarks highlight the missing plan–practice–evidence loop. None requires copying proprietary data, prompts, templates, scoring, integrations, or course content.

---

## 3. Prioritized backlog

### P0 — Foundation: make resume intelligence usable in a real job-search workflow

| ID | Item | Status | User value | Concrete implementation change |
|---|---|---|---|---|
| P0.1 | Job, application, and snapshot domain | **Recommended addition** | A user can retain a job description and see exactly what was analyzed or sent. | Add authenticated JobPosting, Application, ApplicationEvent, ResumeVersion, and immutable AnalysisSnapshot records; manual job capture; saved JD content hash and capture timestamp; soft delete/export/delete. |
| P0.2 | Job-linked resume version and ATS-safe export | **Recommended addition** | A user can tailor, export, and later prove which resume version was used. | Add canonical editable resume JSON, job-linked copies, diff/history, deterministic PDF export, preflight checks, and user-confirmed “mark Applied.” |
| P0.3 | Per-job explainable matching | **Recommended addition** | A user sees *why* a role fits and which evidence is missing instead of receiving a generic score. | Add a versioned analysis API using required/preferred skills, exact/semantic match types, evidence spans, weighted coverage, limitations, confidence, and a transparent lexical baseline. |
| P0.4 | Tracker workspace | **Recommended addition** | A user can turn insight into action, retain notes, and avoid missed follow-ups. | Add table/Kanban views, status transitions, dates, notes, checklist, search/filter/sort, saved views, stale indicators, and follow-up date. |
| P0.5 | O*NET canonical data and provenance base | **Recommended addition** | Career recommendations become attributable and reproducible rather than hard-coded only. | Ingest a pinned, attributed O*NET Database release into normalized tables; map roles/aliases/skills to stable IDs; display field-level source and update dates. |
| P0.6 | Consent, lifecycle, and model labels | **Recommended addition** | Users control their sensitive information and understand estimates. | Add purpose-specific consent, export/delete, retention, audit event, access-scoping, and uncertainty/provenance components before storing expanded job/chat/profile data. |

### P1 — High-value product: explain, plan, and keep the user moving

| ID | Item | Status | User value | Concrete implementation change |
|---|---|---|---|---|
| P1.1 | Canonical skill registry and hybrid linker | **Recommended addition** | Skill matches are less brittle and users can correct ambiguous mappings. | Canonical skill IDs, aliases, categories, type, source/version, raw evidence spans, confidence, rules plus semantic disambiguation, correction queue, precision/recall evaluation. |
| P1.2 | O*NET occupation report, compare, and pathways | **Recommended addition** | A user can explore task/skill/ability distinctions and see evidence-backed adjacent roles. | Search/detail/compare/provenance APIs; task, skill, knowledge, ability, technology, interest, Job Zone, education, related-role UI; explainable pathway graph. |
| P1.3 | Tasks, reminders, contacts, and company CRM | **Recommended addition** | Users can follow through on applications and networking without another tracker. | Stage-aware task templates; contacts/interaction notes; optional ICS export; editable thank-you/follow-up templates; explicit opt-in reminders. |
| P1.4 | Provider-neutral learning plan and evidence ledger | **Recommended addition** | A gap becomes an ordered, trackable plan with proof of progress. | Plan, GoalRole, PlanItem, PlanItemSkillCoverage, ProgressEvent, ProjectEvidence, Credential records; gap heatmap; external provider links and verification labels. |
| P1.5 | Grounded coaching and text role-play | **Recommended addition** | Users can practise and receive evidence-linked guidance without treating a chat answer as truth. | Goal profile; response contract with sources/version/retrieval coverage; selectable scenarios/rubrics; practice feedback linked to roadmap actions; per-answer feedback. |
| P1.6 | Source-labeled market evidence | **Recommended addition** | Recommendations can show observation period and region rather than implied real-time demand. | Source adapter and evidence cards for permitted public data; geography/time filters; observed vs inferred badges; trends, compensation, and supply/demand only where authorized. |

### P2 — Advanced differentiators: improve coverage only after the foundation is dependable

| ID | Item | Status | User value | Concrete implementation change |
|---|---|---|---|---|
| P2.1 | Taxonomy explorer and local role–skill graph | **Recommended addition** | Users can inspect transferable skills, alternatives, and why a pathway was suggested. | Versioned Role↔Skill, Role↔Occupation, Role↔Title, Skill↔Skill, Role↔Course edges with weight, source, region, time window, and text/table accessible views. |
| P2.2 | Lightcast adapter under licence | **Recommended addition** | A licensed deployment can enrich public baseline data with commercial intelligence where permitted. | Server-side contract-aware adapter, credential vault, entitlement checks, permitted cache, response timestamps, and no browser exposure or data redistribution. |
| P2.3 | Limited browser job-save extension | **Recommended addition** | Faster user-triggered job capture from supported sites. | Launch only after server model/consent UX are stable; site allowlists/adapters, review screen, universal paste fallback, tested DOM changes, and terms review. |
| P2.4 | Review-before-submit autofill exploration | **Recommended addition** | Reduces manual re-entry without removing user agency. | Local/on-demand approved-field fill only, never default auto-submit; least privilege, encryption, audit trail, allowlists, robust failure states, and legal/accessibility review. |
| P2.5 | External provider integrations | **Recommended addition** | Optional progress import or portfolio evidence links where authorized. | Consent-first OAuth/API integrations, least scopes, revocation, external-link fallback, deletion propagation, and privacy-preserving aggregates. |

### Explicit non-goals and deferred work

- **Do not build job-loss prediction.** Preserve the current *automation exposure/task exposure* estimate only as a local, uncertainty-labelled educational signal.
- **Do not make automated employment decisions**, rank candidate eligibility, claim ATS acceptance, infer protected attributes, or predict interviews/offers.
- **Do not scrape or reproduce** Teal workflows, Lightcast records/graphs, LinkedIn Learning course content/logic, job boards, assessment wording, commercial datasets, or proprietary prompts.
- **Do not auto-submit applications** or bypass CAPTCHA, platform controls, rate limits, robots/access controls, or terms of service.
- Defer voice role play, email sending, calendar OAuth, external LLM processing, broad job-board adapters, and autofill until consent, security, retention, and provider-policy controls are complete.

---

## 4. Major workstreams: data model, API, UI, and ML/analytics changes

### 4.1 Application workspace and reproducible job records — P0.1/P0.4

**Status: Recommended addition**

**Data model**

| Entity | Essential fields |
|---|---|
| `Company` | `id`, `user_id`, `name`, `website`, `industry`, `created_at`, `deleted_at` |
| `JobPosting` | `id`, `user_id`, `company_id`, `title`, `canonical_url`, `source`, `location_text`, `work_mode`, `compensation_text`, `description_raw`, `description_normalized`, `content_hash`, `captured_at`, `posted_at`, `closing_at`, `taxonomy_version`, `deleted_at` |
| `Application` | `id`, `user_id`, `job_posting_id`, `resume_version_id`, `status`, `priority`, `excitement_rating`, `date_applied`, `follow_up_at`, `archived_at`, `created_at`, `updated_at` |
| `ApplicationEvent` | `id`, `application_id`, `event_type`, `event_at`, `actor`, `payload_json`, `created_at` |
| `Contact`, `Note`, `Task`, `FollowUp` | User-scoped IDs; link to company/application; consent state for contact details; due/completion dates; soft delete. |
| `AnalysisSnapshot` | `id`, `user_id`, `job_posting_id`, `resume_version_id`, `analysis_version`, `input_hashes`, `result_json`, `model_versions`, `created_at`; immutable. |

Use explicit default statuses: **Bookmarked, Applying, Applied, Interviewing, Negotiating, Accepted, Withdrawn, Rejected/Not Selected, No Response, Archived**. Permit a user-defined stage mapping, but preserve the canonical status for analytics. Every user-owned query must be scoped by authenticated `user_id`; do not rely on client-supplied ownership.

**API**

- `POST /api/v1/jobs` for manual capture and JD paste; validate URL, size, dates, and user scope.
- `GET/PATCH/DELETE /api/v1/jobs/{id}`; `POST /api/v1/jobs/{id}/analyses` creates a snapshot for selected resume version.
- `POST /api/v1/applications`; `PATCH /api/v1/applications/{id}` for explicit status/date changes.
- `POST /api/v1/applications/{id}/events`, `/notes`, `/tasks`; `GET /api/v1/applications?status=&q=&sort=&saved_view=`.
- `POST /api/v1/export` and `DELETE /api/v1/me/data` should be authenticated, auditable, and asynchronous where needed.
- Return `request_id`, pagination, timestamps, data/source versions, and an authorization-safe error shape.

**UI**

- Start with a **manual save job** dialog: URL, title, company, location, salary text, source, and full JD paste/capture.
- Provide table and Kanban pipeline views, quick status updates, date applied, note preview, filters, saved views, a stale-item badge, and follow-up due state.
- The application detail page should bind job, selected resume version, analysis snapshot, cover-letter draft, contacts, notes, checklist, and events in one timeline.
- Never silently change an application after export. Show **“Export and mark Applied”** with a confirmation and optional follow-up date.

**Analytics/ML**

- No model is required for P0. Capture privacy-preserving operational metrics only after consent: time between saved/applied, task completion, follow-up completion, and resume-version use.
- Treat user-reported interview/offer results as noisy optional outcomes, never as labels of worth or eligibility.

### 4.2 Resume versions, preflight, and deterministic export — P0.2

**Status: Recommended addition**

**Data model:** `ResumeDocument` (canonical structured profile), `ResumeVersion` (parent, job/application link, content JSON, version number, created from, snapshot hash), `ResumeSection`, `ExportArtifact` (format, render version, hash, generated at), and `PreflightResult` (rule ID, severity, evidence, rule-set version). Preserve the original uploaded artifact separately from structured editable content where retention permits.

**API:** CRUD under `/api/v1/resume-versions`; `POST /{id}/preflight`; `POST /{id}/exports/pdf`; `GET /{id}/diff?base=`. Link export artifact ID to the application only on confirmed user action.

**UI:** Structured editor with job-linked copy, version timeline, redline/diff, ATS-safe templates, accessible field labels, export preview, and a preflight panel. Preflight checks should include missing contact details/critical sections, parseability, excessive length, unsupported formatting, and job-match gaps. It should recommend—not rewrite or fabricate—evidence.

**Analytics/ML:** Deterministic rules are primary. Optional suggestions must cite the matched job requirement and underlying resume evidence. Do not generate invented skills, experience, qualifications, or outcome promises.

### 4.3 Explainable per-job match analysis — P0.3

**Status: Recommended addition**

**Data model:** `JobRequirement` (raw phrase, normalized skill/credential/title, required/preferred/unknown, extractor/method/version, confidence), `ResumeEvidence` (resume version, canonical skill ID, raw span, section, timeframe if supplied), `MatchEvidence` (requirement/evidence links, match type, component weight), `AnalysisSnapshot` as above.

**API response contract:**

```json
{
  "analysis_version": "match-1.0",
  "resume_version_id": "...",
  "job_posting_id": "...",
  "score": {"value": 62, "scale": "0-100", "meaning": "documented profile alignment", "calibration_status": "not yet calibrated"},
  "coverage": {"required": 0.58, "preferred": 0.41},
  "matched": [{"requirement": "Python", "evidence_span": "...", "match_type": "exact", "weight": 0.12}],
  "missing_evidence": [{"requirement": "AWS", "importance": "high", "reason": "no supporting resume evidence found"}],
  "limitations": ["Job description did not clearly label required versus preferred qualifications."],
  "source_versions": {"skill_registry": "...", "occupation_data": "..."},
  "created_at": "..."
}
```

**UI:** Separate **required**, **preferred**, **matched**, and **missing evidence**; show the evidence span and section, score components, confidence/coverage, and an “I have evidence—add/correct it” flow. Use wording such as “No supporting evidence found in this resume,” not “You lack this skill.”

**ML/analytics:** Retain TF-IDF/lexical matching as the transparent baseline. Add embeddings/cross-encoder reranking only after consented labeled data exists. Evaluate extraction, linking, ranking, and calibration separately. The score measures **documented text/profile alignment**, not qualification, ATS compatibility, candidate quality, interview probability, or hiring likelihood.

### 4.4 Canonical skills and role graph — P1.1/P2.1

**Status: Recommended addition**

**Data model:**

- `CanonicalSkill`: stable internal ID, preferred label, aliases, category/subcategory, type (`specialized`, `common`, `certification`, or local type), source, taxonomy version, status.
- `SkillMention`: document/job source, raw text/span, canonical ID, match method, confidence, user correction flag.
- `Role`, `Occupation`, `TitleAlias`, and edges `RoleSkill`, `RoleOccupation`, `RoleTitle`, `SkillSkill`, `RoleCourse`.
- Every edge carries `weight`, `evidence_source`, `geography`, `observation_window`, `version`, and `created_at`.

Start relationally. Introduce a graph database only if measured traversal/query needs justify operational complexity.

**API:** `/v1/skills/normalize`, `/v1/roles/match`, `/v1/graph/pathways`, `/v1/market/skills`; session/OAuth authorization, schema validation, pagination, rate limits, request IDs, source/version fields, and contract-aware caching.

**UI:** Skill profile pages, raw mention → canonical skill explanations, correction controls, a searchable hierarchy, transferable-skill/pathway views, and text/table alternatives to any graph visualization.

**ML/analytics:** Alias/phrase candidate generation; deterministic rules for acronyms and certificates; context-aware disambiguation; thresholds with “uncertain” state; human review queue. Measure precision/recall and calibration independently for skills, credentials, and ambiguous phrases. Corrections are feedback for offline tuning, not automatic truth.

### 4.5 O*NET occupation intelligence — P0.5/P1.2/P1.6

**Status: Recommended addition**

#### O*NET enhancement plan by information domain

| Domain | Data and source-date plan | Product behavior | Important boundary |
|---|---|---|---|
| Tasks | Ingest task statements and any available relevance/importance/frequency ratings from a **pinned O*NET release**. Store O*NET-SOC code, release/version, collection/update metadata, import date, checksum, and field source. | Rank task requirements; compare resume evidence to task-related skills; show task evidence separately from skill evidence. | A task rating describes an occupation, not whether the individual can perform it. |
| Skills, knowledge, and abilities | Store distinct O*NET elements and ratings; map local canonical skills to O*NET element IDs with method/confidence. | Explain matched and missing resume evidence; keep **abilities** distinct from skills and avoid claims that a user possesses an ability. | Resume mentions are imperfect, ambiguous, and may be stale. |
| Technology/software | Import permitted technology/tool categories and their source metadata. | Show technology categories, definitions, and any permitted hot/in-demand labels with an “as of” date. | Do not treat tool mentions as proficiency or real-time hiring demand. |
| Interests | Store occupational RIASEC/specific-interest data from the pinned release. For a person, use an authorized official Interest Profiler integration or retain current keyword-RIASEC as clearly labelled local inference. | Show occupational interest patterns and, separately, user self-report or inferred profile with an explanation. | Do not reproduce official question wording/scoring without authorization; do not call a keyword profile diagnostic. |
| Education, training, and Job Zone | Store Job Zone and reported preparation/education data with exact release/source dates. | Present preparation ranges, reported education, and training requirements in occupation reports. | U.S.-specific; not an admissions or eligibility decision. |
| Wages, employment, and outlook | Obtain only approved O*NET/BLS-linked or other permitted public sources. Persist provider, SOC/O*NET crosswalk, geography, observation period, release/as-of date, unit, and methodology. | Provide national/state/local views when data are comparable; show unavailable/non-comparable rather than estimating. | Keep wage/outlook entirely separate from match score; label U.S. geography and source vintage. |
| Related careers/pathways | Store O*NET related-occupation links plus shared task/skill, Job Zone and education deltas. | Show multiple user-selectable routes, why each edge is suggested, missing evidence, and alternatives. | “Related” does not mean guaranteed promotion, hiring, or salary progression. |

**API:** `GET /api/occupations/search`, `GET /api/occupations/{onet_soc}`, `GET /api/occupations/{code}/comparison`, and `GET /api/occupations/{code}/provenance`. Return structured elements, ratings, field-level source labels, versions, and dates—not generated prose alone. A future O*NET Web Services adapter must remain server-side, cache versioned responses, handle `429`/`5xx`, and fall back to the pinned local snapshot.

**UI:** Occupation report tabs: **Summary, Tasks, Requirements, Experience & Education, Technology, Interests, Market, Related Careers, Provenance**. Each panel displays source and exact/as-of date. For example, only after confirmed data ingestion, a badge may say “O*NET occupational evidence — [release/field date]” or “BLS wage data — [as-of date]”; do not hard-code a generic “current” label.

**ML/analytics:** Use deterministic title/alternate-title retrieval plus skill-to-element mapping and weighted evidence. Semantic reranking is optional. Return alternatives and distinct `confidence` and `coverage` values. Keep task exposure/automation exposure as a **separate local estimate**, never as an O*NET metric.

**Release operations:** Build repeatable ETL, crosswalk/migration, release-diff report, checksum manifest, regression tests, snapshot retention, and rollback. Verify the applicable O*NET database/license terms and attribution for each distributed release; identify modified data as modified and do not imply U.S. Department of Labor approval.

### 4.6 Plans, learning evidence, coaching, and role play — P1.4/P1.5

**Status: Recommended addition**

**Data model:** `GoalProfile` (role, location, seniority, budget/time, stated constraints, consent), `Plan`, `GoalRole`, `PlanItem`, `PlanItemSkillCoverage`, `ProgressEvent`, `ProjectEvidence`, `Credential`, `CoachingThread`, `CoachingMessage`, `ResponseFeedback`, and a data-provenance registry. Store external provider IDs/URLs, level, duration, prerequisites, source/license, and last verification—not copied course/video/assessment content.

**API:** Plan CRUD; progress/evidence updates; `POST /api/v1/coaching/respond` returning generated narrative plus citations, evidence spans, retrieval coverage, model/prompt/retrieval versions, and limitations; `POST /api/v1/practice/sessions` for scenario/rubric turns; feedback endpoint with reason codes. Support profile edit/reset and thread reset.

**UI:** Gap heatmap, ordered course/project cards, provider/duration/constraint labels, skill coverage rationale, remaining-gap timeline, portfolio/credential drawer, weekly goal/check-in, and external deep links. Text-first role play should provide selectable or user-authored scenarios, a rubric, end-session strengths/gaps, example revisions, and “add next action to plan.”

**ML/analytics:** Use a prerequisite filter, weighted gap coverage, stated preferences, and diversity control (for example, MMR) before narrative generation. Evaluate NDCG@K, coverage, redundancy, calibration, groundedness, citation coverage, helpfulness, and safety. Voice is a later opt-in feature requiring separate transcription, retention, accessibility, and abuse-safety design.

### 4.7 Lightcast integration/reference plan — P2.2

**Status: Recommended addition, conditional on a commercial contract**

Lightcast is a useful **architecture reference** for canonical skills, relationships, occupation mapping, and labor-market evidence. It is not a free data source to copy. Its taxonomy, broader labor-market products, compensation, postings, profiles, benchmarks, and API access are commercial/contract-governed; the occupation taxonomy is proprietary. Browseable pages and API documentation do not grant bulk-copying, scraping, redistribution, model-training, or unlimited caching rights.

| Deployment state | Allowed approach | Prohibited approach |
|---|---|---|
| No Lightcast licence | Use a clearly labelled local registry and permitted public alternatives such as O*NET and applicable government statistics; maintain a local/offline fallback. | Do not scrape, mirror, cache, train on, or represent Lightcast taxonomy/postings/profiles/relationships as local data. |
| Licensed Lightcast deployment | Confirm entitled products/endpoints, permitted fields, regions, retention/cache rules, display/attribution, rate limits, user restrictions, and termination/deletion obligations in the executed contract. Call API server-side with OAuth 2.0 bearer credentials; pin retrieved version/effective date. | Do not expose credentials in browser code, Ollama prompts, logs, analytics, client responses, or source control; do not use non-entitled endpoints or redistribute raw data. |
| Product display | Return source name, source/version/effective date, observation window/geography, and whether a value is observed, taxonomy-mapped, or locally inferred. | Do not present a resume mention as verified proficiency, demand as hiring likelihood, or a taxonomy match as an employment decision. |

**Adapter design:** create a `LaborMarketProvider` interface with `searchSkills`, `classifySkills`, `searchOccupations`, `getMarketEvidence`, and `health`. Implement `OnetProvider`/public-data baseline first. A `LightcastProvider` must live only server-side, read secrets from a vault, attach entitlement-aware cache policy, redact identifiers, record request/response schema/version metadata, and have contract tests. Cache only fields and durations expressly permitted by the contract. Never route full resumes or raw job descriptions to a commercial provider without documented consent, contractual approval, minimization, and a privacy review.

### 4.8 Browser capture and autofill — P2.3/P2.4

**Status: Recommended addition, intentionally late**

**Data/API:** `CaptureSource`, `SupportedSite`, `ConsentReceipt`, and `AutofillAuditEvent`; server endpoint receives user-approved normalized fields only. Keep browser extension permissions least-privilege and site allowlisted.

**UI:** User-triggered “Save this job” review before persistence; universal URL/paste fallback; supported-site disclosure; visible error/failure state; opt-in approved-field review for autofill. The extension must never auto-submit by default.

**Security/ML:** No autonomous application agent. No CAPTCHA bypass. No scraping that violates site terms. Do not send page content to an LLM without disclosure and consent. Test changing DOMs, accessibility, permissions revocation, cross-site isolation, and data deletion.

---

## 5. Model quality, uncertainty, privacy, fairness, security, and evaluation

### 5.1 Quality and uncertainty standards

1. **Separate the outputs.** Resume quality, job-document alignment, occupation match, interest fit, task exposure, learning recommendation, and observed market data must be separate response types and UI panels.
2. **Version everything.** Persist parser version, skill-registry version, occupation release, job-description hash, model/prompt/retrieval version, timestamp, and source date. Old analysis snapshots remain reproducible.
3. **Display limitations.** Each score shows its meaning, evidence coverage, uncertainty/insufficient-evidence state, and what it does not measure.
4. **Calibrate before strong language.** For any probabilistic output, use held-out calibration analysis (for example, reliability plots, Brier score, expected calibration error) and refrain from probability wording until calibrated.
5. **Keep a deterministic fallback.** If semantic/LLM services fail, return transparent lexical/rule-based results with a limitation banner; do not silently substitute fabricated guidance.
6. **Prompt-injection defenses.** Treat job descriptions, uploaded files, external pages, and retrieved content as untrusted data. Delimit content, disallow instructions from retrieved text, constrain tool access, validate structured output, and never reveal secrets or user data across accounts.

### 5.2 Privacy and data lifecycle controls

| Control | Required implementation |
|---|---|
| Purpose-specific consent | Separate consent for resume parsing, job/application storage, coaching/history, provider integrations, optional analytics, and any third-party model transfer. Explain purpose, recipient, retention, and withdrawal. |
| Data minimization | Store only needed data; keep raw resume/JD content separate from derived metadata; redact PII in logs, traces, and evaluation datasets. |
| User rights | Authenticated view/correct/export/delete for resumes, extracted profile, jobs, applications, contacts, plans, chat, feedback, and integration tokens. Define deletion propagation and backup-erasure schedule. |
| Retention | Configurable retention policy by files, extracts, chats, feedback, tokens, and audit records; default to the shortest practical retention. |
| Security at rest/in transit | TLS in transit; encryption at rest for sensitive fields and backups; secret vault; key rotation; password hashing; no keys in client bundles or repositories. |
| Isolation | Per-user authorization at database query layer; tenant/RBAC rules if institutional deployment is added; admin actions separately logged and least-privilege. |
| Auditability | Immutable security/audit events for export, deletion, consent change, data sharing, sensitive view, admin action, autofill, and application status transition. |

### 5.3 Fairness and safety

- Do not infer or use protected traits. Do not derive them from names, addresses, photos, interests, chat text, or proxies.
- Test parser/linker/ranker error rates across representative document formats, languages where supported, career stages, and lawful/consented groups. Report coverage gaps rather than masking them.
- Use a correction and appeal path: users can correct skills, roles, evidence, preferences, and unsafe advice; support staff can review reports under documented access controls.
- Avoid deterministic language about suitability, ability, salary, career progression, or automation. Offer alternatives and uncertainty, especially where source coverage is thin.
- Put human review in the loop for high-impact or ambiguous recommendations. The app is career-support software, not an automated employment decision system.

### 5.4 Evaluation plan

| Layer | Dataset and method | Acceptance signal |
|---|---|---|
| Parsing | Versioned, consented/synthetic fixture set across PDF/DOCX/TXT layouts. | No regression in section/evidence extraction; failed fields are surfaced. |
| Skill extraction/linking | Hand-labelled mentions, aliases, certifications, and ambiguous abbreviations; temporal holdout. | Precision/recall/F1 by category and calibrated confidence; manual review of error clusters. |
| Role and job matching | Hand-labelled resume–occupation and resume–job pairs; rank evaluation and temporal/geographic splits where market data is used. | NDCG@K/MRR, coverage, component explanations, and reliable uncertainty—not merely TF-IDF cross-validation. |
| Recommendations | Curated relevance/coverage judgments and user study; compare against transparent baseline. | Better gap coverage and lower redundancy without reduced safety/citation quality. |
| Coaching | Offline groundedness/citation/safety set; red-team prompt-injection cases; user feedback. | Source coverage, bounded claims, safe refusal/escalation, helpfulness, and no unsupported citations. |
| Fairness | Lawful, consented subgroup/error analysis plus document-format/accessibility slices. | No uninvestigated material error disparity; published limitations and remediation plan. |
| Workflow | Opt-in product metrics and qualitative usability tests. | Faster job capture, complete snapshots, follow-up completion, successful export/delete, and accessible task flow—not hiring or offer claims. |

---

## 6. Practical phased implementation order and acceptance criteria

### Phase 0 — Design, governance, and baseline (1–2 weeks)

**Build:** data inventory; ownership/retention map; roles/authorization matrix; model/output glossary; source/licensing registry; API conventions; test fixtures; UX wireframes. Confirm current feature inventory in the actual checkout.

**Acceptance criteria**

- [ ] A verified implementation inventory distinguishes shipped features from planned features.
- [ ] Every new entity has user ownership, soft-delete/export/delete behavior, and retention class.
- [ ] Privacy notice/consent copy and source/license registry are reviewed before new sensitive data is collected.
- [ ] The UI vocabulary says **automation exposure/task exposure**, not job-loss prediction, and includes a limitation statement.
- [ ] Existing parsing, matching, security, PWA, and evaluation tests remain green.

### Phase 1 — Core application loop (3–5 weeks)

**Build:** P0.1–P0.4: manual job capture, JobPosting/Application schema/migrations, immutable snapshots, tracker, resume versions, deterministic export/preflight, per-job baseline analysis.

**Acceptance criteria**

- [ ] An authenticated user can save a job manually, including full JD, source URL, `content_hash`, and capture time.
- [ ] A user can create a job-linked resume version, run preflight, export an artifact, and explicitly record the exact version as Applied.
- [ ] Analysis results identify matched evidence and missing evidence, required/preferred ambiguity, score components, version, and limitations.
- [ ] User A cannot retrieve, modify, or export User B’s jobs/resumes/applications in API or UI tests.
- [ ] Table and Kanban views support canonical status, date applied, note, follow-up date, filter/search/sort, and stale indicator.
- [ ] Deleting/exporting an application follows documented lifecycle behavior and produces an audit event.

### Phase 2 — Trusted occupational foundation (3–5 weeks)

**Build:** P0.5/P0.6 plus P1.1/P1.2: pinned O*NET ingestion, canonical skills, correction workflow, occupation search/report/compare, provenance drawer, role-path explanation.

**Acceptance criteria**

- [ ] Every displayed O*NET-backed field has O*NET-SOC identifier, source/release, applicable source/update date, import checksum, and attribution path.
- [ ] Tasks, skills, knowledge, abilities, interests, technology, education/Job Zone, and related occupations are modelled separately where data permits.
- [ ] User sees raw mention → canonical skill mapping, confidence/method, and can correct it.
- [ ] A release-diff, regression test, migration/crosswalk, rollback, and local-snapshot fallback have been exercised.
- [ ] Any wage/outlook card shows provider, geography, observation period/as-of date, units, and non-comparability/unavailable state; it is not blended into a match score.

### Phase 3 — Plan, follow-through, and grounded help (3–4 weeks)

**Build:** P1.3–P1.5: tasks/reminders/contacts, ICS export, provider-neutral learning plan/evidence ledger, goal profile, cited coaching, text role play, response feedback.

**Acceptance criteria**

- [ ] Task/reminder delivery is opt-in; ICS export works without requiring external calendar OAuth.
- [ ] A plan item has provider/source/version, skill coverage, status, user-entered progress, and evidence URL; clicking a course never marks it complete.
- [ ] Coaching response displays source URL/title, bounded evidence, retrieval/model/version data, limitations, and a correction/report action.
- [ ] Role play gives rubric-specific feedback and can create a user-approved roadmap action.
- [ ] Chat/profile/export/delete retention behavior is demonstrable end-to-end.

### Phase 4 — Market evidence and validated quality (2–4 weeks)

**Build:** P1.6, quality/fairness dashboards, holdout evaluation, calibration, source-labeled public market evidence.

**Acceptance criteria**

- [ ] Observed data, taxonomy mappings, and local model inferences have distinct visual labels.
- [ ] Tests report parsing/linking/ranking/calibration/safety metrics on versioned datasets; results include limitations and regression gates.
- [ ] Automation/task-exposure display shows model/data version, uncertainty/coverage, calibration status, and explicit non-prediction disclaimer.
- [ ] Red-team and authorization tests cover cross-account access, prompt injection, secrets, rate limiting, export/delete, and log redaction.

### Phase 5 — Optional integrations and differentiators (only after review)

**Build:** licensed Lightcast adapter if contractually approved; limited job-save extension; authorized provider/OAuth integrations; later review-before-submit autofill.

**Acceptance criteria**

- [ ] Legal/licensing and privacy review approves each data source, endpoint, cache duration, display/attribution, and retention rule.
- [ ] Commercial API credentials remain server-side and entitlement/caching tests pass.
- [ ] Extension works only on tested, allowlisted sites, provides paste fallback, and never auto-submits or bypasses platform controls.
- [ ] OAuth has least scopes, revocation, expiration handling, audit events, and deletion propagation.

---

## 7. Delivery guardrails for the final-year team

1. **Ship manual flows before automation.** Manual job saving and reviewable resume export provide durable value without brittle scraping or extension maintenance.
2. **Use public, versioned data before commercial enrichment.** A well-attributed O*NET-backed local snapshot is more defensible than an unlicensed imitation of Lightcast.
3. **Treat every model score as an explanation problem.** A result without evidence, source/version, limitation, and user correction path should not ship.
4. **Prefer user evidence over inferred claims.** Suggestions can identify a missing evidence gap; they must not invent experience or call a user unqualified.
5. **Make privacy a product feature.** Export, deletion, retention controls, local-model disclosure, and source provenance are differentiators for a career product handling sensitive data.
6. **Measure workflow quality, not employment outcomes.** Focus on capture completeness, explanation quality, task completion, user correction, usability, and privacy/security success. Interviews/offers are optional, noisy self-reports—not a training target or product promise.

---

## 8. References

### Teal workflow benchmark

1. [Teal Job Tracker](https://www.tealhq.com/tools/job-tracker)
2. [Teal Help: Track job applications](https://help.tealhq.com/en/articles/14435727-how-to-track-your-job-applications)
3. [Teal Resume Builder](https://www.tealhq.com/tools/resume-builder)
4. [Teal Resume Job Description Match](https://www.tealhq.com/tool/resume-job-description-match)
5. [Teal Help: Export resume and cover letter](https://help.tealhq.com/en/articles/9519151-export-your-resume-cover-letter)
6. [Teal Autofill Job Applications](https://www.tealhq.com/tools/autofill-job-applications)
7. [Teal Help: Job Tracker tools](https://help.tealhq.com/en/articles/9525013-leveraging-your-job-tracker-tools)
8. [Teal Job Search Chrome Extension](https://www.tealhq.com/tool/job-search-chrome-extension)
9. [Teal Pricing](https://www.tealhq.com/pricing)

### Lightcast reference and licensing boundary

10. [Lightcast Skills Taxonomy](https://lightcast.io/taxonomies/skills-taxonomy)
11. [Lightcast Open Skills FAQ](https://lightcast.io/our-data/taxonomies/open-skills/faqs)
12. [Lightcast Skills API overview](https://docs.lightcast.io/lightcast-api/reference/overview-skills)
13. [Lightcast Occupation Taxonomy](https://lightcast.io/taxonomies/occupation-taxonomy)
14. [Lightcast data overview](https://lightcast.io/our-data)
15. [Lightcast API menu](https://lightcast.io/our-data/api/menu)
16. [Lightcast taxonomies](https://lightcast.io/taxonomies)

### O*NET, My Next Move, and public occupational data

17. [U.S. Department of Labor: O*NET](https://www.dol.gov/agencies/eta/onet)
18. [O*NET OnLine help](https://www.onetonline.org/help/onet/)
19. [O*NET OnLine data and update information](https://www.onetonline.org/help/online/data)
20. [O*NET OnLine data sources](https://www.onetonline.org/help/online/datasources)
21. [O*NET Software Developers summary example](https://www.onetonline.org/link/summary/15-1252.00)
22. [O*NET Software Developers details example](https://www.onetonline.org/link/details/15-1252.00)
23. [O*NET Database releases](https://www.onetcenter.org/database.html)
24. [O*NET data collection](https://www.onetcenter.org/dataCollection.html)
25. [O*NET Web Services reference](https://services.onetcenter.org/reference/)
26. [O*NET database licence and attribution](https://www.onetcenter.org/license.html)
27. [O*NET release updates](https://www.onetcenter.org/whatsnew.html)
28. [My Next Move / O*NET help](https://www.onetonline.org/help/onet/mynextmove)
29. [O*NET Interest Profiler](https://onetinterestprofiler.org/)
30. [Interest Profiler information](https://www.onetcenter.org/IP.html)
31. [Interest Profiler service](https://services.onetcenter.org/ip)
32. [My Next Move occupation profile example](https://www.mynextmove.org/profile/summary/15-1252.00)
33. [O*NET Resource Center content](https://www.onetcenter.org/content.html)
34. [O*NET Work Importance Locator notice](https://www.onetcenter.org/WIL.html)

### Learning and coaching references

35. [Coursera Career Academy](https://www.coursera.org/campus/career-academy)
36. [Coursera Career Academy overview](https://www.coursera.org/career-academy)
37. [Coursera: Introducing Career Academy](https://blog.coursera.org/introducing-career-academy/)
38. [Coursera support: path completion](https://www.coursera.support/s/article/learner-000002219)
39. [LinkedIn Learning](https://www.linkedin.com/learning/)
40. [LinkedIn Learning Paths](https://www.linkedin.com/learning/paths)
41. [LinkedIn Learning Professional Certificates](https://www.linkedin.com/learning/topics/professional-certificates)
42. [LinkedIn Learning help: certificates](https://www.linkedin.com/help/learning/answer/a700836)
43. [LinkedIn Learning help: Skill Evaluations](https://www.linkedin.com/help/learning/answer/a709010)
44. [LinkedIn Learning help: role guides](https://www.linkedin.com/help/learning/answer/a724525)
45. [LinkedIn Learning AI-powered Coaching](https://www.linkedin.com/products/linkedin-learning-aipowered-coaching/)
46. [LinkedIn Learning AI-powered Coaching resources](https://business.linkedin.com/learn/resources/learner-engagement/linkedin-learning-ai-powered-coaching)
47. [LinkedIn Learning help: AI-powered Coaching](https://www.linkedin.com/help/learning/answer/a1621583)
48. [LinkedIn Learning help: role play](https://www.linkedin.com/help/learning/answer/a7118820)
49. [LinkedIn AI transparency: Learning](https://business.linkedin.com/hire/ai-transparency/learn)
50. [LinkedIn Privacy Policy](https://www.linkedin.com/legal/privacy-policy)

---

## 8A. Inside-out product audit alignment

The repository audit reinforces the same strategic conclusion from a product, UX, architecture, security, and ML perspective: Prayash should not accumulate isolated AI features. Its core experience should be one coherent loop:

> **Intent → target role → evidence → skill gap → ordered learning path → application action → progress re-check**

### Product and information-architecture implications

1. **Intent and constraints first:** ask for target role, location, seniority, time available, learning budget, preferred learning format, and application goal before generating a roadmap.
2. **One visible next action:** every analysis should end with one primary action, such as “save this target role,” “add missing evidence,” “start the first prerequisite,” or “set a follow-up date.”
3. **Traceability everywhere:** connect each recommendation through the chain `role requirement → resume evidence → gap → course/project → application action`.
4. **Learning as a path, not a list:** display prerequisites, ordering, estimated effort, skill coverage, project evidence, and progress.
5. **Application context:** connect learning items to saved jobs, resume versions, application stages, contacts, notes, and follow-ups.
6. **Trust labels:** show source, version, freshness, confidence, and fact-versus-inference labels beside recommendations.

A practical target navigation structure is:

- **Dashboard:** current goal, progress, one next action, upcoming follow-up.
- **Career goal:** target role, constraints, interest results, alternative roles.
- **Evidence profile:** resume versions, extracted skills, evidence spans, corrections, projects, credentials.
- **Skill gaps:** required/preferred skills, matched evidence, missing evidence, confidence.
- **Learning path:** ordered courses, projects, prerequisites, progress, evidence.
- **Applications:** saved jobs, tailored resumes, match analyses, stages, contacts, tasks.
- **Career coach:** grounded questions, interview practice, and action-linked feedback.
- **Settings and privacy:** consent, retention, export, deletion, integrations, model disclosures.

### MVP boundary

The MVP should deliver one complete vertical slice rather than many disconnected screens:

1. Capture intent and a target role.
2. Upload or paste a resume.
3. Extract evidence and allow corrections.
4. Select or save a job description.
5. Show explainable required/preferred skill gaps.
6. Generate an ordered learning path with one first action.
7. Create or select a targeted resume version.
8. Track the application and schedule a follow-up.
9. Re-run the analysis after progress or resume changes.

Defer broad browser automation, voice coaching, large-scale integrations, and opaque model expansion until this loop is usable and measurable.

### Production hardening before expansion

Resolve these risks before retaining more job, coaching, or learning data:

- Remove or rotate default admin/student credentials and require production secrets.
- Disable Flask debug mode and insecure OAuth transport in production.
- Move rate limits, sessions, background jobs, and other in-memory state to production-safe shared services where multiple workers are used.
- Document external LLM data flow, provide a local-model option, redact prompts/logs, and add consent before sending resume data to a third party.
- Replace unsafe `innerHTML` rendering with escaped or sanitized rendering and add content-security tests.
- Add per-user authorization tests for every new record and API route.
- Add export, deletion, retention, audit, and backup-restore tests.

### Success metrics

Measure whether the loop works, not merely whether users open AI features:

- Percentage of users who define a target role and constraints.
- Percentage who reach a first recommended action.
- Time from resume upload to first completed action.
- Skill-gap explanation helpfulness.
- Learning-path start and completion rates.
- Percentage of learning items linked to evidence or projects.
- Application tracker activation and follow-up completion.
- Re-analysis rate after learning or resume updates.
- Citation/provenance coverage of recommendations.
- User correction rate for skills and occupations.
- Extraction precision/recall and ranking quality.
- Privacy-control completion and deletion-request success.

## Final recommendation

The highest-return roadmap is: **(1) a traceable application workspace, (2) job-linked resume versions and explainable matching, (3) a versioned O*NET-backed occupation/skills foundation, and (4) consented plan/coaching features that turn gaps into user-owned evidence.** This preserves the project’s strongest assets—local extraction, transparent TF-IDF baseline, career exploration, optional local narratives, and security foundations—while adding the workflow, provenance, and evaluation discipline that a final-year project can defend technically and ethically.
