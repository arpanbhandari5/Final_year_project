from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import smtplib
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import requests
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from bootstrap import ensure_model_artifacts, runtime_security_settings
from risk_assessor import analyze_resume as assess_resume
from risk_assessor import _extract_skills
from resume_parser import extract_resume_text as parse_resume_file
from storage import (
    AnalysisSnapshot, Application, CanonicalSkill, CareerGoal, JobPosting, OnetInterest, OnetOccupation, OnetSkill, OnetTask, OnetTechnology, ResumeVersion, Upload, User, authenticate_user, application_payload,
    career_goal_payload, correct_resume_skill, create_analysis_snapshot, create_application,
    create_job_posting, create_partnership_request, create_resume_version, create_user, db,
    dashboard_metrics, get_career_goal, get_career_profile, get_owned_application,
    get_owned_job, get_owned_resume_version, get_resume_profile, get_user_by_email,
    init_database, job_posting_payload, list_owned_applications, record_feedback,
    record_partnership_response, record_upload, resume_profile_payload, resume_version_payload,
    save_career_goal, save_career_profile, snapshot_payload,
)
from utils import install_log_redaction
from skill_registry import seed_skill_registry, resolve_skill_names

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

security_settings = runtime_security_settings()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=security_settings["flask_secret_key"],
    ADMIN_EMAIL=security_settings["admin_email"],
    ADMIN_PASSWORD=security_settings["admin_password"],
    DEBUG=security_settings["debug"],
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'prayash.db').as_posix()}"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
install_log_redaction([app.logger, logging.getLogger("werkzeug")])


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
with app.app_context():
    seed_skill_registry()


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

Local task exposure estimate: {analysis['risk_score']:.2f}
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
            f"Local ML identifies a {analysis['risk_label'].lower()} task exposure estimate with immediate room to sharpen adjacent skills."
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
    profile = get_career_profile(current_user.id)
    return render_template("workspace.html", active_page="workspace", title="Workspace | Prayash", career_profile=profile)


@app.get("/api/career-profile")
@login_required
def api_get_career_profile():
    profile = get_career_profile(current_user.id)
    return jsonify({
        "success": True,
        "profile": {
            "intent": profile.intent,
            "target_role": profile.target_role,
            "target_role_source": profile.target_role_source,
            "confidence": profile.confidence,
        } if profile else None,
    })


@app.put("/api/career-profile")
@login_required
def api_save_career_profile():
    payload = request.get_json(silent=True) or {}
    intent = _clean_text(payload.get("intent"))
    target_role = _clean_text(payload.get("target_role"))
    if not intent or not target_role:
        return jsonify({"success": False, "error": "Intent and target role are required."}), 400
    if len(intent) > 80 or len(target_role) > 160:
        return jsonify({"success": False, "error": "Intent or target role is too long."}), 400
    try:
        profile = save_career_profile(user_id=current_user.id, intent=intent, target_role=target_role)
    except Exception:
        return jsonify({"success": False, "error": "Could not save career profile."}), 500
    return jsonify({
        "success": True,
        "profile": {
            "intent": profile.intent,
            "target_role": profile.target_role,
            "target_role_source": profile.target_role_source,
            "confidence": profile.confidence,
        },
    })


def _optional_number(value: Any, *, minimum: float = 0.0, maximum: float = 1000000.0) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("Numeric fields must contain numbers.")
    if not minimum <= number <= maximum:
        raise ValueError("Numeric fields are outside the allowed range.")
    return number


@app.get("/api/career-goal")
@login_required
def api_get_career_goal():
    return jsonify({"success": True, "goal": career_goal_payload(get_career_goal(current_user.id))})


@app.post("/api/career-goal")
@login_required
def api_save_career_goal():
    payload = request.get_json(silent=True) or {}
    target_role = _clean_text(payload.get("target_role"))
    if not target_role or len(target_role) > 160:
        return jsonify({"success": False, "error": "A target role is required."}), 400
    alternative_roles = payload.get("alternative_roles", [])
    if isinstance(alternative_roles, str):
        alternative_roles = [item.strip() for item in alternative_roles.split(",") if item.strip()]
    if not isinstance(alternative_roles, list) or len(alternative_roles) > 10:
        return jsonify({"success": False, "error": "Alternative roles must be a list of up to 10 roles."}), 400
    try:
        values = {
            "target_role": target_role,
            "alternative_roles": [_clean_text(item)[:160] for item in alternative_roles if _clean_text(item)],
            "geography": _clean_text(payload.get("geography"))[:120],
            "seniority": _clean_text(payload.get("seniority"))[:60],
            "time_per_week": _optional_number(payload.get("time_per_week"), maximum=168),
            "learning_budget": _optional_number(payload.get("learning_budget")),
        }
        goal = save_career_goal(user_id=current_user.id, values=values)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "goal": career_goal_payload(goal)})


@app.get("/api/evidence-profile")
@login_required
def api_get_evidence_profile():
    return jsonify({"success": True, "profile": resume_profile_payload(get_resume_profile(current_user.id))})


@app.patch("/api/evidence-profile/correct")
@login_required
def api_correct_evidence_profile():
    payload = request.get_json(silent=True) or {}
    action = _clean_text(payload.get("action")).lower()
    if action not in {"add", "edit", "delete"}:
        return jsonify({"success": False, "error": "Action must be add, edit, or delete."}), 400
    skill_id = _clean_text(payload.get("skill_id")) or None
    skill = _clean_text(payload.get("skill")) or None
    if skill and len(skill) > 120:
        return jsonify({"success": False, "error": "Skill mention is too long."}), 400
    try:
        confidence = _optional_number(payload.get("confidence"), maximum=1)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    profile = correct_resume_skill(
        user_id=current_user.id,
        action=action,
        skill_id=skill_id,
        skill=skill,
        evidence_span=_clean_text(payload.get("evidence_span"))[:280] or None,
        confidence=confidence,
    )
    if profile is None:
        return jsonify({"success": False, "error": "Skill mention was not found or is invalid."}), 404
    return jsonify({"success": True, "profile": resume_profile_payload(profile)})


def _onet_provenance(occupation: OnetOccupation) -> dict[str, str]:
    return {"source": f"O*NET {occupation.release_version} Database", "release_version": occupation.release_version, "release_date": occupation.release_date, "imported_at": occupation.imported_at.isoformat()}


def _onet_detail(occupation: OnetOccupation) -> dict[str, Any]:
    skills = OnetSkill.query.filter_by(occupation_id=occupation.id).order_by(OnetSkill.name.asc()).all()
    tasks = OnetTask.query.filter_by(occupation_id=occupation.id).order_by(OnetTask.id.asc()).all()
    technologies = OnetTechnology.query.filter_by(occupation_id=occupation.id).order_by(OnetTechnology.name.asc()).all()
    interests = OnetInterest.query.filter_by(occupation_id=occupation.id).order_by(OnetInterest.score.desc()).all()
    skill_names = sorted({skill.name for skill in skills if skill.name})
    related = []
    if skill_names:
        related = OnetOccupation.query.join(OnetSkill, OnetSkill.occupation_id == OnetOccupation.id).filter(OnetOccupation.id != occupation.id, OnetSkill.name.in_(skill_names[:5])).distinct().limit(5).all()
    return {
        "onet_soc_code": occupation.onet_soc_code,
        "title": occupation.title,
        "description": occupation.description or "Occupation description is not available in the imported release.",
        "job_zone": occupation.job_zone or "Not available",
        "tasks": [{"task_id": task.task_id, "statement": task.statement} for task in tasks] or [{"task_id": "unavailable", "statement": "Task data is not available in the imported release."}],
        "skills": [{"element_id": skill.element_id, "name": skill.name, "scale_id": skill.scale_id, "value": skill.value} for skill in skills],
        "technology": [{"name": item.name, "category": item.category} for item in technologies] or [{"name": "Technology data unavailable", "category": "Not imported"}],
        "interests_riasec": [{"name": item.name, "score": item.score} for item in interests] or [{"name": "RIASEC data unavailable", "score": None}],
        "related_careers": [{"onet_soc_code": item.onet_soc_code, "title": item.title} for item in related] or [{"onet_soc_code": "", "title": "Related career data unavailable"}],
        "provenance": _onet_provenance(occupation),
    }


@app.get("/api/occupations/search")
def api_search_occupations():
    query = _clean_text(request.args.get("q"))
    limit = min(max(int(request.args.get("limit", 20)), 1), 50) if request.args.get("limit", "").isdigit() else 20
    statement = OnetOccupation.query
    if query:
        statement = statement.filter((OnetOccupation.title.ilike(f"%{query}%")) | (OnetOccupation.onet_soc_code.ilike(f"%{query}%")))
    occupations = statement.order_by(OnetOccupation.title.asc()).limit(limit).all()
    return jsonify({"success": True, "query": query, "occupations": [{"onet_soc_code": item.onet_soc_code, "title": item.title, "provenance": _onet_provenance(item)} for item in occupations], "fallback": not occupations})


@app.get("/api/occupations/<onet_soc_code>")
def api_occupation_detail(onet_soc_code: str):
    occupation = OnetOccupation.query.filter_by(onet_soc_code=onet_soc_code).first()
    if occupation is None:
        return jsonify({"success": False, "error": "Occupation not found.", "fallback": True}), 404
    return jsonify({"success": True, "occupation": _onet_detail(occupation)})


@app.get("/api/occupations/<onet_soc_code>/compare")
def api_compare_occupations(onet_soc_code: str):
    other_code = _clean_text(request.args.get("compare_to") or request.args.get("other"))
    if not other_code:
        return jsonify({"success": False, "error": "compare_to is required."}), 400
    left = OnetOccupation.query.filter_by(onet_soc_code=onet_soc_code).first()
    right = OnetOccupation.query.filter_by(onet_soc_code=other_code).first()
    if left is None or right is None:
        return jsonify({"success": False, "error": "One or both occupations were not found.", "fallback": True}), 404
    left_skills = {item.name for item in OnetSkill.query.filter_by(occupation_id=left.id).all()}
    right_skills = {item.name for item in OnetSkill.query.filter_by(occupation_id=right.id).all()}
    return jsonify({"success": True, "left": {"onet_soc_code": left.onet_soc_code, "title": left.title}, "right": {"onet_soc_code": right.onet_soc_code, "title": right.title}, "shared_skills": sorted(left_skills & right_skills), "left_only_skills": sorted(left_skills - right_skills), "right_only_skills": sorted(right_skills - left_skills), "provenance": _onet_provenance(left)})


def _job_skill_breakdown(description: str, resume_text: str) -> dict[str, Any]:
    normalized_description = description.lower()
    preferred_markers = ("preferred", "nice to have", "bonus", "desired", "plus")
    required_markers = ("required", "must have", "minimum qualifications", "qualifications")
    preferred_text = " ".join(line for line in description.splitlines() if any(marker in line.lower() for marker in preferred_markers))
    required_text = " ".join(line for line in description.splitlines() if any(marker in line.lower() for marker in required_markers))
    all_skills = _extract_skills(description)
    preferred_skills = set(_extract_skills(preferred_text))
    required_skills = set(_extract_skills(required_text)) or set(all_skills) - preferred_skills
    if not required_skills and all_skills:
        required_skills = set(all_skills)
    resume_skills = set(_extract_skills(resume_text))
    aliases = {"js": "javascript", "py": "python", "postgres": "sql", "postgresql": "sql", "powerbi": "power bi"}
    semantic_matches = []
    exact_matches = []
    for required_skill in sorted(required_skills | preferred_skills):
        normalized = aliases.get(required_skill.replace(" ", ""), required_skill)
        if required_skill in resume_skills:
            exact_matches.append(required_skill)
        elif normalized in {aliases.get(skill.replace(" ", ""), skill) for skill in resume_skills}:
            semantic_matches.append({"job_skill": required_skill, "resume_skill": normalized})
    sentences = re.split(r"(?<=[.!?])\s+|\n+", resume_text)
    evidence = []
    for skill in exact_matches + [item["resume_skill"] for item in semantic_matches]:
        quote = next((sentence.strip() for sentence in sentences if skill.lower() in sentence.lower()), "")
        if quote:
            evidence.append({"skill": skill, "quote": quote[:280]})
    matched = set(exact_matches) | {item["job_skill"] for item in semantic_matches}
    return {
        "required": {"skills": sorted(required_skills), "matched": sorted(matched & required_skills), "missing": sorted(required_skills - matched)},
        "preferred": {"skills": sorted(preferred_skills), "matched": sorted(matched & preferred_skills), "missing": sorted(preferred_skills - matched)},
        "exact_matches": exact_matches,
        "semantic_matches": semantic_matches,
        "resume_evidence_quotes": evidence,
        "missing_skill_requirements": sorted((required_skills | preferred_skills) - matched),
    }


@app.post("/api/jobs")
@login_required
def api_create_job():
    payload = request.get_json(silent=True) or {}
    title = _clean_text(payload.get("title"))
    description = _clean_text(payload.get("description_raw") or payload.get("description"))
    if not title or not description:
        return jsonify({"success": False, "error": "Job title and pasted job description are required."}), 400
    if len(description) > 50000:
        return jsonify({"success": False, "error": "Job description is too long."}), 400
    job = create_job_posting(user_id=current_user.id, title=title[:200], company=_clean_text(payload.get("company"))[:160], description_raw=description, source_url=_clean_text(payload.get("source_url"))[:1000])
    application = create_application(user_id=current_user.id, job_posting_id=job.id, status="Bookmarked")
    return jsonify({"success": True, "job": job_posting_payload(job), "application": application_payload(application)}), 201


@app.get("/api/jobs")
@login_required
def api_list_jobs():
    jobs = JobPosting.query.filter_by(user_id=current_user.id).order_by(JobPosting.created_at.desc()).all()
    return jsonify({"success": True, "jobs": [job_posting_payload(job) for job in jobs]})


@app.post("/api/resume-versions")
@login_required
def api_create_resume_version():
    payload = request.get_json(silent=True) or {}
    name = _clean_text(payload.get("name")) or "Resume version"
    content = _clean_text(payload.get("content_text") or payload.get("resume_text"))
    if not content:
        return jsonify({"success": False, "error": "Resume content is required."}), 400
    version = create_resume_version(user_id=current_user.id, name=name[:160], content_text=content)
    return jsonify({"success": True, "resume_version": resume_version_payload(version)}), 201


@app.get("/api/resume-versions")
@login_required
def api_list_resume_versions():
    versions = ResumeVersion.query.filter_by(user_id=current_user.id).order_by(ResumeVersion.created_at.desc()).all()
    return jsonify({"success": True, "resume_versions": [resume_version_payload(version) for version in versions]})


@app.get("/api/applications")
@login_required
def api_list_applications():
    return jsonify({"success": True, "applications": [application_payload(item) for item in list_owned_applications(current_user.id)]})


@app.post("/api/applications")
@login_required
def api_create_application():
    payload = request.get_json(silent=True) or {}
    try:
        job_id = int(payload.get("job_posting_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "A job posting is required."}), 400
    if get_owned_job(current_user.id, job_id) is None:
        return jsonify({"success": False, "error": "Job posting not found for the current user."}), 404
    resume_version_id = payload.get("resume_version_id")
    if resume_version_id is not None:
        try:
            resume_version_id = int(resume_version_id)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Resume version is invalid."}), 400
        if get_owned_resume_version(current_user.id, resume_version_id) is None:
            return jsonify({"success": False, "error": "Resume version not found for the current user."}), 404
    status = _clean_text(payload.get("status")) or "Bookmarked"
    if status not in Application.STATUSES:
        return jsonify({"success": False, "error": "Invalid application status."}), 400
    application = create_application(user_id=current_user.id, job_posting_id=job_id, resume_version_id=resume_version_id, status=status, notes=_clean_text(payload.get("notes")))
    return jsonify({"success": True, "application": application_payload(application)}), 201


@app.patch("/api/applications/<int:application_id>")
@login_required
def api_update_application(application_id: int):
    application = get_owned_application(current_user.id, application_id)
    if application is None:
        return jsonify({"success": False, "error": "Application not found for the current user."}), 404
    payload = request.get_json(silent=True) or {}
    status = _clean_text(payload.get("status"))
    if status and status not in Application.STATUSES:
        return jsonify({"success": False, "error": "Invalid application status."}), 400
    if status:
        application.status = status
    if "notes" in payload:
        application.notes = _clean_text(payload.get("notes"))
    if "follow_up_date" in payload:
        try:
            application.follow_up_date = date.fromisoformat(payload.get("follow_up_date")) if payload.get("follow_up_date") else None
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Follow-up date must be YYYY-MM-DD."}), 400
    db.session.commit()
    return jsonify({"success": True, "application": application_payload(application)})


@app.post("/api/jobs/analyze")
@login_required
def api_analyze_job():
    payload = request.get_json(silent=True) or {}
    try:
        job_id = int(payload.get("job_posting_id"))
        version_id = int(payload.get("resume_version_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "A job posting and resume version are required."}), 400
    job = get_owned_job(current_user.id, job_id)
    version = get_owned_resume_version(current_user.id, version_id)
    if job is None or version is None:
        return jsonify({"success": False, "error": "Job posting or resume version not found for the current user."}), 404
    result = _job_skill_breakdown(job.description_raw, version.content_text)
    result["job_posting_id"] = job.id
    result["resume_version_id"] = version.id
    result["comparison_timestamp"] = datetime.utcnow().isoformat() + "Z"
    snapshot_hash = hashlib.sha256(json.dumps({"job": job.content_hash, "resume": version.content_hash, "result": result}, sort_keys=True).encode("utf-8")).hexdigest()
    result["snapshot_hash"] = snapshot_hash
    snapshot = AnalysisSnapshot.query.filter_by(user_id=current_user.id, snapshot_hash=snapshot_hash).first()
    if snapshot is None:
        snapshot = create_analysis_snapshot(user_id=current_user.id, job_posting_id=job.id, resume_version_id=version.id, result=result, snapshot_hash=snapshot_hash)
    application = Application.query.filter_by(user_id=current_user.id, job_posting_id=job.id).order_by(Application.updated_at.desc()).first()
    if application is not None:
        application.analysis_snapshot_id = snapshot.id
        application.resume_version_id = version.id
        db.session.commit()
    return jsonify({"success": True, "analysis": result, "snapshot": snapshot_payload(snapshot)})


@app.post("/api/applications/<int:application_id>/export-apply")
@login_required
def api_export_and_mark_applied(application_id: int):
    application = get_owned_application(current_user.id, application_id)
    if application is None:
        return jsonify({"success": False, "error": "Application not found for the current user."}), 404
    payload = request.get_json(silent=True) or {}
    snapshot_id = payload.get("analysis_snapshot_id") or application.analysis_snapshot_id
    try:
        snapshot_id = int(snapshot_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Analyze the job before marking it applied."}), 400
    snapshot = AnalysisSnapshot.query.filter_by(id=snapshot_id, user_id=current_user.id).first()
    if snapshot is None or snapshot.job_posting_id != application.job_posting_id:
        return jsonify({"success": False, "error": "Analysis snapshot is not valid for this application."}), 400
    application.analysis_snapshot_id = snapshot.id
    application.resume_version_id = snapshot.resume_version_id
    application.status = "Applied"
    db.session.commit()
    return jsonify({"success": True, "export_format": "pdf", "snapshot_locked": True, "application": application_payload(application), "snapshot": snapshot_payload(snapshot)})


@app.get("/methodology")
def methodology() -> str:
    return render_template("methodology.html", active_page="methodology", title="Methodology | Prayash")


@app.get("/occupations/<onet_soc_code>")
def occupation_detail_page(onet_soc_code: str) -> str:
    occupation = OnetOccupation.query.filter_by(onet_soc_code=onet_soc_code).first()
    if occupation is None:
        return render_template("occupation.html", active_page="insights", title="Occupation unavailable | Prayash", occupation=None), 404
    return render_template("occupation.html", active_page="insights", title=f"{occupation.title} | Prayash", occupation=_onet_detail(occupation))


@app.get("/privacy")
def privacy() -> str:
    return render_template("privacy.html", active_page="privacy", title="Privacy | Prayash")


@app.get("/insights")
def insights() -> str:
    return render_template("insights.html", active_page="insights", title="Insights | Prayash")


@app.route("/partnerships", methods=["GET", "POST"])
def partnerships() -> str:
    status = None
    if request.method == "POST":
        organization = _clean_text(request.form.get("organization"))
        contact_email = _clean_text(request.form.get("contact_email")).lower()
        use_case = _clean_text(request.form.get("use_case"))
        if organization and "@" in contact_email and use_case:
            status = "Thanks — your request has been sent to the Prayash team."
            create_partnership_request(organization=organization, contact_email=contact_email, use_case=use_case)
        else:
            status = "Please provide your organisation, contact email, and use case."
    return render_template("partnerships.html", active_page="partnerships", title="Partnerships | Prayash", status=status)


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


@app.get("/admin/evaluation-access")
def admin_evaluation_access():
    """Opt-in reviewer shortcut; deliberately disabled unless explicitly configured."""
    if not (app.config.get("TESTING") or os.environ.get("PRAYASH_EVALUATION_BYPASS") == "1"):
        return jsonify({"success": False, "error": "Evaluation access is disabled."}), 403
    admin_email, _ = os.environ.get("ADMIN_EMAIL", "admin123@prayash"), os.environ.get("ADMIN_PASSWORD", "admin123")
    user = get_user_by_email(admin_email)
    if user is None:
        return jsonify({"success": False, "error": "Admin account is unavailable."}), 500
    login_user(user, remember=False)
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/partnerships/<int:request_id>/reply")
@login_required
def admin_reply_to_partnership(request_id: int):
    if not getattr(current_user, "is_admin_email", False):
        return jsonify({"success": False, "error": "Administrator access required."}), 403
    message = _clean_text(request.form.get("message") or (request.get_json(silent=True) or {}).get("message"))
    if not message:
        return jsonify({"success": False, "error": "A response message is required."}), 400
    item = record_partnership_response(request_id, message)
    if item is None:
        return jsonify({"success": False, "error": "Partnership request not found."}), 404
    delivered = _send_partner_email(item.contact_email, message)
    return jsonify({"success": True, "email_sent": delivered})


def _send_partner_email(recipient: str, message: str) -> bool:
    """Use configured SMTP; local review runs still save the reply when SMTP is absent."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    sender = os.environ.get("SMTP_FROM", "no-reply@prayash.local")
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=8) as server:
            if os.environ.get("SMTP_STARTTLS", "true").lower() == "true":
                server.starttls()
            username, password = os.environ.get("SMTP_USERNAME"), os.environ.get("SMTP_PASSWORD")
            if username and password:
                server.login(username, password)
            server.sendmail(sender, [recipient], f"Subject: Reply from Prayash\nFrom: {sender}\nTo: {recipient}\n\n{message}")
        return True
    except (OSError, smtplib.SMTPException):
        return False


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

    if upload_id is not None:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Authentication required for upload feedback."}), 401
        owned_upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first()
        if owned_upload is None:
            return jsonify({"success": False, "error": "Upload not found for the current user."}), 404

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
    job_description = request.form.get("job_description") or (payload or {}).get("job_description", "")
    raw_skills = request.form.get("confirmed_skills") or (payload or {}).get("confirmed_skills", [])
    uploaded_file = request.files.get("resume_file")

    if uploaded_file and uploaded_file.filename:
        resume_text = parse_resume_file(uploaded_file)

    resume_text = _clean_text(resume_text)
    mode = _clean_text(mode).lower() or "standard"

    if not resume_text:
        return jsonify({"success": False, "error": "Upload a resume or paste resume text first."}), 400

    if mode not in {"standard", "advanced"}:
        mode = "standard"
    if isinstance(raw_skills, str):
        confirmed_skills = [item.strip() for item in raw_skills.split(",") if item.strip()]
    else:
        confirmed_skills = [str(item).strip() for item in raw_skills if str(item).strip()]

    try:
        ensure_model_artifacts()
        analysis = assess_resume(resume_text, mode=mode, job_description=job_description, confirmed_skills=confirmed_skills)
        analysis.setdefault("guided_next_steps", _build_guided_next_steps(analysis))
        analysis.setdefault("support_resources", _build_support_resources())
        analysis.setdefault("report_guide", _build_report_guide(analysis))
        upload = record_upload(
            filename=uploaded_file.filename if uploaded_file and uploaded_file.filename else "pasted_resume.txt",
            file_type=(uploaded_file.filename.rsplit(".", 1)[-1].lower() if uploaded_file and uploaded_file.filename and "." in uploaded_file.filename else "text"),
            mode=analysis.get("mode", mode), risk_score=analysis.get("risk_score", 0.0),
            risk_label=analysis.get("risk_label", "Low"), reasoning=analysis.get("reasoning", {}),
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        analysis.update({"success": True, "upload_id": upload.id if upload else None})
        return jsonify(analysis)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.post("/api/upload")
@login_required
def api_upload():
    return _handle_upload_request()


@app.post("/api/analyze")
@login_required
def api_analyze():
    return _handle_upload_request()


@app.post("/api/analyze-stream")
@login_required
def api_analyze_stream():
    """Return the structured analysis contract for stream-capable clients."""
    return _handle_upload_request()


if __name__ == "__main__":
    ensure_model_artifacts()
    app.run(
        debug=app.config["DEBUG"],
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
    )
