# Prayash

**Learning for better future** — An AI-powered career intelligence platform that turns resumes into actionable learning strategies.

## Overview

Prayash combines local machine learning, O\*NET occupational intelligence, and an optional Llama 3 narrative layer to analyze resumes and provide:

- **Automation Risk Scoring** — Predicts how susceptible a career profile is to automation using a local Ridge regression model trained on O\*NET data.
- **Role Matching** — Maps resumes to the closest O\*NET job profiles using TF-IDF cosine similarity.
- **Skill Clustering** — Groups skills into meaningful competency clusters for targeted upskilling.
- **Learning Roadmap** — Recommends Coursera courses aligned to the strongest skill intersections in the resume.
- **RIASEC Personality Profiling** — Derives a Holland Code (RIASEC) profile from resume content and O\*NET interest data.
- **Cognitive Career Narrative** — In Advanced mode, generates a structured career narrative using a local Llama 3 model via Ollama.

### Privacy-First Design

Resume data is **never** written to a permanent database. Files are read, analyzed in memory, and discarded after response generation. The SQLite database only stores anonymized metadata (filename, mode, risk score) for admin analytics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Flask 3.x, Flask-Login, Flask-SQLAlchemy |
| **ML Pipeline** | scikit-learn (Ridge regression, TF-IDF vectorizer) |
| **Data** | O\*NET occupation profiles, automation risk dataset, Coursera course catalog |
| **Resume Parsing** | pypdf (PDF), python-docx (DOCX), plain text |
| **LLM (optional)** | Ollama with Llama 3 for advanced narrative generation |
| **Database** | SQLite (metadata only) |
| **Frontend** | Vanilla HTML/CSS/JS with Inter font, glassmorphism UI |

## Project Structure

```
Final_year_project/
├── app.py                 # Flask application entry point & routes
├── bootstrap.py           # Model artifact initialization
├── risk_assessor.py       # Core ML pipeline: risk scoring, role matching, RIASEC, roadmap
├── resume_parser.py       # PDF/DOCX/text resume extraction
├── storage.py             # SQLAlchemy models, auth, database helpers
├── evaluation.py          # Model evaluation & cross-validation scripts
├── train_model.py         # Trains and serializes ML artifacts (model.pkl, courses.pkl)
├── requirements.txt       # Python dependencies
├── setup.ps1              # Windows PowerShell setup script
├── data/
│   ├── automation_risk.csv       # O*NET automation risk scores
│   ├── coursera_catalog.csv      # Coursera course recommendations
│   ├── onet_interests.csv        # O*NET interest profiles
│   ├── onet_interest_keywords.csv
│   ├── onet_skils.csv            # O*NET skill mappings
│   └── resume_corpus.csv         # Resume training corpus
├── ml_models/              # Generated after training (gitignored)
│   ├── model.pkl           # Trained Ridge model + vectorizer + job vectors
│   └── courses.pkl         # Skill-to-course mapping index
├── templates/
│   ├── base.html           # Base layout with navbar & footer
│   ├── index.html          # Landing page with dual-mode dashboard
│   ├── workspace.html      # Authenticated analysis workspace
│   ├── login.html / signup.html
│   ├── admin.html          # Admin analytics dashboard
│   ├── methodology.html    # ML methodology documentation
│   ├── privacy.html        # Privacy policy
│   ├── insights.html       # Platform insights
│   └── partnerships.html   # Partnership information
├── static/
│   ├── styles.css          # Full stylesheet (glassmorphism, animations)
│   ├── script.js           # Client-side interactions & API calls
│   └── script.ts           # TypeScript source (if applicable)
└── prayash.db              # SQLite database (auto-created)
```

## Getting Started

### Prerequisites

- **Python 3.11+**
- **pip** (Python package manager)
- **Ollama** (optional, for Advanced mode narratives)

### Installation

1. **Clone the repository** and navigate to the project directory:

   ```bash
   cd Final_year_project
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Train the ML model** (auto-runs on first request if not present):

   ```bash
   python train_model.py
   ```

   This generates `ml_models/model.pkl` and `ml_models/courses.pkl` from the training data.

4. **Run the application:**

   ```bash
   python app.py
   ```

   The server starts at **http://127.0.0.1:5000**.

### Windows Quick Setup

```powershell
.\setup.ps1
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | `prayash-local-development-secret` | Flask session secret |
| `DATABASE_URL` | `sqlite:///prayash.db` | SQLAlchemy database URI |
| `ADMIN_EMAIL` | `admin@prayash.local` | Default admin account email |
| `ADMIN_PASSWORD` | `prayash-admin` | Default admin account password |
| `PORT` | `5000` | Server port |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint (Advanced mode) |
| `OLLAMA_MODEL` | `llama3` | Ollama model name (Advanced mode) |

## Usage

1. **Sign up** for a new account or log in with the default student account (`student` / `student`).
2. Navigate to the **Workspace** page.
3. **Upload a resume** (PDF, DOCX) or **paste resume text** into the text area.
4. Choose a mode:
   - **Standard** — Uses local ML only (Ridge regression + TF-IDF similarity).
   - **Advanced** — Adds Llama 3 cognitive narrative via Ollama (requires Ollama running locally).
5. Click **Run analysis** to see:
   - Automation risk score and risk band
   - Top matching O\*NET job roles
   - Skill competency clusters
   - Personalized learning roadmap with Coursera courses
   - RIASEC personality fit profile

## Default Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@prayash.local` | `prayash-admin` |
| Student | `student` | `student` |

## How It Works

### ML Pipeline

1. **Vectorization** — Resume text is converted to TF-IDF features using a vocabulary trained on O\*NET job descriptions and the resume corpus.
2. **Risk Prediction** — A Ridge regression model predicts an automation risk score (0.0–1.0) from the TF-IDF vector.
3. **Role Matching** — Cosine similarity between the resume vector and pre-computed job vectors identifies the closest O\*NET occupations.
4. **Skill Clustering** — The resume is matched against O\*NET skill cluster profiles for competency grouping.
5. **Course Recommendation** — A skill-to-course index maps detected skills to relevant Coursera courses.
6. **RIASEC Profiling** — Keyword analysis combined with O\*NET interest cluster scores produces a Holland Code profile.

### Dual-Mode Architecture

| Mode | Components | Latency |
|------|-----------|---------|
| **Standard** | Local scikit-learn model | < 100ms |
| **Advanced** | Local ML + Ollama Llama 3 narrative | 10–45s |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Landing page |
| `GET/POST` | `/login` | Login form |
| `GET/POST` | `/signup` | Registration form |
| `GET` | `/workspace` | Analysis workspace (auth required) |
| `POST` | `/api/upload` | Submit resume for analysis |
| `POST` | `/api/analyze` | Alias for `/api/upload` |
| `POST` | `/api/feedback` | Submit user feedback |
| `GET` | `/admin` | Admin dashboard (admin only) |
| `POST` | `/admin/logout` | Admin logout |
| `POST` | `/logout` | User logout |
| `GET` | `/healthz` | Health check |
| `GET` | `/methodology` | ML methodology page |
| `GET` | `/privacy` | Privacy policy page |
| `GET` | `/insights` | Platform insights page |
| `GET` | `/partnerships` | Partnerships page |

## Model Evaluation

Run the evaluation script to reproduce 5-fold cross-validation metrics:

```bash
python evaluation.py
```

This reports MAE, RMSE, and R² on the automation risk prediction task.

## Credits

**Team:** Samir, Umanga and Arpan

## License

This project was developed as a Final Year Project. See the repository for license details.
