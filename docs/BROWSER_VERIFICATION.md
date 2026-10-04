# Browser verification log

Live workflow against `http://127.0.0.1:5000` with CSRF **enabled**. Playwright Chromium; no retraining; 248-row files not moved.

Command (must execute, not skip):

```
pytest -q tests/test_browser_resume_workflow.py --run-browser -rs
```

Result of that run: **1 passed** (not skipped).

## Status

```
Browser verification:
PASS (executed; see BLOCKED rows)

Server:
http://127.0.0.1:5000

CSRF:
enabled — PASS (POST /api/upload without token returned 400; UI uploads with X-CSRFToken succeeded)

PDF upload:
PASS

DOCX upload:
PASS

Covered occupation:
PASS (verified published lookup; labels matched stored CSV for the resolved SOC)

Match method:
exact_code

Matched occupation code:
53-7121.00 (Tank Car, Truck, and Ship Loaders)

Note:
The fixture title “Chief Executives” did not win. Production precedence is exact cluster SOC before exact title. The first O*NET cluster SOC was 53-7121.00, which is in the 800 product subset.

800-subset membership:
PASS

Historical reference:
PASS (occupation-level N/100 band; disclaimer present; no personal job-loss wording)

E0/E1/E2 lookup:
PASS (source_type published_benchmark_lookup)

Distribution denominator:
PASS (occupation-wide shares match labelled-task counts in the public benchmark CSV)

Unresolved occupation:
BLOCKED — cluster exact_code still matched a benchmark SOC for a non-occupational resume. Title-only unresolved is not reachable while clusters always expose a valid SOC.

Invalid upload:
PASS (empty.txt → unsuccessful analysis / error UI)

Oversized upload:
PASS (over 8 MB rejected; no successful analysis)

Prompt injection:
PASS (published distribution unchanged; prohibited job-loss claims not shown as model output)

Ollama disabled:
PASS (Standard mode)

Ollama enabled:
BLOCKED — local Ollama model unavailable (probe of localhost:11434 failed)

Ollama unavailable fallback:
PASS (Advanced still returned deterministic verified lookup; Flask log: ConnectionError)

Safe rendering:
PASS (layered HTML had no injected <img>; narrative used textContent path)

248-row data integrity:
PASS (SHA-256 of task_exposure_training.csv and final_validated_task_training_table.csv unchanged)

Retraining:
NO

Dataset movement:
NO

Git commit/push:
NO
```

## Manual visual checklist

- Layout of Historical occupation reference / E0/E1/E2: exercised in headless Chromium DOM text (PASS).
- Live Ollama narrative quality: **not done** — model not running (BLOCKED).
- CSRF: automated (PASS).
- 248-row isolation: file hashes, not the browser (PASS).

## How to re-run

1. `python app.py` (do not set `WTF_CSRF_ENABLED=False`).
2. `pytest -q tests/test_browser_resume_workflow.py --run-browser -rs`
3. If Ollama is running with `llama3`, Advanced should change `ollama_enabled` from BLOCKED to PASS.
