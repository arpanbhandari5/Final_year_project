# 10-Day Low-Cost Coding Plan for Final_year_project

## Executive recommendation

Because GitHub Copilot credits are exhausted and money is limited, do **not** immediately buy Copilot Pro+, Max, or another expensive high-model subscription.

Use this order:

1. **Check Copilot Student first.** If you are a verified student, GitHub lists Copilot Student as free.
2. **Use local AI with Ollama + Continue** in VS Code if your computer has enough memory.
3. **Use Cline with Ollama** only if you need an agent-style workflow; give it narrow permissions and review every diff.
4. **Use Aider with Ollama** for small terminal-based commits and code review.
5. **Use the AI access you already have** for architectural decisions and difficult debugging instead of spending it on routine edits.
6. If local models are unusably slow and Copilot is essential, consider **Copilot Pro for one month only**, not Pro+, Max, or an annual commitment. GitHub’s official documentation currently lists Copilot Pro at $10 USD/month, but taxes, currency conversion, regional pricing, and plan details can change. Verify the final amount on GitHub before confirming.

You do not need a high model for every task. Use a stronger model only for design decisions, migrations, security review, and difficult debugging. Use a local model or free autocomplete for repetitive implementation.

---

## 1. First check: Copilot Student

GitHub’s current plan documentation lists Copilot Student as a free plan for verified students.

Check:

1. Open GitHub Settings.
2. Open **Billing & licensing** or **Plans and usage**.
3. Check whether Copilot Student is available.
4. If you are a university student, open GitHub Education and apply for the Student Developer Pack.
5. Complete student verification using your institutional email or accepted proof.
6. Do not create a second account to bypass limits.

If approved, use Copilot Student for the 10-day implementation period. The official plan documentation says Copilot Student has an allowance of GitHub AI Credits and auto model selection, so it may not provide unlimited premium high-model use. It can still be enough if you use focused prompts and local AI for routine work.

Official reference: [GitHub Copilot plans](https://docs.github.com/en/copilot/get-started/plans)

---

## 2. Zero-cost local setup: Ollama + Continue

This is the best no-subscription option if your computer can run local models.

Continue is an open-source VS Code coding assistant. Ollama runs models locally, so there is no per-request cloud credit cost. The trade-off is that your computer supplies the RAM, storage, and processing power.

### Requirements

A practical starting point:

| Available RAM | Recommended local model size | Expected use |
|---:|---:|---|
| 8 GB | 1.5B–3B | Simple edits, explanations, small tests; slow/limited reasoning |
| 16 GB | 7B–8B | Good general coding and review for focused files |
| 32 GB | 13B–14B | Better reasoning, slower and heavier |
| 32 GB+ with strong GPU | Larger models | Optional; not necessary for this project |

Continue’s official Ollama guide recommends at least 8 GB RAM, 16 GB or more for better use, and at least 10 GB free storage. Actual needs vary by quantization, context length, operating system, and GPU.

### Install on Windows

1. Install Ollama from [ollama.com](https://ollama.com/).
2. Install the **Continue** extension from the VS Code Extensions view.
3. Open a terminal and verify:

```powershell
ollama --version
ollama list
```

4. Download one coding model appropriate for your computer. Start small:

```powershell
ollama pull qwen2.5-coder:7b
```

If 7B is too slow or your machine has only 8 GB RAM:

```powershell
ollama pull qwen2.5-coder:1.5b
```

5. Check that Ollama responds:

```powershell
curl http://localhost:11434
```

6. Restart VS Code.
7. Open Continue’s model selector and select the downloaded Ollama model.
8. Set context length conservatively, for example 4096 or 8192. Larger context consumes more memory.

### Install on Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
ollama pull qwen2.5-coder:7b
curl http://localhost:11434
```

Then install Continue in VS Code and select the local model.

### Model choices

Start with one model rather than downloading many:

- `qwen2.5-coder:1.5b` — very light, simple edits and autocomplete
- `qwen2.5-coder:7b` — practical starting point for Python/HTML/CSS/JavaScript
- `deepseek-coder:6.7b` — another focused coding option if available in your Ollama registry
- `llama3.1:8b` or a current comparable instruct model — general reasoning and code review

Model names and tags change. Always use the exact tag shown by the Ollama model page and verify with `ollama list`.

### Continue workflow

Use Continue for:

- Explain one file
- Add tests for one function
- Refactor one small module
- Review a Git diff
- Fix one failing test
- Generate a migration draft
- Improve one template or CSS component

Do not ask it to “implement the entire roadmap” in one prompt.

Official references:

- [Continue Ollama guide](https://docs.continue.dev/guides/ollama-guide)
- [Ollama VS Code integration](https://docs.ollama.com/integrations/vscode)

---

## 3. Cline with Ollama: optional agent mode

Cline can connect to Ollama and can perform agent-style work. It is more powerful and more risky than a simple chat assistant because it may inspect files, run commands, and edit multiple files.

Use it only when:

- The repository is on the correct branch.
- A checkpoint exists.
- You have a clean Git status.
- You give it one small objective.
- You review every command and diff.

Recommended Cline permissions:

- Allow read access.
- Ask before shell commands.
- Ask before file deletion.
- Ask before dependency installation.
- Ask before database migrations.
- Never provide production secrets.
- Never allow it to submit forms, publish, delete user data, or change account security.

Use a prompt such as:

```text
Inspect only app.py and tests/test_app.py. Do not edit yet. Explain how the current /api/skills-gap/analyze route works, identify its tests, and propose the smallest safe change for adding evidence metadata. Do not run destructive commands.
```

Then review its plan before allowing implementation.

Use Cline as an optional alternative to Continue, not in parallel with multiple agent tools editing the same files.

Official reference: [Cline local models](https://docs.cline.bot/running-models-locally/overview)

---

## 4. Aider with Ollama

Aider is useful when you prefer the terminal and Git-oriented small commits.

Install in a virtual environment or user environment according to its documentation. Then configure it for Ollama and include only the files relevant to the current task.

Typical workflow:

```bash
aider --model ollama/<exact-model-name> app.py tests/test_app.py
```

Use Aider for:

- Small refactors
- Test creation
- Code review
- Focused bug fixes
- Commit-sized changes

Do not include the entire repository at once. Start with two to five files.

Official references:

- [Aider with Ollama](https://aider.chat/docs/llms/ollama.html)
- [Aider LLM configuration](https://aider.chat/docs/llms.html)

---

## 5. Do not depend on uncertain free hosted tools

Free cloud coding tools can change their quotas, model availability, or eligibility. Treat them as optional experiments, not the core 10-day plan.

The search results for Gemini Code Assist currently contain conflicting information: one official page advertises high limits while another official deprecation page states that certain individual IDE extensions stopped serving requests from June 18, 2026. Do not build your 10-day plan around Gemini availability without verifying the current status in your own VS Code extension marketplace and account.

Amazon Q Developer has a perpetual free tier with limits, but it requires its own account/provider setup. It may be useful as a backup, but it is not necessary if Ollama works.

Avoid creating many new accounts or switching providers repeatedly. That spends time and creates privacy/configuration risk.

---

## 6. If you must pay for only 10 days

Use the lowest appropriate monthly plan, not the highest plan.

GitHub’s official plan documentation currently lists:

| Plan | Listed price | Suitability for your situation |
|---|---:|---|
| Copilot Free | $0 | Use immediately; limited features and AI credits |
| Copilot Student | $0 if verified | Best if eligible |
| Copilot Pro | $10/month | Possible last resort for a 10-day sprint |
| Copilot Pro+ | $39/month | Not recommended for a limited budget |
| Copilot Max | $100/month | Do not buy for this project sprint |

The final price may vary by taxes, currency, billing region, and current plan changes.

If you choose Pro:

1. Confirm the exact final price before payment.
2. Set a calendar reminder immediately for cancellation.
3. Use it for difficult architecture, debugging, and review—not routine text generation.
4. Use local Ollama for repetitive edits.
5. Cancel through GitHub’s subscription controls before the next billing cycle if you do not want renewal.

GitHub states that cancelling retains access until the current billing cycle ends and then downgrades to Copilot Free. Check the current billing screen because billing behavior and available options can change.

Official reference: [Changing or cancelling Copilot plans](https://docs.github.com/en/copilot/how-tos/manage-your-account/view-and-change-your-copilot-plan)

Do not buy a high-priced plan simply because a high model sounds necessary. For this repository, careful scope control and testing are more important than using the maximum model.

---

## 7. How to use AI efficiently for this project

### Use a strong model only for

- Database design and migrations
- Security review
- ML evaluation interpretation
- O*NET data-model decisions
- Cross-module debugging
- Planning a risky refactor
- Reviewing a large diff
- Diagnosing a failure that local models cannot solve

### Use local AI for

- Test scaffolding
- CSS changes
- Template cleanup
- Documentation
- Small helper functions
- Adding type hints
- Explaining existing code
- Simple refactoring
- Writing fixtures
- Formatting and lint fixes

### Use ordinary editor tools for

- Search/replace
- Rename symbol
- Format document
- Git diff review
- Running tests
- Running `rg`
- Running `pytest`
- Running `compileall`

Never spend premium model requests on work that an editor command can do reliably.

---

## 8. Ten-day implementation schedule

### Day 1 — Setup and baseline

- Confirm the correct branch: `develop/final-year-enhancement`.
- Pull the latest branch.
- Create a clean Git checkpoint.
- Install Ollama.
- Install Continue.
- Download one model.
- Run `ollama list`.
- Install project dependencies.
- Install pytest.
- Run compilation and tests.
- Record failures before editing.

Commands:

```bash
git switch develop/final-year-enhancement
git pull --ff-only
python -m compileall -q .
python -m pytest -q
```

If pytest is missing:

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
```

### Day 2 — Security hardening

Use the stronger model only if needed. Otherwise use Continue.

Tasks:

- Production secrets
- Debug mode
- Default credentials
- Unsafe rendering
- Upload validation
- Authorization tests
- Sensitive log review

Run focused tests and create a checkpoint.

### Day 3 — ML reproducibility

Tasks:

- Inspect the actual current ML code.
- Add or verify RidgeCV.
- Add metadata and dataset hashes.
- Add baselines.
- Preserve transparent scoring.
- Do not claim predictive improvement without evaluation.

Run training, evaluation, and ML tests.

### Day 4 — Intent and evidence

Tasks:

- Add target role and constraints.
- Add editable evidence.
- Add ownership tests.
- Keep raw resume persistence decisions explicit.

### Day 5 — Job capture foundation

Tasks:

- Add manual job paste/URL capture.
- Add saved-job model and ownership.
- Show required/preferred skills.
- Do not add scraping.

### Day 6 — Application tracker

Tasks:

- Add application status.
- Add notes and follow-up date.
- Add resume version reference.
- Use Alpine or HTMX only for small local interactions if appropriate.

### Day 7 — Learning path

Tasks:

- Add a first prioritized action.
- Add fastest practical route.
- Add credential route.
- Add foundation route.
- Add prerequisite and progress metadata.

### Day 8 — UI/UX polish

Tasks:

- Simplify landing page.
- Improve tokens and shared components.
- Add AutoAnimate to dynamic lists.
- Add restrained Motion only where useful.
- Preserve reduced motion.

### Day 9 — Testing and accessibility

Tasks:

- Playwright smoke tests.
- axe-core scans.
- Lighthouse audit.
- Keyboard navigation.
- Mobile viewport review.
- Error/empty/loading states.

### Day 10 — Integration and release checkpoint

Tasks:

- Full pytest.
- Compile check.
- ML evaluation.
- Browser smoke tests.
- Security scan.
- Review Git diff.
- Update README and changelog.
- Create a release candidate checkpoint.

Do not start a new large feature on Day 10.

---

## 9. Prompt template that saves AI credits

Use this prompt with any assistant:

```text
Work only on the following narrow task:
[TASK]

Repository:
Final_year_project, Flask/Jinja/vanilla JavaScript.

Allowed files:
[LIST 1–5 FILES]

Do not:
- rewrite the repository
- migrate frameworks
- change unrelated routes
- add dependencies unless necessary
- modify database schema without a migration
- use unsafe innerHTML
- expose secrets
- claim tests passed unless they ran

First inspect the files and tests. Then state the smallest plan. Implement only after the plan. Add or update focused tests. Run the focused tests and report exact results. Show the diff summary and list any risks. Stop after this task; do not continue into the next roadmap phase.
```

This is more effective than asking for “make the whole project advanced.”

---

## 10. Git safety before using an agent

Before every AI coding session:

```bash
git status --short
pytest -q
python -m compileall -q .
```

Create a temporary branch or checkpoint:

```bash
git switch -c work/day-02-security
```

After the agent edits:

```bash
git diff --stat
git diff --check
pytest -q
python -m compileall -q .
```

Do not accept an AI-generated change if:

- It changes unrelated files.
- It removes tests.
- It disables security checks.
- It adds a secret.
- It uses unsafe rendering.
- It silently changes score meaning.
- It changes model/data versions without recording them.
- It skips a migration.
- It claims success without running tests.

---

## 11. Privacy and local-model warning

Local Ollama is more private than a hosted API, but prompts can still contain sensitive resume data on the local computer. Protect the machine, do not upload private data to model-sharing sites, and do not expose the Ollama port publicly.

Keep `OLLAMA_HOST` bound to localhost unless you deliberately understand network security. Never commit model configuration containing API keys.

For external assistants, avoid sending:

- Full resumes
- Passwords
- OAuth tokens
- Database files
- Production `.env` files
- Private user records
- Unredacted job application histories

Use a synthetic resume fixture when asking a hosted model for help.

---

## 12. Final recommendation for your budget

**Best zero-cost plan:**

```text
Copilot Student check
→ Ollama + Continue
→ Aider or Cline only when needed
→ Existing AI access reserved for difficult decisions
→ Git checkpoints and tests every day
```

**Best low-cost paid fallback:**

```text
One month of Copilot Pro only if local AI is unusably slow
→ cancel immediately after activation if you do not want renewal
→ do not buy Pro+, Max, or an annual plan
```

The project can make substantial progress in ten days without unlimited high-model credits if each day has one narrow objective, one test gate, and one checkpoint.
