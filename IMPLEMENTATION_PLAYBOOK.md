# Final_year_project Sequential Implementation Playbook

## 1. Recommended working method

Use one feature branch per phase and one Git checkpoint after every green test gate. Do not ask Copilot, Codex, or another agent to rewrite the whole repository in one pass. The project is a Flask application with a large `app.py`, local ML artifacts, SQLite storage, templates, JavaScript, and existing authentication. Large unbounded edits create regression risk.

Recommended branch layout:

```text
main
└── develop/final-year-enhancement
    ├── phase-00-baseline
    ├── phase-01-production-hardening
    ├── phase-02-ml-reproducibility
    ├── phase-03-intent-and-evidence
    ├── phase-04-job-application-workflow
    ├── phase-05-onet-occupation-data
    ├── phase-06-learning-path
    ├── phase-07-grounded-coaching
    └── phase-08-ui-ux-polish
```

If one branch per phase feels heavy, keep a single development branch but create annotated tags named `checkpoint-phase-00-green`, `checkpoint-phase-01-green`, and so on.

Before editing, create a clean baseline:

```bash
git switch main
git pull --ff-only origin main
git switch -c develop/final-year-enhancement
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
python -m compileall -q .
git tag checkpoint-baseline-green
git push origin develop/final-year-enhancement --tags
```

The repository currently contains an older ML implementation on the connected checkout. Treat the newer ML results in the audit as an unmerged change set until the code is actually visible in GitHub and passes the gates below.

## 2. Non-negotiable rules for every phase

1. Read the relevant files before editing.
2. Make the smallest related change that satisfies the phase.
3. Write or update tests before or alongside implementation.
4. Run focused tests first, then the full local suite.
5. Run security and accessibility checks for UI or authentication changes.
6. Inspect the diff and remove unrelated formatting changes.
7. Record assumptions, migrations, model versions, and known limitations.
8. Create a checkpoint only after tests are green.
9. Never silently delete user data, rewrite historical analysis, or change score semantics without a migration and release note.
10. Never call the automation score a job-loss prediction, hiring prediction, ATS score, or personal probability.

## 3. Phase sequence and checkpoint gates

### Phase 00 — Baseline, inventory, and rollback

Goal: establish a known-good starting point.

Tasks:

- Confirm Python, Node, npm, Git, and database versions.
- Capture the current commit and test results.
- Run `pytest -q` and `python -m compileall -q .`.
- Run the existing model training command and record artifact hashes.
- Export the current route list and database schema.
- Verify the current branch and remote.
- Create a local database backup before migrations.
- Add `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md`, and `docs/DECISIONS.md` if absent.

Gate:

```bash
pytest -q
python -m compileall -q .
git diff --exit-code
```

Checkpoint:

```bash
git add .
git commit -m "chore: establish enhancement baseline"
git tag checkpoint-phase-00-green
git push origin develop/final-year-enhancement --tags
```

Rollback:

```bash
git reset --hard checkpoint-phase-00-green
```

### Phase 01 — Production and security hardening

Goal: remove risks before retaining more user data.

Tasks:

- Remove default admin/student passwords from production configuration.
- Require `FLASK_SECRET_KEY`, admin credentials, and database configuration in production.
- Fail closed or show a clear startup warning when production secrets are missing.
- Ensure `FLASK_DEBUG` is false in production.
- Disable insecure OAuth transport outside local development.
- Review cookie security, CSRF, upload limits, file validation, and error-page leakage.
- Replace unsafe `innerHTML` rendering with safe DOM APIs or a trusted sanitizer.
- Add per-user authorization tests for upload, feedback, analysis history, and future records.
- Document external Ollama/OpenAI-compatible data flow and add an explicit local/external model setting.
- Redact resumes, tokens, passwords, and prompt content from logs.
- Add retention, export, and deletion design before introducing persistent resume content.

Gate:

```bash
pytest -q
python -m compileall -q .
rg -n "admin@prayash|Student@123|innerHTML|FLASK_DEBUG|OAUTHLIB_INSECURE_TRANSPORT" .
```

The grep output must be reviewed, not blindly eliminated: development-only examples may remain if clearly isolated and documented.

Checkpoint:

```bash
git commit -am "security: harden production defaults and rendering"
git tag checkpoint-phase-01-green
git push origin develop/final-year-enhancement --tags
```

### Phase 02 — ML reproducibility and honest evaluation

Goal: merge the reported ML improvements without overstating accuracy.

Tasks:

- Replace fixed Ridge with `RidgeCV` inside a scikit-learn `Pipeline`.
- Fit vectorization inside each evaluation fold to prevent leakage.
- Add 12,000-feature TF-IDF, bigrams, `min_df=2`, and sublinear TF only if repeated validation supports it.
- Convert numeric occupation fields into documented buckets.
- Store original values, transformed buckets, thresholds, and transformation version.
- Add model version, dataset hashes, row counts, Git commit, selected alpha, target definition, feature configuration, and training timestamp.
- Add mean, median, role-mean, and industry-mean baselines.
- Add repeated cross-validation and fold-level metrics.
- Add duplicate and near-duplicate checks.
- Report the number of rows, unique roles, target distribution, within-role variance, and between-role variance.
- Keep the hybrid score components separate from predictive validation.
- Add `low_evidence` or `insufficient_evidence` status when match evidence is weak.
- Add calibration metrics only when there are labels appropriate for calibration.
- Label the current risk result as contextual automation/task exposure.
- Keep a local fallback if artifacts are absent, but expose model metadata in the API.

Important interpretation: the supplied evaluation has 3,000 rows, 20 roles, R² of approximately zero across roles, and selected alpha 100. These findings require a target/data audit before deeper models.

Gate:

```bash
python train_model.py
python evaluation.py
pytest -q
python -m compileall -q .
```

The evaluation output must show the model beside baselines. A more complex model is not accepted merely because it produces a different score.

Checkpoint:

```bash
git add train_model.py evaluation.py risk_assessor.py utils.py ml_models tests docs
git commit -m "ml: add reproducible training metadata and honest baselines"
git tag checkpoint-phase-02-green
git push origin develop/final-year-enhancement --tags
```

### Phase 03 — Intent, goal, and evidence profile

Goal: collect user intent before generating recommendations.

Add:

- Target role
- Alternative roles
- Location/geography
- Seniority
- Time available per week
- Learning budget
- Preferred learning format
- Application goal
- User-selected constraints
- Evidence profile with correction controls
- Extracted skill evidence spans
- Confidence and provenance per extracted item

Recommended tables:

- `CareerGoal`
- `GoalConstraint`
- `ResumeProfile`
- `EvidenceItem`
- `SkillMention`
- `UserCorrection`

Do not persist raw resume text unless the user has consented and retention/deletion behavior is implemented.

Gate:

- Unit tests for validation and ownership.
- API tests for create, update, read, delete, export.
- Browser tests for onboarding, correction, and empty states.
- Verify that one user cannot access another user's goal or evidence.

Checkpoint:

```bash
git commit -am "feat: add career intent and editable evidence profile"
git tag checkpoint-phase-03-green
git push origin develop/final-year-enhancement --tags
```

### Phase 04 — Job and application workflow

Goal: create the central action loop missing from the current project.

Add:

- Manual job capture and paste fallback
- Job title, company, location, source URL, salary text, and full description
- Content hash and capture timestamp
- `JobPosting`
- `Application`
- `ApplicationEvent`
- `ResumeVersion`
- `AnalysisSnapshot`
- Notes, contacts, tasks, and follow-up date
- Table and Kanban tracker views
- Search, filtering, sorting, and stale-item indicators
- Explicit status transitions

The first version must not scrape job boards or auto-submit applications. Manual URL and paste capture is safer and sufficient for the MVP.

Per-job analysis should return:

- Required skills
- Preferred skills
- Matched skills
- Missing skills
- Resume evidence excerpts
- Evidence section
- Match method
- Confidence
- Score components
- Source and model versions
- Limitations

Gate:

- Flask API tests for CRUD and ownership.
- Migration test on a fresh database.
- Migration test on a database containing existing users and uploads.
- Playwright test: login → save job → analyze → create resume version → update application status → set follow-up.
- Accessibility scan on tracker and job-analysis pages.

Checkpoint:

```bash
git commit -am "feat: add job application workflow and explainable per-job analysis"
git tag checkpoint-phase-04-green
git push origin develop/final-year-enhancement --tags
```

### Phase 05 — O*NET-backed occupation intelligence

Goal: replace hard-coded role assumptions with versioned, attributable occupational data.

Tasks:

- Pin an approved O*NET database release.
- Preserve license and attribution requirements.
- Import occupations, alternate titles, tasks, skills, knowledge, abilities, technology, interests, Job Zones, education, experience, and related occupations.
- Store release/version and source date at field or dataset level.
- Add occupation search, detail, compare, and provenance endpoints.
- Show task, skill, technology, interest, education, Job Zone, wage, and outlook information separately.
- Distinguish O*NET facts, external BLS-linked data, resume evidence, local estimates, and generated narrative.
- Use the official Interest Profiler only through an authorized route; otherwise label local RIASEC inference as a heuristic approximation.

Gate:

- Import is repeatable and idempotent.
- Old snapshot remains readable.
- Occupation pages show source and date.
- Crosswalk and missing-data tests pass.
- No API key is exposed to the browser.

Checkpoint:

```bash
git commit -am "feat: add versioned O*NET occupation intelligence"
git tag checkpoint-phase-05-green
git push origin develop/final-year-enhancement --tags
```

### Phase 06 — Canonical skill system and ordered learning path

Goal: turn a flat course list into an evidence-backed learning path.

Add:

- Canonical skill IDs and aliases
- Raw phrase and evidence span
- Skill confidence and user correction
- Required/preferred/transferable skill types
- Prerequisite graph
- Course/project metadata
- Provider, level, duration, language, source, freshness
- Plan, plan item, skill coverage, progress event, project evidence, credential record
- Gap heatmap
- First recommended action
- Re-analysis after progress or resume changes

Do not scrape Coursera or LinkedIn Learning. Use permitted local catalog data, public metadata, official links, or authorized integrations.

Gate:

- Alias and false-positive tests.
- Course ranking tests.
- Prerequisite ordering tests.
- Plan progress persistence tests.
- UI test from skill gap to first learning action.
- Verify that completion is user-entered or provider-verified, not inferred from link clicks.

Checkpoint:

```bash
git commit -am "feat: add canonical skills and evidence-backed learning paths"
git tag checkpoint-phase-06-green
git push origin develop/final-year-enhancement --tags
```

### Phase 07 — Grounded coaching and practice

Goal: make chat a controlled interface to evidence and actions, not an opaque source of advice.

Add:

- Goal-aware coaching profile
- Source-linked responses
- Retrieved evidence spans
- Model and retrieval version
- Confidence/coverage
- Fact-versus-inference label
- User correction and helpfulness feedback
- Text interview practice
- Rubric-based feedback
- Roadmap handoff after practice
- Resettable conversation threads
- Privacy and retention controls

Keep external LLM use opt-in. Default to local Ollama or deterministic local analysis where practical.

Gate:

- Prompt-injection tests using untrusted job descriptions.
- Tests for unsupported claims and missing citations.
- Redaction tests for prompts and logs.
- Model failure fallback tests.
- Browser tests for chat reset, feedback, and action handoff.

Checkpoint:

```bash
git commit -am "feat: add grounded coaching and text practice"
git tag checkpoint-phase-07-green
git push origin develop/final-year-enhancement --tags
```

### Phase 08 — UI/UX system and quality pass

Goal: improve usability without changing backend semantics.

Target information architecture:

- Dashboard: current goal, progress, one next action, follow-up
- Career goal: target role and constraints
- Evidence profile: resume versions, skills, evidence, corrections
- Skill gaps: required/preferred skills and evidence
- Learning path: ordered courses and projects
- Applications: jobs, resumes, stages, contacts, tasks
- Career coach: grounded chat and practice
- Settings and privacy: consent, retention, export, deletion, integrations

UI principles:

- One clear next action per screen.
- No card-inside-card nesting unless it communicates a real hierarchy.
- Use progressive disclosure for technical metadata.
- Show source, date, confidence, and fact/inference labels near the result.
- Use skeleton loading for analysis and streaming states.
- Respect reduced-motion preferences.
- Use keyboard navigation, visible focus, labels, semantic headings, and sufficient contrast.
- Provide table/text alternatives for charts and graphs.
- Preserve the existing visual identity unless a deliberate design decision is recorded.

Gate:

- Playwright Chromium smoke suite.
- Responsive tests at mobile, tablet, and desktop widths.
- axe-core scans for key pages.
- Manual keyboard pass.
- Lighthouse performance/accessibility review.
- Visual screenshots reviewed at each breakpoint.

Checkpoint:

```bash
git commit -am "ui: refine career workflow and accessibility"
git tag checkpoint-phase-08-green
git push origin develop/final-year-enhancement --tags
```

## 4. Final verification gate

Before merging to `main`:

```bash
pytest -q
python -m compileall -q .
python train_model.py
python evaluation.py
npm ci
npx playwright test
```

If standalone authentication tests require a server, start it explicitly in a separate terminal and document the command. Do not hide skipped tests. CI should run:

- Unit tests
- Integration tests
- Model evaluation smoke test
- Playwright smoke tests
- Accessibility tests
- Secret/configuration checks
- Python compile check

Create a release candidate tag only after all gates pass:

```bash
git tag -a v0.2.0-rc1 -m "Final_year_project enhancement release candidate"
git push origin v0.2.0-rc1
```

## 5. Free or low-cost tools to use

| Tool | Use | Cost guidance | Recommendation |
|---|---|---|---|
| VS Code | Main editor | Free | Keep using it. |
| GitHub | Branches, PRs, Actions, checkpoints | Free tier available; limits apply | Use PRs and CI for every phase. |
| GitHub Copilot Free | Small code suggestions and chat | Free tier has published usage limits that can change | Use for focused files and tests, not whole-repo rewrites. |
| OpenAI Codex already available to you | Implementation and review | Depends on your existing access/limits | Use the phase prompts below and require diffs/tests. |
| Python pytest | Unit/integration tests | Free/open source | Required baseline. |
| Playwright Test | Browser E2E tests | Free/open source | Install locally and run Chromium first. Add Firefox/WebKit later. |
| Playwright VS Code extension | Test explorer, debugging, code generation, traces | Free | Strongly recommended. Official documentation: https://playwright.dev/docs/getting-started-vscode |
| `@axe-core/playwright` | Automated accessibility checks | Free/open source | Strongly recommended; combine with manual keyboard testing. |
| Lighthouse CI | Performance and accessibility regression checks | Free/open source | Add after the app has stable pages. |
| Ruff | Python linting and formatting | Free/open source | Recommended for fast feedback. |
| Bandit | Python security linting | Free/open source | Recommended before merge. |
| pip-audit | Dependency vulnerability checks | Free/open source | Run in CI; review findings rather than auto-upgrading blindly. |
| Continue | Open-source VS Code/JetBrains coding assistant | Free extension; model costs depend on provider | Good local alternative to conserve Copilot usage. Official docs: https://docs.continue.dev/ |
| Ollama | Local LLM runtime | Free/open source; needs local compute | Already fits the project’s privacy-first direction. |
| Aider | Terminal coding assistant | Free/open source; model cost depends on local/provider model | Useful for small commits with Git review. |
| GitHub Codespaces | Cloud development | Free quota is limited and changes | Optional, not required. |

### Tools to use cautiously

- **Playwright MCP:** useful for browser inspection and interaction, but add it only from a trusted official source and scope its tools. VS Code warns that local MCP servers can run arbitrary code. Use workspace configuration and never place secrets in `mcp.json`. Official documentation: https://code.visualstudio.com/docs/agent-customization/mcp-servers
- **UI/UX Pro Max, Impeccable, Motion Design Skill, Ponytail, and Superpowers:** treat these as workflow prompts, skills, or review methods unless you have verified a maintained official extension for your exact environment. Do not add them as runtime dependencies.
- **OmniRoute, NVIDIA NIM keys, OpenCode, and external gateways:** do not make them prerequisites. They introduce provider, privacy, quota, and configuration complexity. Use Ollama/Continue/Aider first.
- **Three.js, WebGPU, GSAP, Genjutsu, and Lottie:** do not add them unless a concrete product requirement needs interactive visualization. They are not necessary for the core career workflow.
- **Watermark-removal utilities:** unrelated to this project and should not be installed.

## 6. Suggested VS Code setup

Install only the useful baseline extensions:

- Python
- Pylance
- Python Debugger
- Playwright Test for VS Code
- Ruff
- GitLens, optional
- GitHub Copilot/Copilot Chat, if already available
- Continue, optional local-AI alternative

Recommended project files:

```text
.vscode/
  settings.json
  tasks.json
  launch.json
  extensions.json
  mcp.json          # only if Playwright MCP is deliberately enabled
playwright.config.ts
pytest.ini
pyproject.toml
```

Example safe workspace recommendation for MCP:

```json
{
  "servers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp"],
      "sandboxEnabled": true
    }
  }
}
```

Review the exact package name and publisher in the VS Code MCP gallery before installing. Do not hardcode API keys. Keep MCP disabled unless the current task needs browser automation.

## 7. Master prompt for GitHub Copilot, Codex, or another coding agent

Copy this prompt into the agent after opening the repository root. Use it as an operating contract, then use the phase prompts below one at a time.

```text
You are the senior engineer working inside the existing Final_year_project Flask repository.

Your job is to implement the requested phase only, preserving existing behavior unless the phase explicitly changes it. The application already contains resume parsing, skill extraction, TF-IDF role matching, skills-gap analysis, RIASEC-style interest profiling, course recommendations, optional Ollama narrative generation, RAG chat, authentication, admin, feedback, SQLite, PWA support, tests, and CI. Do not rewrite the repository or replace working features with a new framework.

Product direction:
Intent → target role → evidence → skill gap → ordered learning path → application action → progress re-check.

Product boundaries:
- The automation result is contextual automation/task exposure, not job-loss prediction, hiring prediction, ATS acceptance, employability probability, or a personal probability.
- Recommendations must show evidence, source, version, freshness, confidence, and fact-versus-inference status where applicable.
- Do not copy proprietary Lightcast, Teal, LinkedIn, Coursera, or other commercial data, prompts, scores, templates, or course content.
- Use public/licensed data only and record provenance.
- Do not send resume or application data to an external model unless the user has explicitly opted in.
- Do not add browser scraping or auto-submit behavior in the MVP.
- Do not expose secrets in source, logs, prompts, browser code, or MCP configuration.

Engineering rules:
1. Inspect the relevant files and existing tests before editing.
2. State a short implementation plan and list files you expect to change.
3. Write focused tests before or alongside the feature.
4. Implement the smallest coherent change.
5. Preserve backward compatibility for existing API responses unless a versioned response or migration is provided.
6. Use per-user authorization for every user-owned record and route.
7. Use safe rendering; do not introduce unsafe innerHTML or unescaped user/LLM content.
8. Add migrations or safe initialization for schema changes.
9. Do not change unrelated UI, dependencies, or formatting.
10. Run focused tests, then the full relevant suite, then compile/lint checks.
11. Inspect `git diff`, report failures honestly, and do not claim tests passed unless they actually passed.
12. At the end, provide: summary, changed files, tests run, results, migrations, risks, and a proposed checkpoint commit message.

Checkpoint policy:
- Never commit until tests pass unless I explicitly ask for a work-in-progress commit.
- After a green gate, create an annotated Git tag named checkpoint-phase-NN-green.
- If a migration or model artifact changes, record a rollback command and artifact version.
- Keep all changes reversible.

Before coding, ask only questions that materially change the design. Otherwise choose the smallest safe assumption and document it.
```

## 8. Phase prompts

### Phase 01 prompt

```text
Implement Phase 01 only: production and security hardening.

Inspect app.py, storage.py, templates, static JavaScript, .env.example, Docker files, and tests. Remove production dependence on default credentials, require production secrets, ensure debug and insecure OAuth transport are development-only, review secure cookies and upload validation, and identify unsafe innerHTML rendering. Replace unsafe rendering with safe DOM APIs or a narrowly scoped sanitizer. Add focused tests for configuration behavior, authorization, rendering safety, and log redaction. Do not redesign the product or add new feature domains yet.

Run pytest, compileall, and focused security tests. Report every changed file and any remaining development-only exceptions.
```

### Phase 02 prompt

```text
Implement Phase 02 only: reproducible ML training and honest evaluation.

Inspect train_model.py, evaluation.py, risk_assessor.py, utils.py, data schemas, bootstrap behavior, and ML tests. Add a Pipeline with RidgeCV and leakage-safe fold evaluation. Add the improved TF-IDF configuration only where justified. Add documented numeric buckets, dataset hashes, row counts, model version, selected alpha, Git commit, target definition, feature configuration, and training metadata. Add mean/median/role/industry baselines, duplicate checks, target-distribution reporting, and repeated or clearly documented cross-validation. Keep automation exposure explicitly contextual and add low-evidence/insufficient-evidence handling.

Do not claim improved prediction unless metrics beat the relevant baselines out of sample. Preserve the transparent lexical baseline. Run training, evaluation, focused ML tests, full pytest, and compileall. Do not commit generated artifacts unless the project’s existing workflow requires them; if artifacts are committed, document their hash and generation command.
```

### Phase 03 prompt

```text
Implement Phase 03 only: career intent and editable evidence profile.

Add target role, alternative roles, geography, seniority, time available, learning budget, learning format, and application goal. Add safe persistence and ownership for CareerGoal, GoalConstraint, ResumeProfile, EvidenceItem, SkillMention, and UserCorrection or the smallest equivalent schema. Preserve metadata-only resume behavior unless explicit consent and retention controls are present. Add APIs, validation, templates, and tests for create/update/read/delete/export and cross-user access denial. Provide clear empty, loading, and error states. Do not add job tracking yet.
```

### Phase 04 prompt

```text
Implement Phase 04 only: manual job and application workflow.

Add JobPosting, Application, ApplicationEvent, ResumeVersion, and immutable AnalysisSnapshot or equivalent models with user ownership, content hash, capture timestamp, source URL, and safe deletion/export behavior. Add manual paste/URL capture, tracker table/Kanban, status transitions, notes, follow-up date, and per-job explainable matching. Return required/preferred skills, matched/missing skills, resume evidence spans, match methods, score components, confidence, limitations, and model/data versions. Do not scrape job boards or auto-submit applications. Add Flask tests, migration tests, Playwright workflow tests, and accessibility checks.
```

### Phase 05 prompt

```text
Implement Phase 05 only: versioned O*NET occupation intelligence.

Use an approved O*NET data release and preserve attribution and license requirements. Create an idempotent import with stable O*NET-SOC identifiers, alternate titles, tasks, skills, knowledge, abilities, technologies, interests, Job Zones, education, experience, and related occupations. Store release/version/source dates. Add search/detail/compare/provenance endpoints and pages. Distinguish official occupational facts, external labor-market facts, user resume evidence, local estimates, and generated narrative. Keep the current local fallback if the import is unavailable. Add import, crosswalk, date, missing-data, and API-key protection tests.
```

### Phase 06 prompt

```text
Implement Phase 06 only: canonical skills and ordered learning path.

Create canonical skill identifiers, aliases, raw evidence spans, confidence, user correction, required/preferred/transferable type, prerequisites, course/project metadata, plan items, progress events, project evidence, and credentials. Convert the flat course list into an ordered path with one first action. Use only permitted local/public/provider-linked metadata. Add alias, false-positive, ranking, prerequisite, persistence, and UI tests. Do not infer mastery from a link click and do not scrape commercial course platforms.
```

### Phase 07 prompt

```text
Implement Phase 07 only: grounded coaching and text practice.

Add a user-controlled coaching profile, source-linked responses, evidence spans, model/retrieval version, confidence/coverage, fact-versus-inference labels, correction/helpfulness feedback, resettable threads, and text interview scenarios with rubric feedback. Link practice feedback to a learning-path action. Keep external model use opt-in, redact prompts/logs, defend against prompt injection from job descriptions, and provide deterministic/local fallback behavior. Add tests for unsupported claims, missing citations, redaction, fallback, reset, and action handoff.
```

### Phase 08 prompt

```text
Implement Phase 08 only: UI/UX and accessibility quality pass.

Preserve the current brand direction but create a coherent information architecture: Dashboard, Career Goal, Evidence Profile, Skill Gaps, Learning Path, Applications, Career Coach, and Settings/Privacy. Make one next action visible on each workflow screen. Reduce card nesting, improve hierarchy, loading/skeleton states, error/empty states, responsive behavior, contrast, focus states, semantic labels, reduced motion, and table alternatives. Use Playwright and axe-core for automated checks and perform a manual keyboard pass. Do not change backend score semantics or add a new frontend framework.
```

## 9. What “done” means

The project is ready for the next major release when a new user can complete this vertical slice without ambiguity:

1. Define a target role and constraints.
2. Upload or paste a resume.
3. Review and correct extracted evidence.
4. Save or paste a job description.
5. See explainable required/preferred skill gaps.
6. Start an ordered learning path.
7. Create or select a targeted resume version.
8. Track the application and set a follow-up.
9. Re-run analysis after changing evidence or progress.
10. Export or delete their data.

Success metrics should measure this loop:

- Goal-definition completion
- First-action completion
- Time to first action
- Skill-gap helpfulness
- Learning-path start and completion
- Evidence/project linkage
- Application tracker activation
- Follow-up completion
- Re-analysis after progress
- Provenance/citation coverage
- User correction rate
- Extraction and ranking quality
- Export/deletion success

## 10. Official references

- Playwright VS Code extension: https://playwright.dev/docs/getting-started-vscode
- Playwright accessibility testing: https://playwright.dev/docs/accessibility-testing
- VS Code MCP servers and security: https://code.visualstudio.com/docs/agent-customization/mcp-servers
- Continue open-source coding assistant: https://docs.continue.dev/
- Flask testing with pytest: https://flask.palletsprojects.com/en/stable/testing/
- Project enhancement roadmap: `ENHANCEMENT_ROADMAP.md`
- ML audit: `ML_AUDIT_AND_NEXT_STEPS.md`
