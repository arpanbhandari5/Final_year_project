# AI-Based Career and Skill

This repository contains a Flask-based application for career assessment and skill recommendation using resume parsing, risk analysis, and machine learning models.

## Project Structure

- `app.py` — main Flask application entry point
- `bootstrap.py` — app initialization helpers
- `evaluation.py` — evaluation routines
- `risk_assessor.py` — risk assessment logic
- `resume_parser.py` — resume parsing utilities
- `train_model.py` — model training scripts
- `routes/` — route registration (`api.py`, `auth.py`, `chat.py`, `pages.py`, `admin.py`)
- `services/` — career intelligence services (`resume_service.py`)
- `tests/` — pytest suite (`test_app.py`, `test_score_resume.py`, `test_match_risk.py`, `test_role_enrichment.py`)
- `data/` — datasets used for training and analysis
- `static/` — static frontend assets (`script.js`, `styles.css`)
- `templates/` — Flask HTML templates
- `.vscode/` — VS Code workspace settings

## Setup

1. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the application:
   ```powershell
   python app.py
   ```

## API Reference

All scoring/matching/risk endpoints accept `multipart/form-data` (file upload, field `resume` or `resume_file`) **or** `application/json` with `resume_text`, unless noted otherwise.

### Authentication

The API does not use JWT bearer tokens. Requests are authenticated with the **session cookie + CSRF token header** (Flask-WTF):

| Header | Value |
|---|---|
| `X-CSRFToken` | Token from `GET /api/csrf-token` → `{ "csrf_token": "..." }` |
| `Content-Type` | `application/json` for JSON bodies; omit for multipart (the browser sets the boundary) |

A missing/expired token returns `400` with a CSRF error body; clients should refresh via `/api/csrf-token` and retry once (the bundled frontend `apiCall()` wrapper does this automatically).

### OAuth Sign-In Setup (Google / GitHub / LinkedIn)

OAuth callbacks are registered per provider. **`localhost` and `127.0.0.1` are different origins for cookies** — register **both** redirect URIs in each provider's console and access the app consistently, or state validation will fail at the callback (`MismatchingStateError`).

| Provider | Console | Redirect URIs to register |
|---|---|---|
| Google | [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials) | `http://localhost:5000/login/google/authorized` · `http://127.0.0.1:5000/login/google/authorized` |
| GitHub | [GitHub → Developer settings → OAuth Apps](https://github.com/settings/developers) | `http://localhost:5000/login/github/authorized` · `http://127.0.0.1:5000/login/github/authorized` |
| LinkedIn | [LinkedIn Developer Portal → Products → Sign In](https://www.linkedin.com/developers/apps) | `http://localhost:5000/login/linkedin/authorized` · `http://127.0.0.1:5000/login/linkedin/authorized` |

Then set the matching `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` (etc.) in `.env` and restart. Broken callbacks (state mismatch, cancelled consent, invalid grant) redirect back to `/login` with a friendly error instead of a 500 — this is covered by `tests/test_oauth_errors.py`.

### `POST /score_resume`

Scores resume strength on a 0–100 scale with three sub-scores. Deterministic (rule-based), no LLM calls.

**Request** — multipart file **or** JSON body:

```json
{ "resume_text": "John Doe\nData analyst with 3 years of experience..." }
```

**Response `200`**:

```json
{
  "success": true,
  "result": {
    "final_score": 54,
    "skill_score": 48,
    "experience_score": 60,
    "quality_score": 55,
    "feedback": "Average resume. List more skills, quantify achievements...",
    "skills": ["Python", "SQL", "Power BI"],
    "strengths": ["Contact info", "Skill keywords"],
    "improvements": ["No phone detected", "No metrics found"],
    "word_count": 186
  }
}
```

`final_score = round(0.4·skill + 0.3·experience + 0.3·quality)`. Banding: `≥ 80` strong · `70–79` good · `40–69` average · `< 40` needs work.

**Errors**: `400` — no file / text under 20 chars / unreadable file.

### `POST /match_jobs`

Returns ranked role matches for a resume **or** an explicit skill list.

**Request** — JSON body (one of):

```json
{ "skills": ["python", "sql", "power bi"] }
```

```json
{ "resume_text": "..." }
```

- With `resume_text` (≥ 20 chars): full ML similarity over the bundled corpus.
- With only `skills` (array or comma-separated string): curated skill → archetype coverage scoring (5 covered keywords ⇒ 100%).

**Response `200`**:

```json
{
  "success": true,
  "total": 4,
  "jobs": [
    {
      "title": "Data Analyst",
      "score": 80,
      "skills": ["python", "sql"],
      "risk_level": "Moderate",
      "risk_score": 0.512,
      "industry": "Tech",
      "trait_chips": ["Skill complexity 53%", "Domain knowledge 53%"],
      "job_board_links": [
        { "label": "Indeed", "url": "https://www.indeed.com/jobs?q=Data%20Analyst" },
        { "label": "LinkedIn", "url": "https://www.linkedin.com/jobs/search/?keywords=Data%20Analyst" },
        { "label": "Naukri", "url": "https://www.naukri.com/data-analyst-jobs" }
      ]
    }
  ]
}
```

Jobs are sorted by descending `score`. `risk_level` ∈ `Low | Moderate | Elevated`.

**Errors**: `400` — neither skills nor resume text provided · `503` — model artifacts unavailable.

### `POST /predict_risk`

Automation-risk prediction for a resume, using the local ML model.

**Request** — multipart file **or** JSON body:

```json
{ "resume_text": "..." }
```

**Response `200`**:

```json
{
  "success": true,
  "risk_level": "Moderate",
  "risk_score": 0.475,
  "explanation": "Moderate exposure (48%). Parts of this role can be automated; strengthening transferable skills will keep you ahead.",
  "bands": { "low": 0.35, "moderate": 0.7 }
}
```

Banding: `risk_score < 0.35` → Low · `< 0.70` → Moderate · `≥ 0.70` → Elevated. Deterministic: identical input yields identical output.

**Errors**: `400` — no file / text under 20 chars · `503` — model artifacts unavailable.

### `POST /api/upload`

The original full-analysis endpoint (also aliased at `POST /api/analyze`). Runs the complete ML pipeline in one call and feeds every dashboard section (risk ring, role bars, reasoning cards, next steps).

**Request** — multipart file **or** JSON body:

```json
{ "resume_text": "...", "mode": "standard" }
```

`mode` ∈ `standard` (local ML) | `advanced` (adds LLM narrative when configured; falls back silently to standard).

**Response `200`** (key fields; full payload includes roadmap, RIASEC, reasoning):

```json
{
  "success": true,
  "mode": "standard",
  "risk_score": 0.475,
  "risk_label": "Moderate",
  "top_roles": [
    {
      "job_role": "Data Analyst",
      "industry": "Tech",
      "similarity": 0.68,
      "risk_score": 0.41,
      "trait_chips": ["Skill complexity 53%", "Domain knowledge 53%"],
      "job_board_links": ["Indeed", "LinkedIn", "Naukri objects with url"]
    }
  ],
  "skill_clusters": [],
  "roadmap": [],
  "riasec": { "scores": {} },
  "reasoning": { "summary": "...", "skills_detected": ["Python", "SQL"] },
  "guided_next_steps": {}
}
```

Note: role objects carry `trait_chips` and `job_board_links` (training internals `text`/`skills` are stripped server-side).

**Errors**: `400` — no file/text · `500` — analysis failure (message in `error`).

### `POST /api/compare`

Side-by-side risk comparison of two resume texts.

**Request** — JSON body:

```json
{ "text_a": "resume A text", "text_b": "resume B text", "mode": "standard" }
```

**Response `200`**:

```json
{
  "success": true,
  "mode": "standard",
  "risk_a": 0.41,
  "risk_b": 0.68,
  "risk_delta": 0.27,
  "label_a": "Moderate",
  "label_b": "Elevated",
  "top_role_a": "Data Analyst",
  "top_role_b": "Customer Support",
  "riasec_a": "Investigative",
  "riasec_b": "Enterprising"
}
```

`risk_delta` is `abs(risk_a - risk_b)`, rounded to 3 decimals.

**Errors**: `400` — either text missing · `500` — analysis failure.

### Example (curl)

> **Important:** the CSRF token is bound to the server-side session, so every
> request must carry the **same cookie jar** that obtained the token. Without
> `-b cookies.txt -c cookies.txt` the POST fails with `400 — The CSRF session
> token is missing.`

```bash
# 0. Start from a clean cookie jar
rm -f cookies.txt

# 1. Get a CSRF token (and keep the session cookie that issued it)
TOKEN=$(curl -s -c cookies.txt http://localhost:5000/api/csrf-token \
  | python -c "import sys,json;print(json.load(sys.stdin)['csrf_token'])")

# 2. Score an uploaded resume (multipart: do NOT set Content-Type manually)
curl -X POST http://localhost:5000/score_resume \
  -b cookies.txt -c cookies.txt \
  -H "X-CSRFToken: $TOKEN" \
  -F "resume=@resume.txt"

# 3. Match jobs from extracted skills
curl -X POST http://localhost:5000/match_jobs \
  -b cookies.txt -c cookies.txt \
  -H "X-CSRFToken: $TOKEN" -H "Content-Type: application/json" \
  -d '{"skills":["python","sql","power bi"]}'

# 4. Predict automation risk
curl -X POST http://localhost:5000/predict_risk \
  -b cookies.txt -c cookies.txt \
  -H "X-CSRFToken: $TOKEN" -H "Content-Type: application/json" \
  -d '{"resume_text":"..."}'
```

## Notes

- The `.env` file is intentionally excluded from version control.
- The repository contains preprocessed datasets and model files under `data/` and `ml_models/`.
