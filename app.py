from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import requests
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from bootstrap import ensure_model_artifacts
from risk_assessor import analyze_resume as assess_resume
from resume_parser import extract_resume_text as parse_resume_file
from storage import User, authenticate_user, create_user, dashboard_metrics, get_user_by_email, init_database, record_feedback, record_upload

try:
    from docx import Document
except Exception:  # pragma: no cover - optional dependency during bootstrap
    Document = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency during bootstrap
    PdfReader = None


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "ml_models"
MODEL_PATH = MODEL_DIR / "model.pkl"
COURSES_PATH = MODEL_DIR / "courses.pkl"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "prayash-local-development-secret"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'prayash.db').as_posix()}"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


@login_manager.unauthorized_handler
def unauthorized_handler():
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Authentication required."}), 401
    return redirect(url_for("login", next=request.path))


def initialize_database() -> None:
    init_database(app)


initialize_database()


def _safe_load_bundle() -> dict[str, Any]:
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return {}


def _safe_load_courses() -> dict[str, list[dict[str, Any]]]:
    if COURSES_PATH.exists():
        return joblib.load(COURSES_PATH)
    return {}


@lru_cache(maxsize=1)
def load_artifacts() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    return _safe_load_bundle(), _safe_load_courses()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return "" if text.lower() == "nan" else text


def extract_resume_text(uploaded_file) -> str:
    filename = (uploaded_file.filename or "").lower()
    payload = uploaded_file.read()
    uploaded_file.stream.seek(0)

    if filename.endswith(".pdf") and PdfReader is not None:
        reader = PdfReader(BytesIO(payload))
        pages = [page.extract_text() or "" for page in reader.pages]
        return _clean_text(" ".join(pages))

    if filename.endswith(".docx") and Document is not None:
        document = Document(BytesIO(payload))
        return _clean_text(" ".join(paragraph.text for paragraph in document.paragraphs))

    if filename.endswith(".txt"):
        return _clean_text(payload.decode("utf-8", errors="ignore"))

    return _clean_text(payload.decode("utf-8", errors="ignore"))


def _split_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text.lower())
    stop_words = {
        "with",
        "from",
        "that",
        "this",
        "your",
        "have",
        "will",
        "into",
        "about",
        "for",
        "and",
        "the",
        "are",
        "our",
        "you",
        "role",
        "work",
        "team",
        "data",
        "skills",
        "career",
        "resume",
    }
    return [token for token in tokens if token not in stop_words]


def _format_top_skills(keywords: list[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for keyword in keywords:
        normalized = keyword.replace("_", " ").strip().title()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
        if len(output) >= limit:
            break
    return output


def _load_career_model() -> dict[str, Any]:
    bundle, courses = load_artifacts()
    if not bundle:
        raise RuntimeError("Model artifacts are missing. Run train_model.py first.")
    bundle = dict(bundle)
    bundle["courses"] = courses
    return bundle


def _score_risk(model_bundle: dict[str, Any], resume_text: str) -> float:
    vectorizer = model_bundle.get("vectorizer")
    risk_model = model_bundle.get("risk_model")
    if vectorizer is None or risk_model is None:
        return 0.5
    vector = vectorizer.transform([resume_text])
    raw_score = float(risk_model.predict(vector)[0])
    return float(np.clip(raw_score, 0.0, 1.0))


def _top_matches(model_bundle: dict[str, Any], resume_text: str, limit: int = 5) -> list[dict[str, Any]]:
    vectorizer = model_bundle.get("vectorizer")
    job_vectors = model_bundle.get("job_vectors")
    job_profiles = model_bundle.get("job_profiles", [])
    if vectorizer is None or job_vectors is None or not job_profiles:
        return []

    resume_vector = vectorizer.transform([resume_text])
    similarities = (job_vectors @ resume_vector.T).toarray().ravel()
    ranked_indices = np.argsort(similarities)[::-1][:limit]

    matches: list[dict[str, Any]] = []
    for index in ranked_indices:
        profile = dict(job_profiles[index])
        profile["similarity"] = float(similarities[index])
        matches.append(profile)
    return matches


def _skill_clusters(model_bundle: dict[str, Any], resume_text: str, limit: int = 4) -> list[dict[str, Any]]:
    vectorizer = model_bundle.get("vectorizer")
    cluster_vectors = model_bundle.get("cluster_vectors")
    cluster_profiles = model_bundle.get("cluster_profiles", [])
    if vectorizer is None or cluster_vectors is None or not cluster_profiles:
        return []

    resume_vector = vectorizer.transform([resume_text])
    similarities = (cluster_vectors @ resume_vector.T).toarray().ravel()
    ranked_indices = np.argsort(similarities)[::-1][:limit]

    clusters: list[dict[str, Any]] = []
    for index in ranked_indices:
        profile = dict(cluster_profiles[index])
        profile["similarity"] = float(similarities[index])
        clusters.append(profile)
    return clusters


def _generate_roadmap(model_bundle: dict[str, Any], resume_text: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    courses_index = model_bundle.get("courses", {})
    keywords = _format_top_skills(_split_keywords(resume_text), limit=12)
    roadmap: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for match in matches[:3]:
        for skill in match.get("skills", [])[:4]:
            normalized_skill = str(skill).strip().lower()
            for course in courses_index.get(normalized_skill, []):
                title = course.get("title") or course.get("Course Title") or course.get("Course")
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                roadmap.append(
                    {
                        "skill": skill,
                        "course": title,
                        "url": course.get("url") or course.get("Course URL") or course.get("URL"),
                        "reason": course.get("short_intro") or course.get("Course Short Intro") or course.get("What you learn") or "Aligned course recommendation",
                    }
                )
                if len(roadmap) >= 6:
                    return roadmap

    for keyword in keywords:
        for course in courses_index.get(keyword.lower(), []):
            title = course.get("title") or course.get("Course Title") or course.get("Course")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            roadmap.append(
                {
                    "skill": keyword,
                    "course": title,
                    "url": course.get("url") or course.get("Course URL") or course.get("URL"),
                    "reason": course.get("short_intro") or course.get("Course Short Intro") or course.get("What you learn") or "Aligned course recommendation",
                }
            )
            if len(roadmap) >= 6:
                return roadmap

    return roadmap


def _riasec_profile(clusters: list[dict[str, Any]], resume_text: str) -> dict[str, Any]:
    keyword_weights = {
        "Realistic": ["build", "maintain", "repair", "hands-on", "equipment", "physical", "operations"],
        "Investigative": ["analyze", "research", "model", "data", "ml", "python", "science", "sql", "statistics"],
        "Artistic": ["design", "creative", "visual", "ux", "story", "content", "brand"],
        "Social": ["support", "coach", "guide", "collaborat", "communication", "help", "training"],
        "Enterprising": ["lead", "influence", "business", "stakeholder", "sales", "strategy", "partnership"],
        "Conventional": ["process", "documentation", "organize", "compliance", "report", "workflow", "detail"],
    }

    scores = {key: 0.0 for key in keyword_weights}
    normalized_resume = resume_text.lower()

    for name, keywords in keyword_weights.items():
        for keyword in keywords:
            if keyword in normalized_resume:
                scores[name] += 1.0

    for cluster in clusters[:2]:
        for interest in cluster.get("interests", []):
            interest_name = str(interest).split("|")[0].strip()
            if interest_name in scores:
                scores[interest_name] += float(cluster.get("similarity", 0.0)) * 3.0

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return {
        "primary": ordered[0][0],
        "secondary": ordered[1][0],
        "tertiary": ordered[2][0],
        "scores": {name: round(score, 3) for name, score in ordered},
    }


def _ollama_narrative(resume_text: str, analysis: dict[str, Any]) -> str | None:
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model_name = os.environ.get("OLLAMA_MODEL", "llama3")
    prompt = f"""
You are generating a concise career intelligence narrative for Prayash.

Resume:
{resume_text}

Local ML risk score: {analysis['risk_score']:.2f}
Top matching roles: {json.dumps(analysis['top_roles'], ensure_ascii=False)}
RIASEC fit: {json.dumps(analysis['riasec'], ensure_ascii=False)}
Recommended learning roadmap: {json.dumps(analysis['roadmap'], ensure_ascii=False)}

Return a short structured response with two sections:
1. Cognitive Career Narrative
2. RIASEC Personality Fit
Keep it specific, actionable, and suitable for an executive dashboard.
""".strip()

    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.25}},
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response")
    except Exception:
        return None


def analyze_resume(resume_text: str, mode: str = "standard") -> dict[str, Any]:
    model_bundle = _load_career_model()
    cleaned_resume = _clean_text(resume_text)
    if not cleaned_resume:
        raise ValueError("Resume text is required.")

    risk_score = _score_risk(model_bundle, cleaned_resume)
    top_roles = _top_matches(model_bundle, cleaned_resume)
    clusters = _skill_clusters(model_bundle, cleaned_resume)
    roadmap = _generate_roadmap(model_bundle, cleaned_resume, top_roles)
    riasec = _riasec_profile(clusters, cleaned_resume)

    analysis: dict[str, Any] = {
        "mode": mode,
        "risk_score": round(risk_score, 3),
        "risk_label": "Low" if risk_score < 0.35 else "Moderate" if risk_score < 0.7 else "Elevated",
        "top_roles": top_roles,
        "skill_clusters": clusters,
        "roadmap": roadmap,
        "riasec": riasec,
        "privacy": {
            "storage": "Ephemeral only",
            "resume_persistence": False,
            "database_written": False,
        },
    }

    if mode == "advanced":
        narrative = _ollama_narrative(cleaned_resume, analysis)
        if narrative:
            analysis["cognitive_career_narrative"] = narrative
        else:
            analysis["cognitive_career_narrative"] = (
                f"The resume shows strongest alignment with {top_roles[0]['job_role'] if top_roles else 'knowledge work'} roles. "
                f"Local ML places the candidate in the {analysis['risk_label'].lower()} automation band."
            )
    else:
        analysis["cognitive_career_narrative"] = (
            f"Local ML identifies a {analysis['risk_label'].lower()} automation risk profile with immediate room to sharpen adjacent skills."
        )

    return analysis


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "site_name": "Prayash",
        "site_tagline": "Learning for better future",
        "is_authenticated": bool(current_user.is_authenticated),
        "admin_authenticated": bool(current_user.is_authenticated and getattr(current_user, "is_admin_email", False)),
    }


@app.get("/")
def index() -> str:
    return render_template("index.html", active_page="home", title="Prayash: Learning for better future")


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    error = None
    next_url = request.args.get("next") or request.form.get("next") or url_for("workspace")

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = authenticate_user(email, password)
        if user:
            login_user(user, remember=True)
            return redirect(next_url)
        error = "Invalid email or password."

    return render_template("login.html", active_page="login", title="Login | Prayash", error=error, next_url=next_url)


@app.route("/signup", methods=["GET", "POST"])
def signup() -> str:
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not email or "@" not in email:
            error = "Enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif get_user_by_email(email):
            error = "Email already exists. Please log in."
        else:
            user = create_user(email=email, password=password, role="student")
            login_user(user, remember=True)
            return redirect(url_for("workspace"))

    return render_template("signup.html", active_page="signup", title="Sign Up | Prayash", error=error)


@app.post("/logout")
@login_required
def logout() -> Any:
    logout_user()
    return redirect(url_for("index"))


@app.get("/workspace")
@login_required
def workspace() -> str:
    return render_template("workspace.html", active_page="workspace", title="Workspace | Prayash")


@app.get("/methodology")
def methodology() -> str:
    return render_template("methodology.html", active_page="methodology", title="Methodology | Prayash")


@app.get("/privacy")
def privacy() -> str:
    return render_template("privacy.html", active_page="privacy", title="Privacy | Prayash")


@app.get("/insights")
def insights() -> str:
    return render_template("insights.html", active_page="insights", title="Insights | Prayash")


@app.get("/partnerships")
def partnerships() -> str:
    return render_template("partnerships.html", active_page="partnerships", title="Partnerships | Prayash")


@app.route("/admin", methods=["GET"])
@login_required
def admin_dashboard() -> str:
    if not getattr(current_user, "is_admin_email", False):
        return redirect(url_for("workspace"))

    metrics = dashboard_metrics()
    chart_data = {
        "modeLabels": ["Standard", "Advanced"],
        "modeValues": [metrics["mode_counts"]["standard"], metrics["mode_counts"]["advanced"]],
        "riskLabels": ["Low", "Moderate", "Elevated"],
        "riskValues": [metrics["risk_buckets"]["low"], metrics["risk_buckets"]["moderate"], metrics["risk_buckets"]["elevated"]],
    }
    return render_template(
        "admin.html",
        title="Admin | Prayash",
        active_page="admin",
        metrics=metrics,
        chart_data=chart_data,
    )


@app.post("/admin/logout")
@login_required
def admin_logout() -> Any:
    logout_user()
    return redirect(url_for("login"))


@app.get("/healthz")
def healthz() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.post("/api/feedback")
def api_feedback():
    payload = request.get_json(silent=True) if request.is_json else {}
    message = (request.form.get("message") or (payload or {}).get("message", "")).strip()
    rating_raw = request.form.get("rating") or (payload or {}).get("rating")
    upload_id_raw = request.form.get("upload_id") or (payload or {}).get("upload_id")
    if not message:
        return jsonify({"success": False, "error": "Feedback message is required."}), 400

    rating = None
    upload_id = None
    try:
        rating = int(rating_raw) if rating_raw is not None and rating_raw != "" else None
    except Exception:
        rating = None
    try:
        upload_id = int(upload_id_raw) if upload_id_raw is not None and upload_id_raw != "" else None
    except Exception:
        upload_id = None

    feedback = record_feedback(message=message, rating=rating, upload_id=upload_id, user_id=current_user.id if current_user.is_authenticated else None)
    if feedback is None:
        return jsonify({"success": False, "error": "Could not store feedback."}), 500
    return jsonify({"success": True})


def _build_support_resources() -> list[dict[str, str]]:
    return [
        {
            "title": "Learning resources",
            "description": "Use roadmap suggestions to strengthen high-impact skills in the next 2 to 6 weeks.",
            "link": url_for("methodology"),
            "cta": "Explore methodology",
        },
        {
            "title": "Job search help",
            "description": "Use top role matches as search keywords for alerts, applications, and profile updates.",
            "link": url_for("insights"),
            "cta": "Open insights",
        },
        {
            "title": "Education and training",
            "description": "Compare short certificates and longer pathways for your target roles.",
            "link": url_for("partnerships"),
            "cta": "See partnerships",
        },
        {
            "title": "Support and privacy",
            "description": "Review how your data is handled and where to get additional guidance.",
            "link": url_for("privacy"),
            "cta": "Read privacy details",
        },
    ]


def _build_guided_next_steps(analysis: dict[str, Any]) -> dict[str, list[str]]:
    top_roles = analysis.get("top_roles") or []
    roadmap = analysis.get("roadmap") or []
    risk_label = str(analysis.get("risk_label") or "Moderate")

    role_names = [str(role.get("job_role") or "").strip() for role in top_roles if role.get("job_role")]
    primary_roles = [name for name in role_names if name][:2]

    learning_actions: list[str] = []
    for item in roadmap[:3]:
        course = str(item.get("course") or "").strip()
        skill = str(item.get("skill") or "core skill").strip()
        if course:
            learning_actions.append(f"Start '{course}' and focus on {skill} this week.")

    if not learning_actions:
        learning_actions.append("Pick one high-impact skill gap and schedule three focused practice sessions this week.")

    job_search_actions: list[str] = []
    if primary_roles:
        for role_name in primary_roles:
            job_search_actions.append(f"Save 10 recent postings for {role_name} and track repeated requirements.")
        job_search_actions.append("Update your resume summary using keywords from your strongest role matches.")
    else:
        job_search_actions.extend(
            [
                "Collect 10 postings in your target field and list repeated skills.",
                "Tailor your resume headline for one target role before applying.",
            ]
        )

    education_actions = [
        "Compare one short certificate and one longer credential for your target direction.",
        "Set a realistic 4, 8, or 12-week timeline and add deadlines to your calendar.",
    ]
    if risk_label.lower() == "elevated":
        education_actions.insert(0, "Prioritize transferable digital and analytical skills to reduce automation exposure.")
    elif risk_label.lower() == "low":
        education_actions.insert(0, "Deepen specialization in your strongest areas to preserve your low-risk profile.")
    else:
        education_actions.insert(0, "Build adjacent skills that improve resilience and role flexibility.")

    support_resources = [
        "Review the methodology page to understand how scores and role matches are produced.",
        "Review the privacy page for clear data handling details.",
        "Use advanced mode when you want additional narrative guidance.",
    ]

    return {
        "learning_actions": learning_actions,
        "job_search_actions": job_search_actions,
        "education_training_actions": education_actions,
        "support_resources": support_resources,
    }


def _build_report_guide(analysis: dict[str, Any]) -> dict[str, list[str]]:
    risk_label = str(analysis.get("risk_label") or "Moderate")
    mode = str(analysis.get("mode") or "standard")

    return {
        "how_this_works": [
            "Upload or paste your resume.",
            "Prayash runs local ML scoring for risk, role match, roadmap, and RIASEC fit.",
            "Advanced mode adds optional narrative guidance while preserving core ML outputs.",
        ],
        "what_your_report_means": [
            f"Your current automation band is {risk_label}.",
            "Top role matches show where your profile aligns today.",
            "Roadmap items suggest practical learning moves based on detected skills.",
        ],
        "what_to_do_next": [
            "Choose 1 to 2 actions and complete them in the next 14 days.",
            "Apply to roles that overlap with your strongest matches.",
            f"Re-run your report after updates, using {mode} mode as your baseline.",
        ],
        "need_help": [
            "Use the methodology page for model logic and assumptions.",
            "Use the privacy page for data handling details.",
            "Share feedback after your run so recommendations can improve over time.",
        ],
    }


def _handle_upload_request():
    payload = request.get_json(silent=True) if request.is_json else {}
    resume_text = request.form.get("resume_text") or (payload or {}).get("resume_text", "")
    mode = request.form.get("mode") or (payload or {}).get("mode", "standard")
    uploaded_file = request.files.get("resume_file")

    if uploaded_file and uploaded_file.filename:
        resume_text = parse_resume_file(uploaded_file)

    resume_text = _clean_text(resume_text)
    mode = _clean_text(mode).lower() or "standard"

    if not resume_text:
        return jsonify({"success": False, "error": "Upload a resume or paste resume text first."}), 400

    if mode not in {"standard", "advanced"}:
        mode = "standard"

    try:
        ensure_model_artifacts()
        analysis = assess_resume(resume_text, mode=mode)
        analysis.setdefault("guided_next_steps", _build_guided_next_steps(analysis))
        analysis.setdefault("support_resources", _build_support_resources())
        analysis.setdefault("report_guide", _build_report_guide(analysis))
        record_upload(
            filename=uploaded_file.filename if uploaded_file and uploaded_file.filename else "pasted_resume.txt",
            file_type=(uploaded_file.filename.rsplit(".", 1)[-1].lower() if uploaded_file and uploaded_file.filename and "." in uploaded_file.filename else "text"),
            mode=analysis.get("mode", mode),
            risk_score=analysis.get("risk_score", 0.0),
            risk_label=analysis.get("risk_label", "Low"),
            reasoning=analysis.get("reasoning", {}),
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        analysis.update({"success": True})
        return jsonify(analysis)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.post("/api/upload")
def api_upload():
    return _handle_upload_request()


@app.post("/api/analyze")
def api_analyze():
    return _handle_upload_request()


if __name__ == "__main__":
    ensure_model_artifacts()
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))