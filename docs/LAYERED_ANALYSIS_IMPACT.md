# Layered analysis impact (read-only audit)

This note lists production surfaces touched by the in-place layered-analysis upgrade. It is not a research claim.

## Backend modules

- `app.py` — `/api/analyze`, `/api/analyze-stream`, `/api/upload`, `/api/compare`, `/api/insights-summary`, report workflow copy
- `risk_assessor.py` — historical Ridge score, occupation/title matching, Ollama narrative, `analyze_resume`
- `task_exposure_assessor.py` — **new**; published E0/E1/E2 retrieval only
- `resume_parser.py` — unchanged resume parse/skills
- `train_model.py` / `evaluation.py` / `ml_models/model.pkl` — **not replaced**
- `data/automation_risk.csv` — **not modified**

## API endpoints

- `/api/analyze` and stream/upload: add `historical_occupation_reference`, `task_exposure`, `occupation_match`, `career_development`, `ollama`; keep legacy `risk_score` / `risk_label`
- `/api/compare`: keep `risk_delta` as historical-reference difference; add task-exposure fields
- `/api/insights-summary`: add layered fields without removing existing skills/quality payload

## Templates / JavaScript

- `templates/index.html`, `report.html`, `methodology.html`
- `static/script.js` (loaded by `base.html`); `static/script.ts` kept in sync for wording

## Database

- `storage.Upload.risk_score` / `risk_label` remain metadata columns (historical reference), not personal job-loss probability

## Old user-facing risk terminology

Dashboard “Risk Score %”, modal “Automation risk”, report “Automation Risk Assessment”, compare “Risk %”

## Ollama call sites

- `risk_assessor._ollama_narrative` only (advanced mode). Career chat stays separate.

## Tests that must remain passing

- `tests/test_app.py` analysis + SSE
- `tests/test_ai_narrative.py` Ollama fail-closed
- `tests/test_overhaul.py` Ollama unavailable
