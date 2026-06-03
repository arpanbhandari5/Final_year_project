# AI-Based Career and Skill

This repository contains a Flask-based application for career assessment and skill recommendation using resume parsing, risk analysis, and machine learning models.

## Project Structure

- `app.py` — main Flask application entry point
- `bootstrap.py` — app initialization helpers
- `evaluation.py` — evaluation routines
- `risk_assessor.py` — risk assessment logic
- `resume_parser.py` — resume parsing utilities
- `train_model.py` — model training scripts
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

## Notes

- The `.env` file is intentionally excluded from version control.
- The repository contains preprocessed datasets and model files under `data/` and `ml_models/`.
