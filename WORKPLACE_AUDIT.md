# Workplace Audit — AI-Based Career Risk & Reskilling Recommendation System

## 1. Project Map (current)

```
Final_year_project/
├── app.py                  # Flask app entry, registers routes, login, logging
├── config.py               # env-based config
├── extensions.py           # db / login_manager / csrf / socketio wiring
├── bootstrap.py            # startup bootstrap
├── models/                 # chat.py, profile.py, upload.py, __init__.py
├── routes/                 # api.py (95KB), auth.py, chat.py, pages.py, admin.py
├── services/               # ai_service, chat_service, resume_service, upload_service
├── templates/              # base.html, workspace.html (SPA w/ data-page sections), ...
├── static/                 # styles.css, script.js, career-chat.*, skill-extraction.*, ...
├── data/                   # csv/json datasets (onet, risk, resources)
├── ml_models/
├── resume_parser.py        # PyMuPDF/pdfplumber/pypdf2 extraction
├── risk_assessor.py        # career automation-risk model
├── personalized_roadmap.py # roadmap generation (113KB)
├── rag_retriever.py        # FAISS/sentence-transformers retrieval
├── llm_cooldown.py         # LLM rate-limit guard
└── tests/                  # 163 passing
```

## 2. Module Status

| Module | Frontend (workspace) | Backend/API | DB | Status |
|---|---|---|---|---|
| Dashboard | `data-page="dashboard"` | metrics from latest analysis | User/Upload | Working (real data) |
| Resume Analysis | `data-page="resume-analysis"` | `/api/upload`, `/api/analyze` | Upload | Working |
| Skill Extraction | `data-page="skill-extraction"` | skill service | Upload | Working |
| Skill Gap Analysis | `/workspace/skills-gap` + `data-page="skill-gap"` | `/api/skills-gap/*` | roles | Working |
| Career Risk | `data-page="career-risk"` | `/predict_risk` | Upload | Working |
| Job Matching | `data-page="job-matching"` | `/match_jobs` | Upload | Working |
| Career Path | `data-page="career-path"` | `/api/career-paths` | Upload | Working |
| Reskilling Roadmap | `data-page="reskilling"` | `/api/reskilling-roadmap`, `/api/roadmap-progress` | Roadmap | Working |
| Interview Preparation | `data-page="interview"` | chat/interview generation | — | Working (JS-driven) |
| AI Career Assistant | `data-page="ai-assistant"` | `/api/career-chat*` | Chat | Working |
| Reports | `data-page="reports"` | aggregates latest analysis | Upload | Partially (view/aggregation; download via `/api/export`) |
| History | `data-page="history"` | `/api/history` | Upload | Working |
| Profile | `data-page="profile"` | `/api/profile` | Profile | Working |
| Settings | `data-page="settings"` | linked-accounts, password | User | Working |
| Admin | `/admin` | `/api/admin/users` | User | Working |

## 3. Reference-repo useful ideas (not copied wholesale)

- SAHAY_AI: PyMuPDF-first extraction w/ pdfplumber+PyPDF2 fallback (already present in `resume_parser.py`), section detection, categorized skills, deterministic roadmap from skill gaps, resume-aware RAG assistant (FAISS already in `rag_retriever.py`), model caching (present via lazy singleton in ai_service/llm_cooldown).
- AI-Study-Assistant-Flask: global model init w/ caching, contextual QA, question generation (mapped to interview prep), text summarization, JSON responses, loading behavior.

## 4. Findings

- No compile errors; `pytest` = 163 passed; all 83 routes register.
- Placeholder cards in `workspace.html` (`is-placeholder`) are the intended empty states; they are populated by `script.js` after analysis.
- Minor: file-header comments show mojibake (`�?`) from encoding — cosmetic only.
- Minor: stale `flask_err.log` SyntaxError from Sep 25 is historical; `routes/api.py` compiles today.

## 5. Recommended incremental safe fixes

1. Replace `Query.get()` legacy calls with `db.session.get()` (deprecation warnings).
2. Keep secrets in `.env` (already); verify `SECRET_KEY`, OAuth, Gemini/HF keys are not committed.
3. Do NOT redesign the workspace; connect gaps incrementally (Reports download/regenerate already via `/api/export`).
