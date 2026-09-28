

---

## 16. Technical appendix: exact repository inventory

### 16.1 Exact route inventory observed in `app.py`

Authentication and OAuth routes:

```text
GET      /oauth/google
GET      /oauth/github
GET      /oauth/linkedin
GET      /login/google/callback
GET      /login/github/callback
GET      /login/linkedin/callback
GET/POST /login
GET/POST /signup
GET/POST /verify-otp
POST     /resend-otp
GET/POST /forgot-password/otp
GET/POST /reset-password/otp
GET/POST /forgot-password
GET/POST /reset-password/<token>
GET/POST /logout
POST     /admin/logout
```

Page and workspace routes:

```text
GET      /
GET      /workspace
GET      /workspace/skills-gap
GET      /methodology
GET      /privacy
GET      /insights
GET/POST /partnerships
GET/POST /admin
```

Administration and system routes:

```text
GET      /api/admin/users
GET      /api/auth-assistant/context
GET      /api/rag-status
GET      /healthz
GET      /api/csrf-token
POST     /api/check-password
POST     /api/feedback
```

Analysis and career routes:

```text
GET      /api/analyze-stream
POST     /api/upload
POST     /api/analyze
GET      /api/skills-gap/roles
POST     /api/skills-gap/analyze
POST     /api/career-paths
POST     /api/learning-roadmap
POST     /api/career-chat
POST     /api/career-chat/stream
POST     /api/insights-summary
POST     /api/compare
```

These routes demonstrate that the application already has broad analysis coverage. They do not yet represent a complete persisted Career Plan or job-application workflow.

### 16.2 Exact database models observed in `storage.py`

`User` currently includes identity, username, email, name, phone, profile image, password hash, role, active status, email verification, created/updated timestamps, and last-login data.

`Upload` currently records user association, filename, file type, analysis mode, risk score, risk label, reasoning JSON, and creation time.

`Feedback` currently records user association, upload association, rating, message, and creation time.

`VerificationOTP` currently supports email verification and password reset purposes, expiry, usage, attempt count, and creation timestamp.

`PasswordResetToken` currently supports user association, token, expiry, usage, and creation timestamp.

The following models are still required for the full roadmap:

```text
CareerGoal
GoalConstraint
ResumeProfile
ResumeVersion
EvidenceItem
SkillMention
CanonicalSkill
SkillAlias
UserCorrection
JobPosting
Company
Application
ApplicationEvent
Contact
InteractionNote
Task
FollowUp
AnalysisSnapshot
Occupation
OccupationAlias
OccupationTask
OccupationSkill
OccupationTechnology
OccupationInterest
OccupationEducation
OccupationRelation
LearningPlan
LearningPlanItem
SkillCoverage
Prerequisite
ProgressEvent
ProjectEvidence
Credential
CoachingThread
CoachingMessage
CoachingFeedback
ConsentRecord
RetentionPolicy
AuditEvent
ModelArtifact
DatasetManifest
```

The final names may be adjusted during implementation. The important requirements are user ownership, versioning, provenance, migration support, deletion behavior, and historical reproducibility.

### 16.3 Exact dataset inventory observed

The repository contains these CSV files:

| File | Observed approximate rows | Main purpose |
|---|---:|---|
| `data/automation_risk.csv` | 3,000 | Local automation-exposure target and occupation attributes |
| `data/coursera_catalog.csv` | 8,092 | Local course catalog and metadata |
| `data/onet_interest_keywords.csv` | 75 | Interest keyword mapping |
| `data/onet_interests.csv` | 8,307 | O*NET-style interest records |
| `data/onet_skils.csv` | 44,700 | O*NET-style skill records; filename is misspelled and should be handled compatibly |
| `data/resume_corpus.csv` | 9,544 | Resume corpus and role-related fields |

The `automation_risk.csv` dataset contains fields including:

- Job role
- Industry
- Average salary
- Experience required
- Education level
- Task repetition
- Creativity requirement
- Physical labor
- Analytical complexity
- Social interaction
- AI tool availability
- AI maturity
- Percentage of tasks automatable
- Job growth
- Skill complexity
- Regulation strictness
- Ethical risk
- Communication requirement
- Domain-specific knowledge
- Team collaboration
- Current AI dependency
- Future AI dependency
- Training hours
- Job demand index
- Automation risk score

Important data concerns:

- There are 3,000 rows but only 20 unique roles according to the supplied evaluation artifact.
- The target appears to have broad numeric variation but weak predictive relationship to the current text representation.
- The target-generation process needs to be documented before it is treated as real-world evidence.
- O*NET files must be imported and normalized with stable identifiers and source releases rather than treated as an anonymous text corpus.
- The Coursera catalog should have a documented provenance and refresh policy.
- Course URLs should be checked for staleness.
- The misspelled `onet_skils.csv` filename should not be renamed without a compatibility migration or loader fallback.

### 16.4 Current project files observed

Root files include:

```text
.dockerignore
.env.example
.gitignore
Dockerfile
README.md
app.py
bootstrap.py
conversational_flow.md
evaluation.py
rag_retriever.py
requirements.txt
resume_parser.py
risk_assessor.py
setup.ps1
start.sh
storage.py
test_auth_e2e.py
test_forgot_password.py
train_model.py
utils.py
docker-compose.yml
```

Current documentation files now include:

```text
README.md
conversational_flow.md
ENHANCEMENT_ROADMAP.md
IMPLEMENTATION_PLAYBOOK.md
ML_AUDIT_AND_NEXT_STEPS.md
PROJECT_MASTER_STATUS.md
```

Current template files include:

```text
404.html
500.html
admin.html
auth.html
auth_assistant.html
base.html
forgot_password.html
index.html
insights.html
methodology.html
partnerships.html
privacy.html
report.html
reset_password.html
skills_gap.html
verify_otp.html
workspace.html
```

Current static files include the main styles, analysis scripts, authentication assistant assets, career chat assets, manifest, service worker, offline page, and design reference images.

### 16.5 Current test files observed

```text
tests/test_app.py
tests/test_email_service.py
tests/test_forgot_password_otp.py
test_auth_e2e.py
test_forgot_password.py
```

The two standalone authentication scripts require a separately running server according to the user-provided validation note. They should eventually be converted into controlled pytest or Playwright fixtures so CI does not depend on a manually started local server.

### 16.6 Current CI behavior

The current GitHub Actions workflow:

- Runs on pushes to `main` and `final-year-project`.
- Runs on pull requests to `main`.
- Uses Ubuntu.
- Installs Python 3.11.
- Uses pip caching.
- Installs `requirements.txt` and pytest.
- Caches `ml_models/` based on `train_model.py` and `data/*.csv` hashes.
- Trains the ML model when the cache misses.
- Runs `python -m pytest tests/ -v --tb=short`.
- Disables SMTP credentials in CI.
- Uses a disposable SQLite database URL.

CI improvements still required:

- Include the development branch in the workflow while it is being built.
- Run compilation explicitly.
- Run lint/security/dependency checks.
- Run deterministic ML evaluation.
- Store evaluation JSON as an artifact.
- Run browser smoke tests.
- Run accessibility tests.
- Use a test database that cannot overwrite development data.
- Add migration tests.
- Verify no secrets are committed.
- Add a failure summary that identifies the phase and checkpoint.

### 16.7 Exact Git state after the planning work

The development branch currently points to:

```text
ff912f0 docs: add exhaustive project master status
```

The previous planning commit is:

```text
1557990 docs: add enhancement roadmap and implementation playbook
```

The original main branch source commit reviewed is:

```text
4786a98 fix: career chat - distinct interview vs career-path fallback answers with word-boundary topic matching
```

The planning tags currently created are:

```text
checkpoint-phase-00-planning
checkpoint-phase-00-status
```

The branch is pushed to:

```text
origin/develop/final-year-enhancement
```

No feature-code implementation was included in either planning commit. This is intentional and documented.

---

## 17. Complete “done / suggested / remaining” matrix

| Area | Already in repository | Completed in this conversation | Suggested but not yet implemented |
|---|---|---|---|
| Resume parsing | PDF, DOCX, text, layout and sections | Audited and documented | Evidence spans, corrections, canonical profile |
| Skill extraction | Category-based extraction and normalization | Audited and alias recommendations recorded | Canonical skill registry, confidence, user corrections |
| Role matching | TF-IDF role and cluster matching | Audited and limitations documented | Per-job explainable matching and O*NET-SOC IDs |
| Automation exposure | Local Ridge-based estimate | Metrics interpreted and language boundary defined | Validated target, structured evidence, calibration, abstention |
| RIASEC | Resume-derived heuristic profile | Compared with official Interest Profiler | Authorized profiler or local self-report with clear label |
| Skills gap | Hard-coded role skill gap endpoint | Evidence and alias improvements documented | Required/preferred requirements and versioned occupation data |
| Course recommendations | Local Coursera catalog and roadmap | Benchmark and learning-path direction documented | Persisted plans, prerequisites, progress, evidence |
| Career paths | Suggestions and compare endpoint | Recommended evidence-backed relation graph | O*NET related occupations and transition explanations |
| Career chat | RAG, streaming, local Ollama and fallback | Grounding and privacy requirements documented | Citation contract, goal context, role-play and feedback |
| Authentication | Login, signup, OAuth hooks, OTP, reset | Security review documented | Production secret hardening and authorization matrix |
| Storage | SQLite metadata-oriented models | Model gap documented | Career Plan and application domain models |
| Admin | Admin route, metrics and users | Data-quality dashboard recommendation added | Privacy-safe operational analytics |
| UI | Existing polished glassmorphism/PWA/dark mode UI | IA and UI/UX roadmap documented | Unified Career Plan and accessibility pass |
| Testing | Existing pytest and E2E scripts | Test gaps and gates documented | Playwright, axe, migration, security, ML, and CI expansion |
| CI | Python install, model cache, pytest | CI gap analysis documented | Full quality, browser, security, and artifact pipeline |
| Git workflow | Main branch and GitHub Actions | Development branch and planning tags created/pushed | Per-phase green checkpoints |
| Documentation | README and project docs | Three planning/audit docs plus this report created | Architecture, decision, migration, and release docs |

---

## 18. Small details that must not be forgotten

The following details are easy to lose during implementation and are therefore recorded explicitly:

- Keep the current TF-IDF lexical model as a transparent baseline even if semantic models are added.
- Do not delete the local offline fallback when adding external adapters.
- Keep provider and source metadata on courses.
- Preserve raw skill phrases in addition to normalized skill labels.
- Use word boundaries for short aliases such as `R`, `C`, and `Go`.
- Do not match `Java` and `JavaScript` as the same skill without an explicit rule.
- Record the location of evidence inside the resume.
- Record whether evidence came from a resume, job description, O*NET, course catalog, user input, or model inference.
- Add a confidence state that can be `unknown` or `insufficient evidence`.
- Do not display a percentage without nearby explanatory language.
- Show data freshness and geography for wages and labor-market information.
- Keep O*NET and external labor-market source licenses separate.
- Do not claim Lightcast taxonomy access without a license.
- Do not scrape LinkedIn Learning, Coursera, Teal, or job boards.
- Do not auto-submit applications.
- Do not infer course completion from a link click.
- Do not infer proficiency from a skill mention alone.
- Do not infer protected characteristics.
- Do not use RIASEC as a medical, psychological, or ability diagnosis.
- Keep the user in control of resume corrections.
- Keep the user in control of application status transitions.
- Make reminders opt-in.
- Make external model transfer opt-in.
- Redact raw resume text from logs.
- Redact prompts and tokens from logs.
- Test deletion propagation to derived evidence and analysis.
- Test authorization on every user-owned route.
- Test migration on both fresh and existing databases.
- Do not overwrite historical analysis snapshots after a model update.
- Store model and dataset versions on analysis outputs.
- Store source dates on occupation and course facts.
- Make every course recommendation explain which gap it addresses.
- Make every learning item have a re-check condition.
- Make every result page identify the next action.
- Keep the first page focused and move methodology/resources below the primary action.
- Remove duplicate mode controls.
- Respect reduced-motion preferences.
- Provide keyboard and screen-reader behavior.
- Provide text/table alternatives to visual graphs.
- Test mobile viewport behavior.
- Avoid card-inside-card nesting that hides hierarchy.
- Do not add a new frontend framework unless the current stack becomes an actual blocker.
- Do not add Three.js, WebGPU, GSAP, voice, or a browser extension before the core workflow is measured.
- Do not let an AI coding agent rewrite the whole repository in one request.
- Require a diff, tests, and checkpoint after every phase.
- Do not claim a test passed if it was skipped or could not run.
- Keep an explicit record of skipped tests and their reason.
- Keep checkpoint tags immutable.
- Back up the database before migrations.
- Never commit secrets or real credentials.
- Keep `README.md` synchronized with actual behavior.
- Keep the roadmap synchronized with completed and deferred features.

---

## 19. Final answer to the completeness request

This report now records:

1. What was inspected.
2. What was found in the repository.
3. What was completed in the conversation.
4. What was committed and pushed.
5. What was tested and what could not be tested.
6. What the user supplied in the audits and attachments.
7. What was recommended from benchmark comparisons.
8. What ML improvements were reported.
9. Why the ML target remains weak.
10. What the full implementation sequence is.
11. What tools and extensions are useful.
12. What tools should be deferred or avoided.
13. What the exact route and model inventory is.
14. What the exact dataset and CI inventory is.
15. What remains unimplemented.
16. What decisions still require explicit project choices.
17. What small implementation details must be preserved.

The only items intentionally not presented as completed are the feature-code changes that have not yet been implemented and verified in the connected GitHub source. This boundary is maintained to prevent planning, recommendations, and user-reported changes from being confused with shipped implementation.


---

## 20. Frontend animation, styling, and UI/UX tools

A project-specific guide was added at `FRONTEND_UI_UX_TOOLS_GUIDE.md`. The recommended stack is native CSS design tokens, CSS transitions/keyframes, the Web Animations API, Lucide or Heroicons, Playwright, axe-core, Lighthouse, optional Open Props, and GSAP only for genuinely complex timelines.

The guide covers:

- Tool comparison and free/open-source status.
- Exact fit for the current Flask/Jinja/vanilla-JavaScript architecture.
- Landing-page, workspace, skills-gap, learning-roadmap, career-chat, and form improvements.
- Design-system tokens.
- CSS animation examples.
- Reduced-motion behavior.
- Web Animations API usage.
- Open Props setup and CDN risks.
- GSAP/Anime.js selection rules.
- Icon and asset guidance.
- Figma workflow.
- Storybook decision.
- Playwright and axe-core installation and examples.
- Lighthouse usage in Chrome DevTools and CLI.
- Animation duration budgets.
- Step-by-step UI implementation sequence.
- A Copilot/Codex UI implementation prompt.

The key decision is not to migrate the current project to React, Tailwind, Bootstrap, or another frontend framework merely to improve visual quality. The existing stack can be made substantially better with a tokenized CSS system, restrained native motion, accessibility testing, and a clearer information hierarchy.


---

## 21. Compatibility review of the user-proposed frontend tools

A detailed compatibility review was added at `PROPOSED_FRONTEND_TOOLS_COMPATIBILITY.md`.

The review concludes that the best direct fits for the current Flask/Jinja/vanilla-JavaScript application are Motion, AutoAnimate, selective Lottie, Animate.css for prototypes, Alpine.js for small local UI state, HTMX for later server-rendered fragments, Lucide icons, Figma, Realtime Colors, Coolors, Playwright, axe-core, and Lighthouse.

Framer Motion, shadcn/ui, DaisyUI, Preline UI, FlyonUI, Aceternity UI, and Tailwind Typography are not direct drop-ins because they rely on React, Tailwind, Radix, or a frontend build/component system. They should be deferred unless a deliberate React/Tailwind migration is approved. A migration is not required for the current project goals.

The recommended order is:

```text
Native CSS and Web Animations API
→ Lucide icons and design tokens
→ Playwright, axe-core, and Lighthouse
→ Motion and AutoAnimate where native motion is insufficient
→ Alpine.js for small template-local state
→ HTMX later for job/application HTML fragments
→ Lottie only for a few licensed illustrations
```

The review also records important security and accessibility rules: pin remote assets, preserve CSP, do not use Alpine `x-html` with untrusted content, preserve CSRF and ownership checks with HTMX, respect reduced motion, verify community snippet licenses, and keep animation away from evidence certainty or critical data interpretation.
