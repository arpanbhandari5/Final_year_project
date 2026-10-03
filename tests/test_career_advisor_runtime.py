"""Runtime verification for /career-advisor pipeline (temp DB, deleted after run).

Exercises the REAL Flask app, REAL ML artifacts, REAL endpoints via test client:
login -> page render -> upload/context extraction -> /api/upload analysis ->
score/risk/jobs/paths/roadmap -> skills-gap -> career-chat -> csrf contract.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile

# Allow running from any cwd: python tests/test_career_advisor_runtime.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Isolate the DB before importing the app (Config reads DATABASE_URL at import time)
_tmpdir = tempfile.mkdtemp(prefix="prayash_runtime_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ.setdefault("LLM_PROVIDER", "")  # force rule-based chat fallback determinism

RESUME_TEXT = """John Tester
Email: john.tester@example.com | Phone: +1 555 010 9987

EDUCATION
B.Tech Computer Science, Sample University, 2024

EXPERIENCE
Data Science Intern, Acme Corp (6 months)
- Built machine learning pipelines with Python, pandas and scikit-learn
- Created dashboards using SQL, PostgreSQL and Tableau

SKILLS
Python, Machine Learning, Deep Learning, SQL, PostgreSQL, Data Visualization,
TensorFlow, Git, Docker, Communication, Teamwork, Problem Solving

PROJECTS
Resume screening model with TensorFlow achieving 91% accuracy
Sales forecasting dashboard with pandas and PostgreSQL
"""

failures: list[str] = []
passes: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passes.append(name)
        print(f"  PASS  {name}")
    else:
        failures.append(f"{name} — {detail}")
        print(f"  FAIL  {name}  {detail}")


def main() -> int:
    print("== 1. App import + model artifacts ==")
    from app import app  # noqa: E402  (runs initialize_database on import)
    from storage import User, create_user, db  # noqa: E402

    from bootstrap import ensure_model_artifacts  # noqa: E402

    trained = ensure_model_artifacts()
    check("model artifacts available", os.path.isfile("ml_models/model.pkl"),
          "ml_models/model.pkl missing")
    print(f"  (bootstrap trained fresh: {trained})")

    with app.app_context():
        # init_database() seeds the demo user student@prayash.local / Student@123.
        # Ensure it's verified (fresh DBs get this from the seeder; older ones may not).
        user = db.session.query(User).filter_by(email="student@prayash.local").first()
        if not user:
            from storage import create_user

            create_user(email="student@prayash.local", password="Student@123",
                        full_name="Runtime Tester", username="student")
            user = db.session.query(User).filter_by(email="student@prayash.local").first()
        user.email_verified = True
        db.session.commit()

    c = app.test_client()

    print("== 2. Auth gate + page render ==")
    r = c.get("/career-advisor")
    check("anonymous /career-advisor redirects to login", r.status_code == 302,
          f"status={r.status_code}")

    # Login form is CSRF-protected: fetch the token from the rendered form first.
    import re as _re
    r = c.get("/login")
    m = _re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.get_data(as_text=True))
    login_csrf = m.group(1) if m else ""
    check("login form provides csrf token", bool(login_csrf), "no csrf_token input found")

    r = c.post("/login", data={
        "email": "student@prayash.local",
        "password": "Student@123",
        "csrf_token": login_csrf,
    }, follow_redirects=False)
    check("login succeeds", r.status_code in (200, 302), f"status={r.status_code}")

    r = c.get("/career-advisor")
    html = r.get_data(as_text=True)
    check("page renders 200", r.status_code == 200, f"status={r.status_code}")
    check("template key IDs present",
          all(x in html for x in ('id="resumeInput"', 'id="analyzeBtn"',
                                  'id="targetRole"', 'id="jobModal"', 'id="chatInput"')),
          "one or more key IDs missing")
    check("advisor JS/CSS wired", "career-advisor.js" in html and "career-advisor.css" in html,
          "asset tags missing")
    check("profile email populated", "student@prayash.local" in html,
          "current_user.email not rendered into profile")

    print("== 3. CSRF contract ==")
    csrf = None
    r = c.get("/api/csrf-token")
    if r.status_code == 200:
        csrf = r.get_json().get("csrf_token")
    check("csrf endpoint works", bool(csrf), f"status={r.status_code}")

    def post_json(url, payload, use_csrf=True):
        headers = {"X-CSRFToken": csrf} if use_csrf else {}
        return c.post(url, data=json.dumps(payload),
                      content_type="application/json", headers=headers)

    print("== 4. Text extraction path (as JS does for PDF/DOCX) ==")
    r = c.post("/api/career-chat/context", data={"file": (io.BytesIO(RESUME_TEXT.encode()), "resume.txt")},
               content_type="multipart/form-data", headers={"X-CSRFToken": csrf})
    body = r.get_json() or {}
    check("context extraction 200", r.status_code == 200, f"status={r.status_code} {body}")
    extracted = body.get("text", "")
    check("extracted text >= 20 chars", len(extracted) >= 20, f"len={len(extracted)}")
    check("extraction returns skills", body.get("skill_count", 0) > 0,
          f"skills={body.get('skills')}")

    print("== 5. /api/upload — full analysis (ML) ==")
    r = c.post("/api/upload", data={"resume_text": RESUME_TEXT, "mode": "standard"},
               content_type="multipart/form-data", headers={"X-CSRFToken": csrf})
    analysis = r.get_json() or {}
    check("analysis 200 + success", r.status_code == 200 and analysis.get("success"),
          f"status={r.status_code} err={analysis.get('error')}")
    risk_score = analysis.get("risk_score")
    check("risk_score is real 0..1", isinstance(risk_score, (int, float)) and 0 <= risk_score <= 1,
          f"risk_score={risk_score}")
    check("risk_label present", analysis.get("risk_label") in ("Low", "Moderate", "Elevated"),
          f"got {analysis.get('risk_label')}")
    top_roles = analysis.get("top_roles") or []
    check("top_roles non-empty with job_role", bool(top_roles) and "job_role" in top_roles[0],
          f"roles={len(top_roles)}")
    skills = (analysis.get("skills") or {}).get("all_skills") or []
    check("skills extracted", len(skills) >= 5, f"n={len(skills)}: {skills[:8]}")
    check("skills categorized", bool((analysis.get("skills") or {}).get("by_category")),
          "by_category empty")

    print("== 6. /score_resume ==")
    r = post_json("/score_resume", {"resume_text": RESUME_TEXT})
    body = r.get_json() or {}
    result = body.get("result") or {}
    check("score 200", r.status_code == 200 and body.get("success"), f"{body.get('error')}")
    check("final_score 0..100",
          isinstance(result.get("final_score"), int) and 0 <= result["final_score"] <= 100,
          f"final={result.get('final_score')}")
    check("sub-scores present",
          all(k in result for k in ("skill_score", "experience_score", "quality_score")),
          f"keys={list(result.keys())[:8]}")
    check("feedback non-empty", bool(result.get("feedback")), "no feedback")

    print("== 7. /predict_risk ==")
    r = post_json("/predict_risk", {"resume_text": RESUME_TEXT})
    body = r.get_json() or {}
    check("risk 200", r.status_code == 200 and body.get("success"), f"{body.get('error')}")
    check("risk fields", all(k in body for k in ("risk_level", "risk_score", "explanation")),
          f"keys={list(body.keys())}")

    print("== 8. /match_jobs ==")
    r = post_json("/match_jobs", {"resume_text": RESUME_TEXT})
    body = r.get_json() or {}
    jobs = body.get("jobs") or []
    check("jobs 200", r.status_code == 200 and body.get("success"), f"{body.get('error')}")
    check("jobs returned", len(jobs) > 0, f"n={len(jobs)}")
    if jobs:
        j = jobs[0]
        check("job fields map to card renderer",
              all(k in j for k in ("title", "score", "risk_level", "industry")),
              f"keys={list(j.keys())}")
        check("job score 0..100", 0 <= (j.get("score") or 0) <= 100, f"score={j.get('score')}")

    print("== 9. /api/career-paths + /api/learning-roadmap ==")
    r = post_json("/api/career-paths", {"resume_text": RESUME_TEXT})
    body = r.get_json() or {}
    paths = body.get("paths") or []
    check("career-paths 200", r.status_code == 200, f"status={r.status_code} {body.get('error')}")
    check("paths have role/skills_needed", bool(paths) and "role" in paths[0]
          and "skills_needed" in paths[0], f"keys={list(paths[0].keys()) if paths else 'none'}")

    r = post_json("/api/learning-roadmap", {"resume_text": RESUME_TEXT})
    body = r.get_json() or {}
    roadmap = body.get("roadmap") or []
    check("roadmap 200", r.status_code == 200, f"status={r.status_code} {body.get('error')}")
    check("roadmap areas with stages", bool(roadmap) and "stages" in roadmap[0]
          and len(roadmap[0]["stages"]) == 3, f"areas={len(roadmap)}")

    print("== 10. skills-gap: roles + analyze ==")
    r = c.get("/api/skills-gap/roles")
    body = r.get_json() or {}
    roles = body.get("roles") or []
    check("roles endpoint works", r.status_code == 200 and len(roles) > 0,
          f"status={r.status_code} n={len(roles)}")
    target = roles[0]
    r = post_json("/api/skills-gap/analyze", {"resume_text": RESUME_TEXT, "target_role": target})
    body = r.get_json() or {}
    gap = body.get("analysis") or {}
    check("gap analyze 200", r.status_code == 200 and body.get("success"),
          f"status={r.status_code} {body.get('error')}")
    check("gap has match_percentage (numeric)",
          isinstance(gap.get("match_percentage"), (int, float)),
          f"got {gap.get('match_percentage')!r}")
    check("gap recommendations carry resources",
          bool(gap.get("recommendations")) and "resources" in gap["recommendations"][0],
          "no learning resources in recommendations")
    print(f"  (target role used: {target!r}, match={gap.get('match_percentage')}%)")

    print("== 11. /api/career-chat (rule-based fallback path) ==")
    r = post_json("/api/career-chat", {"message": "What skills am I missing?",
                                       "session_id": "", "resume_text": RESUME_TEXT})
    body = r.get_json() or {}
    check("chat 200", r.status_code == 200 and body.get("success"),
          f"status={r.status_code} {body.get('error')}")
    check("reply non-empty", bool(body.get("reply")), "empty reply")
    check("session_id returned", bool(body.get("session_id")), "no session id")
    check("llm_powered flag present", "llm_powered" in body, "flag missing")

    print("== 12. CSRF enforcement (negative test) ==")
    r = post_json("/predict_risk", {"resume_text": RESUME_TEXT}, use_csrf=False)
    check("POST without CSRF rejected", r.status_code in (400, 403),
          f"status={r.status_code}")

    print("== 13. Frontend contract: every $() id exists on the page ==")
    import re
    js_path = os.path.join("static", "career-advisor.js")
    with open(js_path, encoding="utf-8") as f:
        js = f.read()
    ids = {m for m in re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", js)}
    missing = [i for i in sorted(ids) if f'id="{i}"' not in html]
    check("all JS-referenced IDs rendered", not missing, f"missing={missing}")

    print()
    print(f"RESULT: {len(passes)} passed, {len(failures)} failed")
    if failures:
        print("\nFAILURES:")
        for f_ in failures:
            print(f"  - {f_}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
