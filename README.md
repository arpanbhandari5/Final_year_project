# Prayash

**Learning for better future** — An AI-powered career intelligence platform that turns resumes into actionable learning strategies.

## Overview

Prayash combines local machine learning, O\*NET occupational intelligence, published task-exposure labels, and an optional local Llama explanation layer:

- **Resume analysis** — Parse the upload, extract skills, and keep resume text ephemeral.
- **Occupation matching** — Map the resume to job profiles and O\*NET clusters (exact SOC/title for task labels).
- **Historical occupation reference** — Local Ridge model on `data/automation_risk.csv`. Shown as e.g. 62/100 — Moderate. This is an occupation-level reference, **not** a validated personal probability of job loss, unemployment, replacement, or displacement. Legacy API fields `risk_score` / `risk_label` alias this reference only.
- **Contextual E0/E1/E2 task exposure** — After an exact occupation match, retrieve published GPTs-are-GPTs `human_labels`. Research model: GPTs-are-GPTs benchmark, **923 occupations**. Product coverage: selected **800** common occupations. The resume never creates or overrides a label. Percentages are task-distribution shares, not job-loss probabilities.
- **Career-development recommendations** — Skill gaps, courses, projects, RIASEC, and roadmaps from the deterministic pipeline.
- **Optional Ollama analysis** — Advanced mode only. Ollama explains verified JSON; it does not calculate or change scores, occupation codes, or E0/E1/E2 labels. If Ollama is off or unavailable, structured results still work.
- **Skills Gap Analysis** — Compares resume skills against target roles.
- **Career Path Suggestion** — Discovers suitable career trajectories based on detected skills.
- **Resume Quality Scoring** — Evaluates completeness and provides actionable improvements.

The five-level historical automation rubric remains deferred from the active model path and is not mixed into E0/E1/E2.

### Privacy-First Design

Resume data is **never** written to a permanent database. Files are read, analyzed in memory, and discarded after response generation. The SQLite database only stores anonymized metadata (filename, mode, risk score) for admin analytics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Flask 3.x, Flask-Login, Flask-SQLAlchemy, Flask-WTF |
| **ML Pipeline** | scikit-learn (Ridge regression, TF-IDF vectorizer) |
| **Data** | O\*NET occupation profiles, automation risk dataset, Coursera course catalog |
| **Resume Parsing** | pypdf (PDF), python-docx (DOCX), plain text |
| **LLM (optional)** | Ollama with Llama 3 for advanced narrative generation |
| **Database** | SQLite (metadata only) |
| **Frontend** | Vanilla HTML/CSS/JS with Inter font, glassmorphism UI |
| **Auth** | Email/Password, OAuth (Google, GitHub, LinkedIn, Microsoft) |
| **PWA** | Service worker, manifest, offline page, install prompt |

## Project Structure

```
Final_year_project/
├── app.py                 # Flask application entry point & routes
├── bootstrap.py           # Model artifact initialization
├── risk_assessor.py       # Historical occupation reference, role matching, RIASEC, optional Ollama
├── task_exposure_assessor.py  # Published E0/E1/E2 retrieval (exact occupation match only)
├── resume_parser.py       # PDF/DOCX/text resume extraction
├── storage.py             # SQLAlchemy models, auth, database helpers
├── utils.py               # Shared utilities (text cleaning, validation, ML helpers)
├── evaluation.py          # Historical baseline reproducibility audit
├── train_model.py         # Trains and serializes ML artifacts (model.pkl, courses.pkl)
├── requirements.txt       # Python dependencies
├── setup.ps1              # Windows PowerShell setup script
├── start.sh               # Unix/macOS setup script
├── Dockerfile             # Container build instructions
├── docker-compose.yml     # Multi-service container orchestration
├── .env.example           # Environment configuration template
├── data/
│   ├── automation_risk.csv       # O*NET automation risk scores
│   ├── coursera_catalog.csv      # Coursera course recommendations
│   ├── onet_interests.csv        # O*NET interest profiles
│   ├── onet_interest_keywords.csv
│   ├── onet_skils.csv            # O*NET skill mappings
│   └── resume_corpus.csv         # Resume training corpus
├── ml_models/              # Generated after training
│   ├── model.pkl           # Trained Ridge model + vectorizer + job vectors
│   └── courses.pkl         # Skill-to-course mapping index
├── instance/
│   └── prayash.db          # SQLite database (auto-created)
├── static/
│   ├── styles.css          # Full stylesheet (glassmorphism, animations, dark mode)
│   ├── script.js           # Client-side interactions & API calls
│   ├── auth-assistant.css  # Auth assistant chat widget styles
│   ├── auth-assistant.js   # Auth assistant chat widget logic
│   ├── manifest.json       # PWA manifest
│   ├── sw.js               # Service worker (offline support)
│   ├── offline.html        # Offline fallback page
│   └── icons/              # PWA icons (72x72 to 512x512)
├── templates/
│   ├── base.html           # Base layout with navbar, footer, PWA support
│   ├── index.html          # Landing page with dual-mode dashboard
│   ├── auth.html           # Combined login/signup page
│   ├── auth_assistant.html # Auth chat widget template
│   ├── workspace.html      # Authenticated analysis workspace
│   ├── admin.html          # Admin analytics dashboard
│   ├── verify_otp.html     # Email verification via OTP
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── 404.html / 500.html # Error pages
│   ├── methodology.html    # ML methodology documentation
│   ├── privacy.html        # Privacy policy
│   ├── insights.html       # Platform insights
│   └── partnerships.html   # Partnership information
└── tests/
    ├── test_app.py         # Pytest integration tests
    ├── test_auth_e2e.py    # End-to-end auth tests
    └── test_forgot_password.py  # Password reset flow tests
```

## Getting Started

### Prerequisites

- **Python 3.11+**
- **pip** (Python package manager)
- **Ollama** (optional, for Advanced mode narratives)

### Quick Start

```bash
# Clone and enter the project directory
cd Final_year_project

# Install dependencies
pip install -r requirements.txt

# Train the ML model
python train_model.py

# Run the application
python app.py
```

The server starts at **http://127.0.0.1:5000**.

### Windows Quick Setup

```powershell
.\setup.ps1
```

### Unix/macOS Quick Setup

```bash
./start.sh
```

### Docker Setup

```bash
docker-compose up --build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | `prayash-local-development-secret` | Flask session secret |
| `DATABASE_URL` | `sqlite:///instance/prayash.db` | SQLAlchemy database URI |
| `ADMIN_EMAIL` | `admin@prayash.local` | Default admin account email |
| `ADMIN_PASSWORD` | `prayash-admin` | Default admin account password |
| `PORT` | `5000` | Server port |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3` | Ollama model name |
| `GOOGLE_OAUTH_CLIENT_ID` | (empty) | Google OAuth client ID |
| `GITHUB_OAUTH_CLIENT_ID` | (empty) | GitHub OAuth client ID |
| `SMTP_HOST` | `smtp.gmail.com` | Email SMTP host |
| `SMTP_USERNAME` | (empty) | SMTP username |

Copy `.env.example` to `.env` and fill in your values.

## Default Accounts

| Role | Email / Username | Password |
|------|-----------------|----------|
| Admin | `admin@prayash.local` | `prayash-admin` |
| Student | `student` | `Student@123` |

> **Note:** The default student password was strengthened as part of a code cleanup. Run `python app.py` and use `/forgot-password` if you need to update credentials.

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | No | Landing page |
| `GET/POST` | `/login` | No | Login form |
| `GET/POST` | `/signup` | No | Registration form |
| `GET/POST` | `/verify-otp` | No | Email verification |
| `GET/POST` | `/forgot-password` | No | Password reset request |
| `GET/POST` | `/reset-password/<token>` | No | Password reset with token |
| `GET` | `/workspace` | Yes | Analysis workspace |
| `GET` | `/admin` | Admin | Admin dashboard |
| `POST` | `/api/upload` | No | Submit resume for analysis |
| `POST` | `/api/analyze` | No | Alias for upload |
| `GET` | `/api/analyze-stream` | No | SSE streaming analysis |
| `POST` | `/api/skills-gap/analyze` | No | Skills gap analysis |
| `GET` | `/api/skills-gap/roles` | No | Available target roles |
| `POST` | `/api/career-paths` | No | Career path suggestions |
| `POST` | `/api/learning-roadmap` | No | Learning roadmap generation |
| `POST` | `/api/insights-summary` | No | Full insights summary |
| `POST` | `/api/feedback` | No | Submit user feedback |
| `POST` | `/api/check-password` | No | Password strength checker |
| `GET` | `/api/csrf-token` | No | CSRF token endpoint |
| `GET` | `/healthz` | No | Health check |
| `POST` | `/logout` | Yes | User logout |
| `GET` | `/methodology` | No | ML methodology page |
| `GET` | `/privacy` | No | Privacy policy |
| `GET` | `/insights` | No | Platform insights |
| `GET` | `/partnerships` | No | Partnerships page |

## How It Works

### Layered analysis

Prayash uses resume evidence to identify a likely occupation, retrieve verified benchmark task labels when coverage exists, calculate contextual task-exposure shares, and recommend career-development actions. The historical occupation reference is an occupation-level index, not a personal employment probability. The E0/E1/E2 result describes contextual task exposure under the published GPTs-are-GPTs taxonomy; it is not a personal job-loss, unemployment, replacement, termination, or employment forecast. Optional local Ollama analysis explains verified results but does not calculate or modify them.

1. **Resume parsing and occupation matching** — TF-IDF similarity to job profiles and O\*NET clusters. Task labels use exact SOC, exact title, or an approved reviewed crosswalk only.
2. **Historical occupation reference** — Local Ridge model on `data/automation_risk.csv`. Shown as e.g. 62/100 — Moderate. Occupation-level only; not a validated personal employment probability. Legacy API fields `risk_score` / `risk_label` alias this reference.
3. **Verified E0/E1/E2 lookup** — Production retrieves published `human_labels` from the GPTs-are-GPTs benchmark (O\*NET 27.2 source; project O\*NET 31.0). Research model population is 923 occupations; product coverage is a selected 800 common occupations. The TF-IDF E0/E1/E2 classifier is **research-only** and is not the production label source.
4. **Career recommendations** — Skill gaps, courses, projects, RIASEC, and roadmaps from the deterministic pipeline.
5. **Optional Ollama** — Advanced mode explains verified JSON locally; it cannot change scores or labels.

### Dual-Mode Architecture

| Mode | Components | Latency |
|------|-----------|---------|
| **Standard** | Local scikit-learn model | < 100ms |
| **Advanced** | Local ML + Ollama Llama 3 narrative | 10–45s |

## Running Tests

```bash
# Install test dependencies
pip install pytest requests

# Run integration tests
pytest tests/test_app.py -v

# Run end-to-end auth tests (requires server running)
python test_auth_e2e.py
python test_forgot_password.py
```

## License

This project was developed as a Final Year Project by **Arpan, Umanga, and Samir**.
