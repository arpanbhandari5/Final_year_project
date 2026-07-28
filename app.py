from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from bootstrap import ensure_model_artifacts
from risk_assessor import _clean_text, analyze_resume as assess_resume
from resume_parser import extract_resume_text as parse_resume_file
from storage import User, authenticate_user, create_user, dashboard_metrics, get_user_by_email, init_database, record_feedback, record_upload


BASE_DIR = Path(__file__).resolve().parent

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


@app.after_request
def add_pwa_headers(response):
    # Allow service worker scope from static folder
    if request.path == "/static/sw.js":
        response.headers["Service-Worker-Allowed"] = "/"
    # Security headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response


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
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))