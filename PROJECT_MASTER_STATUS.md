

---

## 15. Conversation-coverage index

This section explicitly maps the substantive material from the conversation into the project record.

### Initial comparison request

| Original area | Covered in this report |
|---|---|
| Resume PDF/DOCX parsing and pasted text | Sections 2, 4.1, 6 |
| Jobscan-style resume/job comparison | Sections 4.3, 6 Phase 04; use original explainable matching rather than copying proprietary scoring |
| Teal-style job tracking and application workflow | Sections 3.2, 5, 6 Phase 04 |
| Skill extraction and normalization | Sections 4.2, 4.3, 6 Phase 06 |
| LinkedIn Skills Match benchmark | Sections 3.2, 6 Phase 06; proprietary behavior must not be copied |
| Lightcast Skills Taxonomy | Sections 3.2, 6 Phase 06, 10; optional licensed adapter only |
| O*NET OnLine occupation benchmark | Sections 3.2, 4.4, 5, 6 Phase 05 |
| Tasks, skills, technology/software, interests, education, wages, related careers, source dates | Section 6 Phase 05 |
| RIASEC-style interest profile | Sections 4.4 and 6 Phase 05 |
| My Next Move / Interest Profiler | Sections 3.2, 4.4, 6 Phase 05 |
| Automation exposure estimate | Sections 4.5, 6 Phase 02 |
| Warning against job-loss prediction | Sections 1, 4.5, 6 Phase 02, 11 |
| Coursera/local learning catalog | Sections 4.7, 6 Phase 06 |
| Coursera Career Academy benchmark | Sections 3.2, 4.7, 5.3 |
| LinkedIn Learning benchmark | Sections 3.2, 4.7, 6 Phase 07 |
| AI career-coach benchmark | Sections 4.8, 6 Phase 07 |
| Accounts, admin, authentication, feedback | Sections 4.9, 6 Phase 01 |
| SQLite metadata-first storage | Sections 4.9, 6 Phase 03/04, 13 |
| Privacy-first career platform | Sections 1, 4.9, 6 Phase 01, 13 |

### Inside-out audit findings

The supplied inside-out audit is represented by:

- The product focus on one coherent loop.
- Intent and constraints before recommendations.
- Traceability from role requirement to resume evidence, gap, learning item, and application action.
- One clear “Do this next” action.
- Career Plan as the primary user object.
- Target-role-first information architecture.
- Consolidation of role matching, skills, gaps, learning, applications, and coaching.
- Deferral of isolated social-login, marketing, decorative, and generic chat work.
- Progressive disclosure and evidence drawers.
- Trust labels for estimate, source, date, confidence, and inference.
- Visual prerequisite-aware learning paths.
- Application and learning progress re-checks.
- Security concerns involving default credentials, debug mode, external LLM data, in-memory state, unsafe `innerHTML`, and incomplete data lifecycle controls.
- Product success measures based on completed user actions rather than AI feature usage alone.

### ML improvement report

The supplied ML improvement report is represented by:

- RidgeCV recommendation.
- Larger TF-IDF capacity.
- Bigrams, `min_df=2`, and sublinear TF.
- Removal of noisy raw floating-point values from job text.
- Interpretable numeric occupation buckets.
- Model versioning.
- Dataset hashes.
- Training metadata.
- Row counts.
- Selected alpha.
- Hybrid risk components.
- Contextual estimate wording.
- Canonical aliases.
- Word-boundary matching.
- Resume evidence for matched skills.
- Target-role skill prioritization.
- Course provider, level, duration, and match-type metadata.
- Explainability UI fields.
- Focused tests.
- Model artifact verification.
- Full-suite caveat when a separately running server is required.

### ML evaluation findings

The evaluation artifact is represented by:

- MAE `0.24793` versus mean baseline `0.24781`.
- RMSE `0.28727` versus mean baseline `0.28693`.
- R² `-0.00241` versus baseline `0.00000`.
- 3,000 rows.
- 20 unique roles.
- Target range `0.00074` to `0.99962`.
- Mean `0.50132`.
- Standard deviation `0.28693`.
- Full-data selected alpha `100.0`.
- Approximately zero or negative R² for every role.
- Need for role-specific baselines, duplicates audit, target-generation audit, O*NET mappings, provenance, and abstention.

The focused tests are also recorded:

- Alias and boundary behavior.
- Evidence returned from skills-gap analysis.
- Hybrid explainability fields.
- Model metadata.
- Semantic role similarity.
- Role deduplication.

### Attached full enhancement roadmap

The longer attached roadmap’s topics are covered, including:

- Executive assessment.
- Product promise.
- Current end-to-end flow.
- Current information architecture.
- Recommended primary navigation.
- Current recommendation-list architecture.
- Recommended role-plan structure.
- Learning item fields.
- Multiple learning pathways.
- Current strong features.
- Features that should be combined.
- Features to defer or de-emphasize.
- Landing-page simplification.
- Duplicate mode-control removal.
- Progressive disclosure.
- Score certainty reduction.
- Priority action card.
- Contextual chat actions.
- Recommended result-page layout.
- Benchmark inspiration and boundaries.
- Technical architecture and maintainability.
- Security and privacy risks.
- ML/model trust and explainability.
- MVP scope.
- Product metrics.
- Phased implementation.
- Target information architecture.
- Learning roadmap redesign.
- Application readiness.
- Progress comparison and re-analysis.

### Tools and extensions from the attached tooling list

| Mentioned tool or skill | Decision |
|---|---|
| UI/UX Pro Max / `ui-ux-pro-max-skill` | Optional design-review workflow; do not add as a runtime dependency. Use its accessibility/design principles only after verifying its source and compatibility. |
| Impeccable | Optional design-review method; use for audits, not as a core application dependency. |
| Motion Design Skill | Optional review guidance; use restraint and respect reduced-motion preferences. |
| Ponytail | Optional code-simplicity method; apply manually through small diffs and dependency discipline. |
| Playwright CLI / Playwright Test | Recommended free/open-source browser testing tool. |
| Playwright VS Code extension | Recommended free extension for test explorer, recording, debugging, and traces. |
| Superpowers | Optional development workflow/TDD method; replicate its useful discipline with the phase prompts and checkpoint rules. |
| OmniRoute | Not required; defer because it adds provider and privacy complexity. |
| NVIDIA NIM | Optional provider; do not make the project dependent on quotas or external API keys. |
| OpenCode | Optional terminal agent; not required when Codex/Aider/Continue are available. |
| Aider | Recommended optional free/open-source terminal assistant with local Ollama support. |
| Claude Code | Optional; not required for this project. Use only if the user already has access and wants another agent. |
| Awesome DESIGN.md | Recommended concept: maintain a project-owned design specification. |
| Design DNA / likethat | Optional inspiration; do not reverse-engineer third-party designs without permission. |
| Genjutsu | Not required; defer creative coding and complex interaction systems. |
| Three.js / WebGPU / TSL | Not required for the core workflow; defer unless a concrete 3D visualization is approved. |
| GSAP | Not required initially; use CSS transitions or small accessible animations first. |
| The Council | Not required; avoid multi-agent complexity until the implementation loop is stable. |
| Watermark Remover | Unrelated to the project; do not install. |
| Ollama | Recommended for local/private model experiments already supported by the project. |
| Continue | Recommended optional open-source VS Code coding assistant. |
| axe-core with Playwright | Recommended for accessibility tests. |
| Lighthouse CI | Recommended after stable screens exist. |
| Ruff, Bandit, pip-audit, Dependabot, CodeQL | Recommended free quality and security checks. |

### User requests that remain intentionally unresolved

The following items were not silently decided because they materially affect scope, privacy, licensing, or architecture:

- Whether to persist raw resume text or only derived evidence.
- Which O*NET release to pin.
- Whether to use official Interest Profiler integration or a local questionnaire.
- Whether Lightcast access will ever be licensed.
- Which external labor-market datasets are legally and technically available.
- Whether reminders are in-app, email, calendar/ICS, or multiple channels.
- Whether external LLM providers are allowed.
- When to migrate from SQLite to a multi-worker database.
- Whether a browser extension is needed after manual job capture.
- How the automation-exposure target will be redefined or replaced.

These must be documented in decision records before implementation locks them in.

### Exact status boundary

To avoid any ambiguity, this conversation completed planning, audit, documentation, branch creation, checkpoint tagging, and branch push. It did **not** yet implement the new job/application schema, O*NET import, canonical skill database, ordered learning plans, full UI/UX redesign, or merged RidgeCV pipeline in the connected GitHub source. Those remain sequential implementation work described in this report.
