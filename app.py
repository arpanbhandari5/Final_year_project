from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Generator

import requests
from flask import Flask, Response, g, jsonify, redirect, render_template, request, session, stream_with_context, url_for

from flask_compress import Compress
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

# ── Project root ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

# ── Structured Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("prayash")

# ── Load .env (optional) ─────────────────────────────────────
# .env file is in .gitignore - add your real credentials there:
#   GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, etc.
# See .env.example for a full template.
# ⚠️ MUST run BEFORE importing any module that reads environment variables at
# import time (e.g. storage.py computes the email config from os.environ).
try:
    from dotenv import load_dotenv
    env_path = BASE_DIR / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
        log.info("Loaded environment variables from %s", env_path)
    else:
        log.info("No .env file found at %s — using environment variables", env_path)
except ImportError:
    log.info("python-dotenv not installed — using system environment variables")

# ── OAuth (Flask-Dance) ──
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.contrib.github import make_github_blueprint

# Optional OAuth providers – gracefully degrade when flask-dance-contrib is absent
try:
    from flask_dance.contrib.linkedin import make_linkedin_blueprint
except ImportError:
    make_linkedin_blueprint = None  # type: ignore[assignment]

from bootstrap import ensure_model_artifacts
from risk_assessor import analyze_resume as assess_resume, analyze_skills_gap, get_available_roles, suggest_career_paths, generate_learning_roadmap, _extract_skills
from next_action import IMMEDIATE_GOALS, SKILL_STATUSES, recommend_next_action
from job_match import analyze_target_job, skills_from_resume_text
from occupation_authorization import (
    AuthorizationError,
    attach_pending_analysis,
    confirm_server_candidate,
    selectable_occupations,
    select_supported_occupation,
    allowlist_inventory,
    is_selectable,
    canonical_title,
)
from resume_parser import extract_resume_text as parse_resume_file
from storage import (
    User, Application, AnalysisSnapshot, JobPosting, OnetOccupation, OnetSkill, ResumeVersion,
    authenticate_user, create_user, create_oauth_user,
    dashboard_metrics, get_detailed_metrics, get_all_users,
    get_user_by_email, get_user_by_username, init_database, record_feedback, record_upload,
    create_password_reset_token, verify_reset_token, consume_reset_token, update_user_password,
    create_otp, verify_otp, mark_email_verified, send_email,
    check_otp, invalidate_user_otps, get_otp_attempts_remaining,
    OTP_LENGTH, OTP_MAX_ATTEMPTS,
    get_career_profile, save_career_profile, career_goal_payload, get_career_goal, save_career_goal,
    delete_career_goal, get_resume_profile, resume_profile_payload, correct_resume_skill,
    replace_resume_skills, action_item_payload, get_current_action, save_action_item, update_action_status,
    create_job_posting, get_owned_job, job_posting_payload,
    create_resume_version, get_owned_resume_version, resume_version_payload,
    save_target_job_match, get_owned_target_job_match, target_job_match_payload,
    list_owned_target_job_matches, update_owned_target_job_match, delete_owned_target_job_match,
    create_application, get_owned_application, list_owned_applications, application_payload,
    create_analysis_snapshot, snapshot_payload,
    save_application_from_target_job_match,
    create_partnership_request, record_partnership_response,
    db,
)
from utils import clean_text, is_valid_email, split_keywords, format_top_skills
from resume_parser import extract_skills_from_text, analyze_resume_quality, parse_resume_enhanced
from rag_retriever import build_rag_context, rag_service

# ── LLM API (OpenRouter / DeepSeek / OpenAI) ──
try:
    import openai as _openai_module
    _HAS_OPENAI = True
except Exception:
    _HAS_OPENAI = False
_log_openai = logging.getLogger("prayash.llm")


# ── Allow OAuth2 over HTTP for local development ──
# oauthlib (used by Flask-Dance) rejects non-HTTPS by default.
# This env var is REQUIRED for local dev with http://127.0.0.1
# Set FLASK_ENV=production in production with HTTPS to disable this.
if os.environ.get("FLASK_ENV", "development") != "production":
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    log.info("OAUTHLIB_INSECURE_TRANSPORT=1 (local dev mode)")


# ── CSP uses a per-request nonce for inline scripts ──
def _make_csp(nonce: str) -> str:
    return (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        f"font-src 'self' https://fonts.gstatic.com; "
        f"img-src 'self' data: blob:; "
        f"connect-src 'self' https://www.googleapis.com https://api.github.com https://api.linkedin.com https://openrouter.ai; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'"
    )


# ── In-Memory Rate Limiters ──
_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW = 60       # seconds
_RATE_LIMIT_MAX_REQUESTS = 30  # requests per window

# ── OTP request throttling (per email) ──
_OTP_REQUEST_STORE: dict[str, float] = {}
_OTP_REQUEST_WINDOW = 60      # seconds between OTP requests for the same email

# ── Brute-force protection (per-email or per-IP) ──
_LOGIN_ATTEMPT_STORE: dict[str, tuple[int, float]] = {}
_LOGIN_LOCKOUT_WINDOW = 300    # 5 minutes
_LOGIN_MAX_ATTEMPTS = 5         # max failed attempts before lockout


def _otp_request_cooldown(email: str) -> int:
    """Seconds remaining before a new OTP may be requested for this email."""
    key = (email or "").strip().lower()
    if not key:
        return 0
    last = _OTP_REQUEST_STORE.get(key)
    if last is None:
        return 0
    remaining = int(_OTP_REQUEST_WINDOW - (time.time() - last))
    return max(0, remaining)


def _record_otp_request(email: str) -> None:
    _OTP_REQUEST_STORE[(email or "").strip().lower()] = time.time()


def _is_dev_mode() -> bool:
    """True in development (default); False when FLASK_ENV=production.

    Used to surface the OTP code on-screen when email delivery is not
    available, so the forgot-password flow remains usable locally.
    """
    return os.environ.get("FLASK_ENV", "development") != "production"


def _rate_limit_key() -> str:
    """Derive a rate-limit key from the client IP."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() or request.remote_addr or "127.0.0.1")


def _login_attempt_key() -> str:
    """Derive a key from both IP and submitted email/username for login tracking."""
    ip = _rate_limit_key()
    email = (request.form.get("email") or "").strip().lower()
    return f"{ip}:{email}"


def _check_login_lockout() -> bool:
    """Check if this IP+email combination is temporarily locked out.
    Returns True if the request should be blocked."""
    key = _login_attempt_key()
    now = time.time()
    entry = _LOGIN_ATTEMPT_STORE.get(key)
    if entry:
        count, window_start = entry
        if now - window_start < _LOGIN_LOCKOUT_WINDOW:
            if count >= _LOGIN_MAX_ATTEMPTS:
                return True
            return False
        else:
            # Window expired, reset
            _LOGIN_ATTEMPT_STORE.pop(key, None)
    return False


def _record_failed_login() -> None:
    key = _login_attempt_key()
    now = time.time()
    entry = _LOGIN_ATTEMPT_STORE.get(key)
    if entry:
        count, window_start = entry
        if now - window_start < _LOGIN_LOCKOUT_WINDOW:
            _LOGIN_ATTEMPT_STORE[key] = (count + 1, window_start)
        else:
            _LOGIN_ATTEMPT_STORE[key] = (1, now)
    else:
        _LOGIN_ATTEMPT_STORE[key] = (1, now)


def _clear_login_attempts() -> None:
    _LOGIN_ATTEMPT_STORE.pop(_login_attempt_key(), None)


def _get_login_lockout_remaining() -> int:
    """Return seconds remaining in lockout, or 0 if not locked."""
    key = _login_attempt_key()
    now = time.time()
    entry = _LOGIN_ATTEMPT_STORE.get(key)
    if entry:
        count, window_start = entry
        elapsed = now - window_start
        remaining = int(_LOGIN_LOCKOUT_WINDOW - elapsed)
        if remaining > 0 and count >= _LOGIN_MAX_ATTEMPTS:
            return remaining
    return 0


def rate_limit(fn: Callable) -> Callable:
    """Simple sliding-window rate limiter (in-memory, not for multi-worker).

    Disabled automatically when ``app.config["TESTING"]`` is ``True`` so that
    test suites can make many requests without hitting the limit."""
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Bypass rate limiting entirely during tests
        if app.config.get("TESTING"):
            return fn(*args, **kwargs)

        key = _rate_limit_key()
        now = time.time()
        window_start = now - _RATE_LIMIT_WINDOW

        timestamps = _RATE_LIMIT_STORE.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
            log.warning("Rate limit exceeded for IP %s", key)
            return jsonify({"success": False, "error": "Too many requests. Please slow down."}), 429

        timestamps.append(now)
        _RATE_LIMIT_STORE[key] = timestamps
        return fn(*args, **kwargs)
    return wrapper


# ── Static File Versioning ──
_CACHE_BUST_HASH: str | None = None


def _get_cache_bust_hash() -> str:
    """Return a content-based hash of the main stylesheet for cache busting."""
    global _CACHE_BUST_HASH
    if _CACHE_BUST_HASH is None:
        css_path = BASE_DIR / "static" / "styles.css"
        try:
            _CACHE_BUST_HASH = hashlib.md5(css_path.read_bytes()).hexdigest()[:12]
        except OSError:
            _CACHE_BUST_HASH = "v1"
    return _CACHE_BUST_HASH


def ensure_sqlite_parent_directory(database_uri: str) -> str:
    """Create the parent folder for a SQLite file without rewriting the URI.

    In-memory SQLite and non-SQLite URLs are left untouched. A failure to
    create the directory is logged and re-raised so startup does not continue
    with a database path that SQLite cannot open.
    """
    if not database_uri or not str(database_uri).lower().startswith("sqlite:"):
        return database_uri
    try:
        from sqlalchemy.engine.url import make_url
        parsed = make_url(database_uri)
    except Exception as exc:
        log.error("Could not parse SQLite URL while preparing its directory (%s)", type(exc).__name__)
        raise
    if parsed.drivername != "sqlite":
        return database_uri
    database = parsed.database
    if not database or database == ":memory:":
        return database_uri
    parent = Path(database).expanduser().resolve().parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.error("Failed to create SQLite directory %s: %s", parent, exc.strerror or exc)
        raise
    return database_uri


app = Flask(__name__, template_folder="templates", static_folder="static")
_database_uri = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'instance' / 'prayash.db').as_posix()}",
)
ensure_sqlite_parent_directory(_database_uri)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "prayash-local-development-secret"),
    SQLALCHEMY_DATABASE_URI=_database_uri,
    ADMIN_EMAIL=os.environ.get("ADMIN_EMAIL", "admin@prayash.local"),
    ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "prayash-admin"),
    WTF_CSRF_ENABLED=True,
    WTF_CSRF_TIME_LIMIT=3600,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # SESSION_COOKIE_SECURE must be True in production with HTTPS.
    # Default False for local dev. Set FLASK_ENV=production to enable.
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV", "development") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),  # Remember me duration
    # Flask-Compress
    COMPRESS_REGISTER=True,
    COMPRESS_MIMETYPES=["text/html", "text/css", "text/javascript", "application/json", "application/javascript", "image/svg+xml"],
    COMPRESS_LEVEL=6,
    COMPRESS_MIN_SIZE=500,
)

# Initialise compression
Compress(app)
csrf = CSRFProtect(app)

# ── OAuth Blueprints ────────────────────────────────────────────
# Google OAuth: Requires GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env
#   Register redirect URI in Google Cloud Console:
#     - http://localhost:5000/login/google/authorized
#     - http://127.0.0.1:5000/login/google/authorized
# GitHub OAuth: Requires GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET in .env
#   Register callback URL in GitHub OAuth App:
#     - http://localhost:5000/login/github/authorized
# LinkedIn OAuth: Requires LINKEDIN_OAUTH_CLIENT_ID and LINKEDIN_OAUTH_CLIENT_SECRET in .env
#   Register redirect URI in LinkedIn Developer Console
# Microsoft OAuth: NOT IMPLEMENTED (no blueprint registered)
google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
    # Use the full URL scopes exactly as Google returns them.  The short
    # forms ("email profile openid") cause oauthlib to raise a
    # "Scope has changed" Warning exception when the token response's
    # scope does not match the requested scope string.
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
    redirect_to="google_login_callback",
)
github_bp = make_github_blueprint(
    client_id=os.environ.get("GITHUB_OAUTH_CLIENT_ID", ""),
    client_secret=os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", ""),
    redirect_to="github_login_callback",
)

app.register_blueprint(google_bp, url_prefix="/login")
app.register_blueprint(github_bp, url_prefix="/login")

# ── LinkedIn OAuth (only if flask-dance contrib supports it) ──
linkedin_bp = None
if make_linkedin_blueprint is not None:
    linkedin_bp = make_linkedin_blueprint(
        client_id=os.environ.get("LINKEDIN_OAUTH_CLIENT_ID", ""),
        client_secret=os.environ.get("LINKEDIN_OAUTH_CLIENT_SECRET", ""),
        scope=["r_liteprofile", "r_emailaddress"],
        redirect_to="linkedin_login_callback",
    )
    app.register_blueprint(linkedin_bp, url_prefix="/login")

@app.before_request
def _set_csp_nonce() -> None:
    g.csp_nonce = secrets.token_urlsafe(16)

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


@app.errorhandler(CSRFError)
def handle_csrf_error(error: CSRFError):
    """Keep CSRF enabled. Target Job Match unauthenticated mutations return 401."""
    if (
        request.path.startswith("/api/target-job-match") or request.path.startswith("/api/applications")
    ) and not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required."}), 401
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "CSRF validation failed."}), 400
    return error.description or "CSRF validation failed.", 400


# ── OAuth Callback Routes ────────────────────────────────────────
# ── OAuth configuration check helper ──

def _oauth_is_configured(provider: str) -> bool:
    """Return True when the environment variables for *provider* are set."""
    prefix = provider.upper()
    cid = os.environ.get(f"{prefix}_OAUTH_CLIENT_ID", "")
    csec = os.environ.get(f"{prefix}_OAUTH_CLIENT_SECRET", "")
    return bool(cid and csec)


# ── OAuth Login Routes ──────────────────────────────────────────

@app.get("/oauth/google")
def google_login():
    """Redirect to Google OAuth.  Uses /oauth/ path to avoid
    conflicting with the Flask-Dance blueprint at /login/google."""
    if not _oauth_is_configured("google"):
        return redirect(url_for("login", error="Google login is not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."))
    return redirect(url_for("google.login"))


@app.get("/oauth/github")
def github_login():
    """Redirect to GitHub OAuth."""
    if not _oauth_is_configured("github"):
        return redirect(url_for("login", error="GitHub login is not configured. Set GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET."))
    return redirect(url_for("github.login"))


@app.get("/oauth/linkedin")
def linkedin_login():
    """Redirect to LinkedIn OAuth."""
    if linkedin_bp is None:
        return redirect(url_for("login", error="LinkedIn login is not available. Install flask-dance[linkedin] or set LINKEDIN_OAUTH_CLIENT_ID and LINKEDIN_OAUTH_CLIENT_SECRET."))
    if not _oauth_is_configured("linkedin"):
        return redirect(url_for("login", error="LinkedIn login is not configured. Set LINKEDIN_OAUTH_CLIENT_ID and LINKEDIN_OAUTH_CLIENT_SECRET."))
    try:
        return redirect(url_for("linkedin.login"))
    except Exception:
        return redirect(url_for("login", error="LinkedIn OAuth endpoint is unavailable."))


@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token:
        log.warning("Google OAuth failed — no token received")
        return False
    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        log.warning("Google OAuth failed — could not fetch userinfo")
        return False
    info = resp.json()
    email = info.get("email", "").strip().lower()
    if not email:
        log.warning("Google OAuth — no email in userinfo")
        return False
    user = create_oauth_user(email, "google")
    login_user(user, remember=True)
    log.info("Google OAuth login: %s", email)
    return False  # Prevent Flask-Dance from storing the token


@oauth_authorized.connect_via(github_bp)
def github_logged_in(blueprint, token):
    if not token:
        log.warning("GitHub OAuth failed — no token received")
        return False
    resp = blueprint.session.get("/user")
    if not resp.ok:
        log.warning("GitHub OAuth failed — could not fetch user")
        return False
    info = resp.json()
    email = info.get("email", "") or info.get("login", "") + "@github.oauth"
    email = email.strip().lower()
    if not email:
        log.warning("GitHub OAuth — no email or login in response")
        return False
    # GitHub may not expose the primary email; try the emails endpoint if needed
    if email.endswith("@github.oauth"):
        emails_resp = blueprint.session.get("/user/emails")
        if emails_resp.ok:
            emails_data = emails_resp.json()
            for entry in emails_data:
                if entry.get("primary") and entry.get("verified"):
                    email = entry["email"].strip().lower()
                    break
    user = create_oauth_user(email, "github")
    login_user(user, remember=True)
    log.info("GitHub OAuth login: %s", email)
    return False


# ── OAuth Authorized Handlers ─────────────────────────────────

if linkedin_bp is not None:
    @oauth_authorized.connect_via(linkedin_bp)
    def linkedin_logged_in(blueprint, token):
        if not token:
            log.warning("LinkedIn OAuth failed — no token received")
            return False
        try:
            # LinkedIn v2 API: /me for profile, /emailAddress for email
            resp = blueprint.session.get("/v2/me?projection=(id,localizedFirstName,localizedLastName)")
            email_resp = blueprint.session.get("/v2/emailAddress?q=members&projection=(elements*(handle~))")
            if not resp.ok:
                log.warning("LinkedIn OAuth failed — could not fetch profile")
                return False
            info = resp.json()
            email = ""
            if email_resp.ok:
                email_data = email_resp.json()
                elements = email_data.get("elements", [])
                if elements:
                    email = elements[0].get("handle~", {}).get("emailAddress", "") or ""
            if not email:
                # Fall back to a synthetic email if LinkedIn doesn't provide one
                lid = info.get("id", "")
                email = f"linkedin_{lid}@linkedin.oauth" if lid else ""
            email = email.strip().lower()
            if not email:
                log.warning("LinkedIn OAuth — no email could be derived")
                return False
            user = create_oauth_user(email, "linkedin")
            login_user(user, remember=True)
            log.info("LinkedIn OAuth login: %s", email)
        except Exception as exc:
            log.warning("LinkedIn OAuth error: %s", exc)
            return False
        return False


# ── OAuth Callback Routes ───────────────────────────────────────

@app.get("/login/google/callback")
def google_login_callback():
    """Callback landing after Google OAuth completes."""
    if not current_user.is_authenticated:
        return redirect(url_for("login", error="Google login failed. Please try again."))
    return redirect(url_for("workspace"))


@app.get("/login/github/callback")
def github_login_callback():
    """Callback landing after GitHub OAuth completes."""
    if not current_user.is_authenticated:
        return redirect(url_for("login", error="GitHub login failed. Please try again."))
    return redirect(url_for("workspace"))


@app.get("/login/linkedin/callback")
def linkedin_login_callback():
    """Callback landing after LinkedIn OAuth completes."""
    if not current_user.is_authenticated:
        return redirect(url_for("login", error="LinkedIn login failed. Please try again."))
    return redirect(url_for("workspace"))


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
        "static_version": _get_cache_bust_hash(),
        "csp_nonce": getattr(g, "csp_nonce", secrets.token_urlsafe(16)),
        "csrf_token": lambda: generate_csrf(),
        # OAuth provider configuration status for the auth template
        "oauth_google_configured": _oauth_is_configured("google"),
        "oauth_github_configured": _oauth_is_configured("github"),
        "oauth_linkedin_configured": _oauth_is_configured("linkedin") and linkedin_bp is not None,
    }


@app.get("/")
def index() -> str:
    return render_template("index.html", active_page="home", title="Prayash: Learning for better future")


# ── Password & OTP Email Helpers ────────────────────────────────

_PASSWORD_SPECIAL_RE = re.compile(r"[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?`~]")


def validate_password_strength(password: str) -> str | None:
    """Return an error message for a weak password, else ``None``."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    if not _PASSWORD_SPECIAL_RE.search(password):
        return "Password must contain at least one special character."
    return None


def _extract_otp_code() -> str:
    """Read the OTP code from the request.

    Prefers the JS-combined ``otp`` field but falls back to assembling the
    individual ``otp_digit_*`` fields so the form also works without JS."""
    otp_code = (request.form.get("otp") or "").strip()
    if otp_code:
        return otp_code
    digits = []
    for key, value in request.form.items():
        if key.startswith("otp_digit_"):
            digits.append((int(key.rsplit("_", 1)[1]), (value or "").strip()))
    digits.sort()
    return "".join(d for _, d in digits)


def _build_otp_email(purpose: str, otp_code: str) -> tuple[str, str, str]:
    """Build a professional HTML + plain-text OTP email.

    Returns ``(subject, html_body, text_body)``."""
    if purpose == "reset_password":
        subject = "Reset your Prayash password"
        heading = "Password Reset Request"
        intro = "We received a request to reset your password. Use this 6-digit code to continue:"
        hint = "This code expires in 10 minutes. If you didn't request a password reset, you can safely ignore this email."
    else:
        subject = "Verify your Prayash account"
        heading = "Verify Your Email"
        intro = "Welcome to Prayash! Use this 6-digit code to verify your email:"
        hint = "This code expires in 10 minutes. If you didn't create an account, ignore this email."

    html = f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;padding:24px;background:#0f0f14;border-radius:16px;color:#e2e8f0">
    <h2 style="color:#d3bbff;margin:0 0 16px">{heading}</h2>
    <p style="margin:0 0 8px">{intro}</p>
    <div style="font-size:36px;letter-spacing:8px;text-align:center;padding:20px;background:#1a1a24;border-radius:12px;margin:16px 0;color:#d3bbff;font-weight:bold">{otp_code}</div>
    <p style="color:#94a3b8;font-size:13px;margin:0">{hint}</p>
    </div>"""
    text = f"{heading}\n\n{intro}\n\nYour 6-digit code: {otp_code}\n\n{hint}"
    return subject, html, text


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    error = request.args.get("error") or None
    next_url = request.args.get("next") or request.form.get("next") or url_for("workspace")
    lockout_remaining = 0

    if request.method == "POST":
        # Check brute-force lockout
        if _check_login_lockout():
            lockout_remaining = _get_login_lockout_remaining()
            error = f"Too many failed attempts. Try again in {lockout_remaining} seconds."
            log.warning("Login lockout active for key %s", _login_attempt_key())
            return render_template(
                "auth.html", mode="login", active_page="login",
                title="Login | Prayash", error=error, next_url=next_url,
                lockout_remaining=lockout_remaining,
            )

        email_or_username = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = request.form.get("remember") == "on"
        user = authenticate_user(email_or_username, password)

        if user:
            if not user.email_verified:
                # Password was correct — don't count as a failed login attempt
                # Send a new OTP and redirect to verification
                otp = create_otp(user, purpose="verify_email")
                subject, html_body, text_body = _build_otp_email("verify_email", otp.otp)
                send_email(user.email, subject, html_body, text_body)
                # Stash the email in the session so the /verify-otp handler
                # knows which account is being verified (matches the signup flow).
                session["verify_email"] = user.email
                error = "Please verify your email first. A new code has been sent."
                return render_template(
                    "verify_otp.html", mode="verify_email",
                    active_page="", title="Verify Email | Prayash",
                    email=user.email, error=error,
                )
            _clear_login_attempts()
            user.touch_last_login()
            login_user(user, remember=remember)
            log.info("Login successful: %s (remember=%s)", user.email, remember)
            return redirect(next_url)
        else:
            _record_failed_login()
            error = "Invalid email/username or password."
            attempts_left = _LOGIN_MAX_ATTEMPTS
            entry = _LOGIN_ATTEMPT_STORE.get(_login_attempt_key())
            if entry:
                attempts_left = max(0, _LOGIN_MAX_ATTEMPTS - entry[0])
            if attempts_left > 0 and attempts_left <= 3:
                error = f"Invalid credentials. {attempts_left} attempt(s) remaining."

    return render_template(
        "auth.html", mode="login", active_page="login",
        title="Login | Prayash", error=error, next_url=next_url,
        form_data={},
    )


@app.route("/signup", methods=["GET", "POST"])
def signup() -> str:
    error = None
    form_data = {}

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        terms = request.form.get("terms") == "on"

        form_data = {
            "full_name": full_name,
            "username": username,
            "email": email,
            "phone": phone,
        }

        # Server-side validation
        if not full_name or len(full_name) < 2:
            error = "Full name must be at least 2 characters."
        elif not username or len(username) < 4:
            error = "Username must be at least 4 characters."
        elif not re.match(r"^[a-zA-Z0-9_]+$", username):
            error = "Username can only contain letters, numbers, and underscores."
        elif not email or not is_valid_email(email):
            error = "Enter a valid email address."
        elif phone and not re.match(r"^[\d\s\+\-\(\)]{7,20}$", phone):
            error = "Enter a valid phone number (7-20 digits)."
        elif not terms:
            error = "You must agree to the terms & conditions."
        elif validate_password_strength(password):
            error = validate_password_strength(password)
        elif password != confirm:
            error = "Passwords do not match."
        elif get_user_by_email(email):
            error = "Email already exists. Please log in."
        elif get_user_by_username(username):
            error = "Username already taken. Please choose another."
        else:
            user = create_user(
                email=email,
                password=password,
                full_name=full_name,
                username=username,
                phone=phone or None,
                role="student",
            )
            # Generate OTP for email verification
            otp = create_otp(user, purpose="verify_email")
            subject, html_body, text_body = _build_otp_email("verify_email", otp.otp)
            send_email(user.email, subject, html_body, text_body)
            log.info("New user registered: %s (username=%s)", email, username)
            # Store user email in session for verification page
            session["verify_email"] = user.email
            return redirect(url_for("verify_otp_page"))

    return render_template(
        "auth.html", mode="signup", active_page="signup",
        title="Sign Up | Prayash", error=error, form_data=form_data,
    )


# ── OTP Verification Routes ──────────────────────────────────────

@app.route("/verify-otp", methods=["GET", "POST"])
@rate_limit
def verify_otp_page():
    """Show OTP verification page and handle code submission."""
    email = session.get("verify_email", "")
    if not email:
        return redirect(url_for("signup"))
    
    error = None
    success = None
    
    if request.method == "POST":
        otp_code = _extract_otp_code()
        purpose = request.form.get("purpose", "verify_email")

        if not otp_code or len(otp_code) != OTP_LENGTH or not otp_code.isdigit():
            error = "Please enter a valid 6-digit code."
        else:
            user = get_user_by_email(email)
            if not user:
                error = "User not found."
            elif verify_otp(user, otp_code, purpose):
                mark_email_verified(user)
                session.pop("verify_email", None)
                # Log the user in after successful verification
                login_user(user, remember=True)
                log.info("Email verified: %s", email)
                return redirect(url_for("workspace"))
            else:
                error = "Invalid or expired code. Please try again."
    
    return render_template(
        "verify_otp.html", mode="verify_email",
        active_page="", title="Verify Email | Prayash",
        email=email, error=error,
    )


@app.route("/resend-otp", methods=["POST"])
@rate_limit
def resend_otp():
    """Resend an OTP code for email verification or password reset."""
    purpose = request.form.get("purpose", "verify_email")
    if purpose not in ("verify_email", "reset_password"):
        purpose = "verify_email"

    session_key = "reset_email" if purpose == "reset_password" else "verify_email"
    email = session.get(session_key, "")
    if not email:
        email = (request.form.get("email") or "").strip().lower()

    if not email:
        return jsonify({"success": False, "error": "Email not found."}), 400

    user = get_user_by_email(email)
    if not user:
        return jsonify({"success": False, "error": "User not found."}), 404

    cooldown = _otp_request_cooldown(email)
    if cooldown > 0:
        return jsonify({
            "success": False,
            "error": f"Please wait {cooldown} second(s) before requesting another code.",
        }), 429

    _record_otp_request(email)
    otp = create_otp(user, purpose=purpose)
    subject, html_body, text_body = _build_otp_email(purpose, otp.otp)
    send_email(user.email, subject, html_body, text_body)

    session[session_key] = user.email
    message = "A new reset code has been sent." if purpose == "reset_password" else "A new verification code has been sent."
    payload: dict[str, Any] = {"success": True, "message": message}
    if _is_dev_mode():
        # Development convenience: return the code so the front-end can show it.
        payload["dev_otp"] = otp.otp
    return jsonify(payload)


# ── Forgot Password with OTP ──

@app.route("/forgot-password/otp", methods=["GET", "POST"])
@rate_limit
def forgot_password_otp():
    """Handle forgot password flow with OTP."""
    error = None
    sent = False
    dev_otp = None
    email = session.get("reset_email", "")

    if request.method == "POST":
        email_input = (request.form.get("email") or "").strip().lower()
        if not email_input or not is_valid_email(email_input):
            error = "Enter a valid email address."
        else:
            # Cooldown is applied to every submission (whether or not the
            # email exists) so the form cannot be used to probe the database.
            cooldown = _otp_request_cooldown(email_input)
            if cooldown > 0:
                error = f"Please wait {cooldown} second(s) before requesting another code."
            else:
                user = get_user_by_email(email_input)
                _record_otp_request(email_input)
                if user:
                    otp = create_otp(user, purpose="reset_password")
                    subject, html_body, text_body = _build_otp_email("reset_password", otp.otp)
                    send_email(user.email, subject, html_body, text_body)
                    session["reset_email"] = user.email
                    email = user.email
                    # In development, surface the code on-screen so the flow
                    # works even when SMTP delivery fails (e.g. no valid
                    # Gmail App Password configured). Never shown in production.
                    if _is_dev_mode():
                        dev_otp = otp.otp
                        log.warning(
                            "DEV MODE: OTP for %s shown on-screen (email delivery may be unavailable). "
                            "Set FLASK_ENV=production to hide it.",
                            email_input,
                        )
                # Always show success to prevent email enumeration
                sent = True

    return render_template(
        "forgot_password.html",
        active_page="",
        title="Forgot Password | Prayash",
        error=error,
        sent=sent,
        email=email if sent else "",
        dev_otp=dev_otp,
    )


@app.route("/reset-password/otp", methods=["GET", "POST"])
@rate_limit
def reset_password_otp():
    """Verify OTP and allow password reset."""
    error = None
    success = False
    email = session.get("reset_email", "")

    if not email:
        return redirect(url_for("forgot_password_otp"))

    user = get_user_by_email(email)
    if not user:
        session.pop("reset_email", None)
        return redirect(url_for("forgot_password_otp"))

    if request.method == "POST":
        otp_code = _extract_otp_code()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        step = request.form.get("step", "otp")

        if step == "otp":
            if not otp_code or len(otp_code) != OTP_LENGTH or not otp_code.isdigit():
                error = "Please enter a valid 6-digit code."
            else:
                status = check_otp(user, otp_code, "reset_password")
                if status == "valid":
                    # OTP verified, show password form
                    session["otp_verified"] = True
                    session.pop("otp_code", None)
                    return render_template(
                        "reset_password.html",
                        active_page="",
                        title="Reset Password | Prayash",
                        error=None,
                        success=False,
                        otp_verified=True,
                        email=email,
                    )
                elif status == "invalid":
                    remaining = get_otp_attempts_remaining(user, "reset_password")
                    if remaining > 0:
                        error = f"Incorrect code. {remaining} attempt(s) remaining."
                    else:
                        error = "Incorrect code."
                elif status == "expired":
                    error = "This code has expired. Please request a new one."
                elif status == "used":
                    error = "This code has already been used. Please request a new one."
                elif status == "max_attempts":
                    error = "Too many incorrect attempts. Please request a new code."
        elif step == "password":
            if not session.get("otp_verified"):
                error = "Please verify your code first."
            else:
                strength_error = validate_password_strength(password)
                if strength_error:
                    error = strength_error
                elif password != confirm:
                    error = "Passwords do not match."
                else:
                    update_user_password(user, password)
                    # Invalidate every outstanding reset OTP (one-time use)
                    invalidate_user_otps(user, "reset_password")
                    session.pop("reset_email", None)
                    session.pop("otp_verified", None)
                    log.info("Password reset (OTP) successful for %s", email)
                    success = True

    return render_template(
        "reset_password.html",
        active_page="",
        title="Reset Password | Prayash",
        error=error,
        success=success,
        otp_verified=session.get("otp_verified", False),
        email=email,
    )


@app.route("/logout", methods=["GET", "POST"])
@login_required
@csrf.exempt
def logout() -> Any:
    user_name = current_user.email
    session.clear()  # Clear session FIRST to prevent residue after logout
    logout_user()
    log.info("User logged out: %s", user_name)
    return redirect(url_for("index"))


@app.get("/workspace")
@login_required
def workspace() -> str:
    return render_template("workspace.html", active_page="workspace", title="Workspace | Prayash")


@app.get("/workspace/job-match")
@login_required
def target_job_match_page() -> str:
    return render_template("job_match.html", active_page="workspace", title="Target Job Match | Prayash")


@app.get("/workspace/skills-gap")
@login_required
def skills_gap() -> str:
    """Dedicated skills gap analysis page (SAHAY_AI-inspired)."""
    return render_template("skills_gap.html", active_page="workspace", title="Skills Gap Analysis | Prayash")


@app.get("/workspace/applications")
@login_required
def applications_page() -> str:
    return render_template(
        "applications.html",
        active_page="workspace",
        title="Saved jobs | Prayash",
        application_statuses=Application.STATUSES,
    )


@app.get("/methodology")
def methodology() -> str:
    return render_template("methodology.html", active_page="methodology", title="Methodology | Prayash")


@app.post("/admin/partnerships/<int:request_id>/reply")
@login_required
def admin_reply_to_partnership(request_id: int):
    if not getattr(current_user, "is_admin_email", False):
        return jsonify({"success": False, "error": "Administrator access required."}), 403
    payload = request.get_json(silent=True) or {}
    message = clean_text(request.form.get("message") or payload.get("message"))
    if not message:
        return jsonify({"success": False, "error": "A response message is required."}), 400
    item = record_partnership_response(request_id, message)
    if item is None:
        return jsonify({"success": False, "error": "Partnership request not found."}), 404
    delivered = False
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        delivered = send_email(
            item.contact_email,
            "Reply from Prayash",
            f"<p>{message}</p>",
            message,
        )
    return jsonify({"success": True, "email_sent": delivered})


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
    intent = clean_text(payload.get("intent"))
    target_role = clean_text(payload.get("target_role"))
    if not intent or not target_role:
        return jsonify({"success": False, "error": "Intent and target role are required."}), 400
    if len(intent) > 80 or len(target_role) > 160:
        return jsonify({"success": False, "error": "Intent or target role is too long."}), 400
    try:
        profile = save_career_profile(user_id=current_user.id, intent=intent, target_role=target_role)
    except Exception:
        log.exception("Could not save career profile")
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


@app.get("/api/career-goal")
@login_required
def api_get_career_goal():
    return jsonify({"success": True, "goal": career_goal_payload(get_career_goal(current_user.id))})


@app.post("/api/career-goal")
@login_required
def api_save_career_goal():
    payload = request.get_json(silent=True) or {}
    occupation_code = clean_text(payload.get("target_occupation_code") or "")
    target_role = clean_text(payload.get("target_role"))
    if occupation_code:
        if not is_selectable(occupation_code):
            return jsonify({"success": False, "error": "Target occupation must be selected from the server allowlist."}), 400
        target_role = canonical_title(occupation_code) or target_role
    if not target_role or len(target_role) > 160:
        return jsonify({"success": False, "error": "A target role is required."}), 400
    alternative_roles = payload.get("alternative_roles", [])
    if isinstance(alternative_roles, str):
        alternative_roles = [item.strip() for item in alternative_roles.split(",") if item.strip()]
    if not isinstance(alternative_roles, list) or len(alternative_roles) > 10:
        return jsonify({"success": False, "error": "Alternative roles must be a list of up to 10 roles."}), 400
    alternative_code = clean_text(payload.get("alternative_occupation_code") or "")
    if alternative_code:
        if not is_selectable(alternative_code):
            return jsonify({"success": False, "error": "Alternative occupation must be selected from the server allowlist."}), 400
        alt_title = canonical_title(alternative_code)
        if alt_title:
            alternative_roles = [alt_title]
    immediate_goal = clean_text(payload.get("immediate_goal") or "")
    if immediate_goal and immediate_goal not in IMMEDIATE_GOALS:
        return jsonify({"success": False, "error": "immediate_goal is not a supported value."}), 400
    try:
        values = {
            "target_role": target_role,
            "target_occupation_code": occupation_code,
            "alternative_roles": [clean_text(item)[:160] for item in alternative_roles if clean_text(item)],
            "geography": clean_text(payload.get("geography"))[:120],
            "seniority": clean_text(payload.get("seniority"))[:60],
            "time_per_week": _optional_number(payload.get("time_per_week"), maximum=168),
            "learning_budget": _optional_number(payload.get("learning_budget")),
            "immediate_goal": immediate_goal,
        }
        goal = save_career_goal(user_id=current_user.id, values=values)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "goal": career_goal_payload(goal)})


@app.delete("/api/career-goal")
@login_required
def api_delete_career_goal():
    deleted = delete_career_goal(current_user.id)
    return jsonify({"success": True, "deleted": deleted})


@app.get("/api/evidence-profile")
@login_required
def api_get_evidence_profile():
    return jsonify({"success": True, "profile": resume_profile_payload(get_resume_profile(current_user.id))})


@app.patch("/api/evidence-profile/correct")
@login_required
def api_correct_evidence_profile():
    payload = request.get_json(silent=True) or {}
    action = clean_text(payload.get("action")).lower()
    if action not in {"add", "edit", "delete"}:
        return jsonify({"success": False, "error": "Action must be add, edit, or delete."}), 400
    skill_id = clean_text(payload.get("skill_id")) or None
    skill = clean_text(payload.get("skill")) or None
    if skill and len(skill) > 120:
        return jsonify({"success": False, "error": "Skill mention is too long."}), 400
    status = clean_text(payload.get("status") or "")
    if status and status not in SKILL_STATUSES:
        return jsonify({"success": False, "error": "Evidence status is not supported."}), 400
    try:
        confidence = _optional_number(payload.get("confidence"), maximum=1)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    profile = correct_resume_skill(
        user_id=current_user.id,
        action=action,
        skill_id=skill_id,
        skill=skill,
        evidence_span=clean_text(payload.get("evidence_span"))[:280] or None,
        confidence=confidence,
        status=status or None,
    )
    if profile is None:
        return jsonify({"success": False, "error": "Skill mention was not found or is invalid."}), 404
    return jsonify({"success": True, "profile": resume_profile_payload(profile)})


@app.post("/api/evidence-profile/import")
@login_required
def api_import_evidence_profile():
    payload = request.get_json(silent=True) or {}
    items = payload.get("skills") or payload.get("items") or []
    if not isinstance(items, list):
        return jsonify({"success": False, "error": "skills must be a list."}), 400
    profile = replace_resume_skills(current_user.id, items)
    return jsonify({"success": True, "profile": resume_profile_payload(profile)})


def _workspace_loop_payload(*, persist: bool = False):
    goal = career_goal_payload(get_career_goal(current_user.id))
    profile = resume_profile_payload(get_resume_profile(current_user.id))
    skills = profile.get("extracted_skills") or []
    recommendation = recommend_next_action(goal=goal, skills=skills)
    action = get_current_action(current_user.id)
    if persist:
        action = save_action_item(
            user_id=current_user.id,
            values={
                "source_type": recommendation["source_type"],
                "source_id": recommendation["source_id"],
                "action_type": recommendation["action_type"],
                "title": recommendation["title"],
                "description": recommendation["description"],
                "status": "not_started",
                "priority": 1,
            },
        )
    return {
        "success": True,
        "goal": goal,
        "profile": profile,
        "gap": recommendation.get("gap"),
        "recommendation": {key: recommendation[key] for key in ("action_type", "title", "description")},
        "action": action_item_payload(action),
        "immediate_goals": list(IMMEDIATE_GOALS),
        "skill_statuses": list(SKILL_STATUSES),
    }


@app.get("/api/workspace-loop")
@login_required
def api_get_workspace_loop():
    return jsonify(_workspace_loop_payload(persist=False))


@app.post("/api/actions/refresh")
@login_required
def api_refresh_action():
    return jsonify(_workspace_loop_payload(persist=True))


@app.patch("/api/actions/<int:action_id>")
@login_required
def api_update_action(action_id: int):
    payload = request.get_json(silent=True) or {}
    status = clean_text(payload.get("status") or "")
    item = update_action_status(user_id=current_user.id, action_id=action_id, status=status)
    if item is None:
        return jsonify({"success": False, "error": "Action was not found or status is invalid."}), 404
    return jsonify({"success": True, "action": action_item_payload(item)})


MAX_TARGET_JOB_DESCRIPTION = 20000


def _target_job_json_payload():
    if request.data and request.mimetype == "application/json":
        payload = request.get_json(silent=True)
        if payload is None:
            return None, (jsonify({"success": False, "error": "Malformed JSON."}), 400)
        if not isinstance(payload, dict):
            return None, (jsonify({"success": False, "error": "Malformed JSON."}), 400)
        return payload, None
    return {}, None


def _resolve_target_job_evidence(payload: dict):
    # Client-supplied user_id / owner_id / labels are ignored; ownership is session-derived.
    source = clean_text(payload.get("evidence_source") or "profile").lower()
    if source in {"", "profile", "current", "current_evidence_profile"}:
        profile = resume_profile_payload(get_resume_profile(current_user.id))
        return {
            "skills": profile.get("extracted_skills") or [],
            "evidence_source_type": "profile",
            "evidence_source_key": "profile",
            "evidence_source_label": "Current evidence profile",
            "resume_version_id": None,
        }, None
    if source in {"resume_version", "resume"}:
        try:
            version_id = int(payload.get("resume_version_id"))
        except (TypeError, ValueError):
            return None, (jsonify({"success": False, "error": "A resume version is required."}), 400)
        version = get_owned_resume_version(current_user.id, version_id)
        if version is None:
            return None, (jsonify({"success": False, "error": "Resume version was not found."}), 404)
        created = version.created_at.isoformat() if version.created_at else ""
        label = f"Resume: {version.name} · Version: {version.id} · {created}"
        return {
            "skills": skills_from_resume_text(version.content_text),
            "evidence_source_type": "resume_version",
            "evidence_source_key": f"resume:{version.id}",
            "evidence_source_label": label[:240],
            "resume_version_id": version.id,
        }, None
    return None, (jsonify({"success": False, "error": "Unknown evidence source."}), 400)


@app.get("/api/target-job-match")
@login_required
def api_list_target_job_matches():
    rows = list_owned_target_job_matches(current_user.id)
    return jsonify({
        "success": True,
        "count": len(rows),
        "matches": [
            {
                "id": row.id,
                "title": row.title,
                "company": row.company,
                "content_hash": row.content_hash,
                "evidence_source_label": getattr(row, "evidence_source_label", None) or "Current evidence profile",
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ],
        "export_supported": False,
    })


@app.post("/api/target-job-match")
@login_required
def api_create_target_job_match():
    payload, error = _target_job_json_payload()
    if error is not None:
        return error
    description = clean_text(payload.get("description") or payload.get("description_raw") or "")
    if not description:
        return jsonify({"success": False, "error": "A pasted job description is required."}), 400
    if len(description) < 40:
        return jsonify({"success": False, "error": "Paste a fuller job description (at least 40 characters)."}), 400
    if len(description) > MAX_TARGET_JOB_DESCRIPTION:
        return jsonify({
            "success": False,
            "error": f"Job description is too long. Maximum length is {MAX_TARGET_JOB_DESCRIPTION} characters.",
        }), 400
    evidence, evidence_error = _resolve_target_job_evidence(payload)
    if evidence_error is not None:
        return evidence_error
    result = analyze_target_job(
        description=description,
        skills=evidence["skills"],
        evidence_source_label=evidence["evidence_source_label"],
    )
    row, created = save_target_job_match(
        user_id=current_user.id,
        values={
            "title": clean_text(payload.get("title"))[:200],
            "company": clean_text(payload.get("company"))[:160],
            "location": clean_text(payload.get("location"))[:160],
            "description_raw": description,
            "result": result,
            "evidence_source_type": evidence["evidence_source_type"],
            "evidence_source_key": evidence["evidence_source_key"],
            "evidence_source_label": evidence["evidence_source_label"],
            "resume_version_id": evidence["resume_version_id"],
        },
    )
    log.info(
        "target job match %s id=%s length=%s hash=%s",
        "created" if created else "reused",
        row.id,
        len(description),
        row.content_hash,
    )
    body = target_job_match_payload(row)
    body["success"] = True
    body["created"] = created
    body["occupation_unchanged"] = True
    return jsonify(body), (201 if created else 200)


@app.patch("/api/target-job-match/<int:match_id>")
@login_required
def api_update_target_job_match(match_id: int):
    payload, error = _target_job_json_payload()
    if error is not None:
        return error
    values = {}
    if "title" in payload:
        values["title"] = clean_text(payload.get("title"))[:200]
    if "company" in payload:
        values["company"] = clean_text(payload.get("company"))[:160]
    if "location" in payload:
        values["location"] = clean_text(payload.get("location"))[:160]
    if not values:
        return jsonify({"success": False, "error": "No updatable fields were provided."}), 400
    row = update_owned_target_job_match(
        user_id=current_user.id,
        match_id=match_id,
        values=values,
    )
    if row is None:
        return jsonify({"success": False, "error": "Job match was not found."}), 404
    body = target_job_match_payload(row)
    body["success"] = True
    return jsonify(body)


@app.delete("/api/target-job-match/<int:match_id>")
@login_required
def api_delete_target_job_match(match_id: int):
    deleted = delete_owned_target_job_match(user_id=current_user.id, match_id=match_id)
    if not deleted:
        return jsonify({"success": False, "error": "Job match was not found."}), 404
    return jsonify({"success": True, "deleted": True})


@app.post("/api/target-job-match/<int:match_id>/save-application")
@login_required
def api_save_application_from_target_job_match(match_id: int):
    payload, error = _target_job_json_payload()
    if error is not None:
        return error
    match = get_owned_target_job_match(current_user.id, match_id)
    if match is None:
        return jsonify({"success": False, "error": "Job match was not found."}), 404
    application, created = save_application_from_target_job_match(user_id=current_user.id, match=match)
    log.info(
        "application save-from-match %s application_id=%s match_id=%s job_hash=%s",
        "created" if created else "reused",
        application.id,
        match.id,
        match.content_hash,
    )
    body = application_payload(application)
    body["success"] = True
    body["created"] = created
    return jsonify(body), (201 if created else 200)


@app.get("/api/target-job-match/<int:match_id>")
@login_required
def api_get_target_job_match(match_id: int):
    row = get_owned_target_job_match(current_user.id, match_id)
    if row is None:
        return jsonify({"success": False, "error": "Job match was not found."}), 404
    body = target_job_match_payload(row)
    body["success"] = True
    return jsonify(body)


def _onet_provenance(occupation: OnetOccupation) -> dict[str, str]:
    return {
        "source": f"O*NET {occupation.release_version} Database",
        "release_version": occupation.release_version,
        "release_date": occupation.release_date,
        "imported_at": occupation.imported_at.isoformat(),
    }


@app.get("/api/occupations/search")
def api_search_occupations():
    query = clean_text(request.args.get("q"))
    raw_limit = request.args.get("limit", "")
    limit = min(max(int(raw_limit), 1), 50) if str(raw_limit).isdigit() else 20
    statement = OnetOccupation.query
    if query:
        statement = statement.filter(
            (OnetOccupation.title.ilike(f"%{query}%")) | (OnetOccupation.onet_soc_code.ilike(f"%{query}%"))
        )
    occupations = statement.order_by(OnetOccupation.title.asc()).limit(limit).all()
    return jsonify({
        "success": True,
        "query": query,
        "occupations": [
            {"onet_soc_code": item.onet_soc_code, "title": item.title, "provenance": _onet_provenance(item)}
            for item in occupations
        ],
        "fallback": not occupations,
    })


@app.get("/api/occupations/<onet_soc_code>")
def api_occupation_detail(onet_soc_code: str):
    occupation = OnetOccupation.query.filter_by(onet_soc_code=onet_soc_code).first()
    if occupation is None:
        return jsonify({"success": False, "error": "Occupation not found.", "fallback": True}), 404
    from storage import OnetInterest, OnetTask, OnetTechnology
    skills = OnetSkill.query.filter_by(occupation_id=occupation.id).order_by(OnetSkill.name.asc()).all()
    tasks = OnetTask.query.filter_by(occupation_id=occupation.id).order_by(OnetTask.id.asc()).all()
    technologies = OnetTechnology.query.filter_by(occupation_id=occupation.id).order_by(OnetTechnology.name.asc()).all()
    interests = OnetInterest.query.filter_by(occupation_id=occupation.id).order_by(OnetInterest.score.desc()).all()
    return jsonify({
        "success": True,
        "occupation": {
            "onet_soc_code": occupation.onet_soc_code,
            "title": occupation.title,
            "description": occupation.description or "Occupation description is not available in the imported release.",
            "job_zone": occupation.job_zone or "Not available",
            "tasks": [{"task_id": task.task_id, "statement": task.statement} for task in tasks] or [{"task_id": "unavailable", "statement": "Task data is not available in the imported release."}],
            "skills": [{"element_id": skill.element_id, "name": skill.name, "scale_id": skill.scale_id, "value": skill.value} for skill in skills],
            "technology": [{"name": item.name, "category": item.category} for item in technologies] or [{"name": "Technology data unavailable", "category": "Not imported"}],
            "interests_riasec": [{"name": item.name, "score": item.score} for item in interests] or [{"name": "RIASEC data unavailable", "score": None}],
            "provenance": _onet_provenance(occupation),
        },
    })


@app.get("/api/occupations/<onet_soc_code>/compare")
def api_compare_occupations(onet_soc_code: str):
    other_code = clean_text(request.args.get("compare_to") or request.args.get("other"))
    if not other_code:
        return jsonify({"success": False, "error": "compare_to is required."}), 400
    left = OnetOccupation.query.filter_by(onet_soc_code=onet_soc_code).first()
    right = OnetOccupation.query.filter_by(onet_soc_code=other_code).first()
    if left is None or right is None:
        return jsonify({"success": False, "error": "One or both occupations were not found.", "fallback": True}), 404
    left_skills = {item.name for item in OnetSkill.query.filter_by(occupation_id=left.id).all()}
    right_skills = {item.name for item in OnetSkill.query.filter_by(occupation_id=right.id).all()}
    return jsonify({
        "success": True,
        "shared_skills": sorted(left_skills & right_skills),
        "only_left": sorted(left_skills - right_skills),
        "only_right": sorted(right_skills - left_skills),
    })


def _job_skill_breakdown(description: str, resume_text: str) -> dict[str, Any]:
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
    title = clean_text(payload.get("title"))
    description = clean_text(payload.get("description_raw") or payload.get("description"))
    if not title or not description:
        return jsonify({"success": False, "error": "Job title and pasted job description are required."}), 400
    if len(description) > 50000:
        return jsonify({"success": False, "error": "Job description is too long."}), 400
    job = create_job_posting(
        user_id=current_user.id,
        title=title[:200],
        company=clean_text(payload.get("company"))[:160],
        description_raw=description,
        source_url=clean_text(payload.get("source_url"))[:1000],
    )
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
    uploaded = request.files.get("resume_file")
    if uploaded and uploaded.filename:
        name = clean_text(request.form.get("name")) or (uploaded.filename or "Resume version")
        try:
            content = clean_text(parse_resume_file(uploaded))
        except Exception:
            return jsonify({"success": False, "error": "That resume file could not be parsed."}), 400
    else:
        payload = request.get_json(silent=True) or {}
        name = clean_text(payload.get("name")) or "Resume version"
        content = clean_text(payload.get("content_text") or payload.get("resume_text"))
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
    status = clean_text(payload.get("status")) or "Bookmarked"
    if status not in Application.STATUSES:
        return jsonify({"success": False, "error": "Invalid application status."}), 400
    application = create_application(
        user_id=current_user.id,
        job_posting_id=job_id,
        resume_version_id=resume_version_id,
        status=status,
        notes=clean_text(payload.get("notes")),
    )
    return jsonify({"success": True, "application": application_payload(application)}), 201


@app.get("/api/applications/<int:application_id>")
@login_required
def api_get_application(application_id: int):
    application = get_owned_application(current_user.id, application_id)
    if application is None:
        return jsonify({"success": False, "error": "Application not found for the current user."}), 404
    body = application_payload(application)
    body["success"] = True
    return jsonify(body)


@app.delete("/api/applications/<int:application_id>")
@login_required
def api_delete_application(application_id: int):
    application = get_owned_application(current_user.id, application_id)
    if application is None:
        return jsonify({"success": False, "error": "Application not found for the current user."}), 404
    db.session.delete(application)
    db.session.commit()
    log.info("application deleted id=%s", application_id)
    return jsonify({"success": True, "deleted": True})


@app.patch("/api/applications/<int:application_id>")
@login_required
def api_update_application(application_id: int):
    application = get_owned_application(current_user.id, application_id)
    if application is None:
        return jsonify({"success": False, "error": "Application not found for the current user."}), 404
    payload = request.get_json(silent=True) or {}
    payload.pop("user_id", None)
    payload.pop("owner_id", None)
    payload.pop("account_id", None)
    payload.pop("job_posting_id", None)
    payload.pop("target_job_match_id", None)
    status = clean_text(payload.get("status"))
    if status and status not in Application.STATUSES:
        return jsonify({"success": False, "error": "Invalid application status."}), 400
    if status:
        application.status = status
    if "notes" in payload:
        notes = clean_text(payload.get("notes"))
        if len(notes) > 4000:
            return jsonify({"success": False, "error": "Notes are too long. Maximum length is 4000 characters."}), 400
        application.notes = notes
    if "resume_version_id" in payload:
        raw_version = payload.get("resume_version_id")
        if raw_version in (None, ""):
            application.resume_version_id = None
        else:
            try:
                version_id = int(raw_version)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "Resume version is invalid."}), 400
            if get_owned_resume_version(current_user.id, version_id) is None:
                return jsonify({"success": False, "error": "Resume version was not found."}), 404
            application.resume_version_id = version_id
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
    result["comparison_timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot_hash = hashlib.sha256(
        json.dumps({"job": job.content_hash, "resume": version.content_hash, "result": result}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    result["snapshot_hash"] = snapshot_hash
    snapshot = AnalysisSnapshot.query.filter_by(user_id=current_user.id, snapshot_hash=snapshot_hash).first()
    if snapshot is None:
        snapshot = create_analysis_snapshot(
            user_id=current_user.id,
            job_posting_id=job.id,
            resume_version_id=version.id,
            result=result,
            snapshot_hash=snapshot_hash,
        )
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
    return jsonify({
        "success": True,
        "export_format": "pdf",
        "snapshot_locked": True,
        "application": application_payload(application),
        "snapshot": snapshot_payload(snapshot),
    })


@app.get("/privacy")
def privacy() -> str:
    return render_template("privacy.html", active_page="privacy", title="Privacy | Prayash")


@app.get("/insights")
def insights() -> str:
    return render_template("insights.html", active_page="insights", title="Insights | Prayash")


@app.route("/partnerships", methods=["GET", "POST"])
def partnerships() -> str:
    submitted = False
    error = None
    if request.method == "POST":
        org = (request.form.get("organization") or "").strip()
        contact = (request.form.get("contact_email") or "").strip()
        use_case = (request.form.get("use_case") or "").strip()
        if not org or not contact or not use_case:
            error = "All fields are required."
        elif not is_valid_email(contact):
            error = "Please enter a valid email address."
        else:
            log.info("Partnership inquiry received from %s", contact)
            create_partnership_request(organization=org, contact_email=contact, use_case=use_case)
            submitted = True
    return render_template(
        "partnerships.html",
        active_page="partnerships",
        title="Partnerships | Prayash",
        submitted=submitted,
        error=error,
    )


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_dashboard() -> str:
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        user = authenticate_user(username, password)
        if user and getattr(user, "is_admin_email", False):
            login_user(user, remember=True)
            return redirect(url_for("admin_dashboard"))
        return render_template(
            "admin.html",
            title="Admin | Prayash",
            active_page="admin",
            requires_login=True,
            login_error="Invalid admin credentials.",
            metrics={},
            chart_data=None,
        )

    if not getattr(current_user, "is_admin_email", False):
        return render_template(
            "admin.html",
            title="Admin | Prayash",
            active_page="admin",
            requires_login=True,
            login_error=None,
            metrics={},
            chart_data=None,
        )

    metrics = get_detailed_metrics()
    chart_data = {
        "modeLabels": ["Standard", "Advanced"],
        "modeValues": [metrics["mode_counts"]["standard"], metrics["mode_counts"]["advanced"]],
        "riskLabels": ["Low", "Moderate", "Elevated"],
        "riskValues": [metrics["risk_buckets"]["low"], metrics["risk_buckets"]["moderate"], metrics["risk_buckets"]["elevated"]],
    }
    users = get_all_users()
    return render_template(
        "admin.html",
        title="Admin | Prayash",
        active_page="admin",
        requires_login=False,
        metrics=metrics,
        chart_data=chart_data,
        users=users,
    )


# ── Admin API ────────────────────────────────────────────────────────

@app.get("/api/admin/users")
@login_required
def api_admin_users():
    """Return all users for the admin panel (JSON)."""
    if not getattr(current_user, "is_admin_email", False):
        return jsonify({"success": False, "error": "Admin access required."}), 403
    users = get_all_users()
    user_list = []
    for u in users:
        user_list.append({
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "email_verified": u.email_verified,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
        })
    verified = sum(1 for u in users if u.email_verified)
    return jsonify({
        "success": True,
        "users": user_list,
        "total": len(users),
        "verified": verified,
        "unverified": len(users) - verified,
    })


@app.post("/admin/logout")
@login_required
def admin_logout() -> Any:
    logout_user()
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password() -> str:
    error = None
    sent = False

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if not email or not is_valid_email(email):
            error = "Enter a valid email address."
        else:
            user = get_user_by_email(email)
            if user:
                reset_token = create_password_reset_token(user)
                log.info(
                    "Password reset requested for %s. Token: %s",
                    email, reset_token.token,
                )
            # Always show success to prevent email enumeration
            sent = True

    return render_template(
        "forgot_password.html",
        active_page="",
        title="Forgot Password | Prayash",
        error=error,
        sent=sent,
    )


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str) -> str:
    error = None
    success = False

    user = verify_reset_token(token)
    if not user:
        return render_template(
            "forgot_password.html",
            active_page="",
            title="Invalid Link | Prayash",
            error="This password reset link is invalid or has expired.",
            sent=False,
            invalid_token=True,
        )

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        strength_error = validate_password_strength(password)
        if strength_error:
            error = strength_error
        elif password != confirm:
            error = "Passwords do not match."
        else:
            update_user_password(user, password)
            consume_reset_token(token)
            log.info("Password reset successful for %s", user.email)
            success = True

    return render_template(
        "reset_password.html",
        active_page="",
        title="Reset Password | Prayash",
        error=error,
        success=success,
        token=token,
    )


# ── Auth Assistant API ──
# Context-aware conversational guidance endpoint
# Currently returns static contextual tips; can be extended with NLP/LLM

_AUTH_ASSISTANT_KNOWLEDGE = {
    "login": {
        "description": "Sign in to your Prayash account",
        "tips": [
            "Enter the email or username you used when signing up.",
            "Passwords are case-sensitive. Check that Caps Lock is off!",
            "Can't remember your password? Use the 'Forgot password?' link below.",
            "Having trouble? Try signing in with Google or GitHub instead.",
        ],
        "alternatives": ["google", "github", "linkedin"],
        "security": "🔒 Always verify you're on the official Prayash site before entering credentials.",
    },
    "signup": {
        "description": "Create your free Prayash account",
        "tips": [
            "Use your real name — it'll appear on your profile.",
            "Your username must be at least 4 characters. Use letters, numbers, and underscores.",
            "Use an email you have access to — you'll need to verify it!",
            "Create a strong password: 8+ chars, uppercase, lowercase, number, and special character.",
            "Adding a phone number is optional but helps with account recovery.",
        ],
        "alternatives": ["google", "github", "linkedin"],
        "security": "🔒 Your password is hashed and salted. We never store plain-text passwords.",
    },
    "verify": {
        "description": "Verify your email address with a 6-digit code",
        "tips": [
            "Check your inbox for the 6-digit verification code.",
            "The code expires in 10 minutes — don't wait too long!",
            "Check your Spam or Promotions folder if you don't see the email.",
            "You can request a new code after 30 seconds.",
        ],
        "alternatives": [],
        "security": "🔒 Never share your verification code with anyone. Prayash will never call or text you for it.",
    },
    "forgot": {
        "description": "Reset your password via email",
        "tips": [
            "Enter the email address associated with your Prayash account.",
            "Check your inbox (and Spam folder) for the reset code.",
            "The reset code expires in 10 minutes for your security.",
            "If you signed up with Google/GitHub, try signing in that way instead!",
        ],
        "alternatives": ["google", "github"],
        "security": "🔒 If you didn't request a password reset, you can safely ignore the email.",
    },
    "forgot_otp": {
        "description": "Enter the password reset code sent to your email",
        "tips": [
            "Enter the 6-digit code from your email.",
            "Check Spam / Promotions if you don't see the email.",
            "The code expires in 10 minutes.",
            "You can go back to request a new code if needed.",
        ],
        "alternatives": [],
        "security": "🔒 Password reset codes are single-use. Each new request invalidates the previous code.",
    },
    "reset": {
        "description": "Create a new password for your account",
        "tips": [
            "Choose a password you haven't used before on Prayash.",
            "Make it at least 8 characters with uppercase, lowercase, a number, and a special character.",
            "Try a passphrase like 'Correct-Horse-Battery-$42' — memorable AND strong!",
            "After resetting, log out of other devices if you think someone else had access.",
        ],
        "alternatives": [],
        "security": "🔒 Consider using a password manager like Bitwarden or iCloud Keychain to store your new password safely.",
    },
}


@app.get("/api/auth-assistant/context")
@rate_limit
def api_auth_assistant_context():
    """Return contextual tips and guidance for the auth assistant."""
    page = request.args.get("page", "login").strip().lower()
    if page not in _AUTH_ASSISTANT_KNOWLEDGE:
        page = "login"
    context = dict(_AUTH_ASSISTANT_KNOWLEDGE[page])
    context["page"] = page
    return jsonify({"success": True, "context": context})


@app.get("/api/rag-status")
@rate_limit
def api_rag_status():
    """RAG pipeline performance monitoring endpoint.

    SAHAY_AI-inspired: mirrors their ``/performance`` view which shows
    RAG cache info, model status, and response metrics.

    Returns:
        JSON with cache status, model info, and uptime.
    """
    return jsonify({
        "success": True,
        "rag_service": rag_service.get_status(),
        "active_sessions": len(_CAREER_CHAT_SESSIONS),
        "rate_limit_window": _RATE_LIMIT_WINDOW,
        "rate_limit_max": _RATE_LIMIT_MAX_REQUESTS,
    })


@app.get("/healthz")
def healthz() -> tuple[dict[str, str], int]:
    # Quick check that model artifacts are loadable
    from risk_assessor import load_artifacts
    try:
        bundle, courses = load_artifacts()
        ml_ok = bool(bundle) and bool(courses)
    except Exception:
        ml_ok = False
    return {
        "status": "ok",
        "version": _get_cache_bust_hash(),
        "ml_pipeline": "ready" if ml_ok else "unavailable",
    }, 200


# ── CSRF Token endpoint ──
@app.get("/api/csrf-token")
def api_csrf_token():
    return jsonify({"csrf_token": generate_csrf()})


# ── Password Strength Checker ──
@app.post("/api/check-password")
@rate_limit
def api_check_password():
    data = request.get_json(silent=True) or {}
    pw = (data.get("password") or "").strip()
    if not pw:
        return jsonify({"score": 0, "label": "Empty", "color": "var(--error)"})
    score = 0
    if len(pw) >= 8: score += 1
    if len(pw) >= 12: score += 1
    if any(c.isupper() for c in pw): score += 1
    if any(c.islower() for c in pw): score += 1
    if any(c.isdigit() for c in pw): score += 1
    if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in pw): score += 1
    labels = ["Very weak", "Weak", "Fair", "Good", "Strong", "Very strong"]
    colors = ["var(--error)", "var(--error)", "#eab308", "#22c55e", "#22c55e", "#16a34a"]
    widths = ["16%", "33%", "50%", "66%", "83%", "100%"]
    idx = min(score, 5)
    return jsonify({"score": score, "label": labels[idx], "color": colors[idx], "width": widths[idx]})


# ── Custom Error Handlers ──
@app.errorhandler(404)
def not_found(_error: Any) -> tuple[str, int]:
    return render_template("404.html", active_page="", title="404 | Prayash"), 404


@app.errorhandler(500)
def server_error(_error: Any) -> tuple[str, int]:
    log.exception("Internal server error")
    return render_template("500.html", active_page="", title="500 | Prayash"), 500


@app.errorhandler(413)
def request_entity_too_large(_error: Any) -> tuple[Any, int]:
    return jsonify({"success": False, "error": "File too large. Maximum size is 8 MB."}), 413


@app.after_request
def add_security_headers(response):
    # Allow service worker scope from static folder
    if request.path == "/static/sw.js":
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    # Security headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-XSS-Protection", "0")  # Deprecated but harmless
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    nonce = getattr(g, "csp_nonce", secrets.token_urlsafe(16))
    response.headers.setdefault("Content-Security-Policy", _make_csp(nonce))
    # Dynamic responses include sessions, CSRF tokens, private JSON and streams.
    # The worker independently refuses to cache any of these responses.
    if request.endpoint != "static" or response.status_code >= 400:
        response.headers["Cache-Control"] = "private, no-store"
    elif request.path == "/static/offline.html":
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    # Cache static assets aggressively
    elif request.path.startswith("/static/") and not request.path.endswith(".html"):
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    return response


@app.post("/api/feedback")
@rate_limit
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
        education_actions.insert(0, "Prioritize transferable digital and analytical skills as career-development actions.")
    elif risk_label.lower() == "low":
        education_actions.insert(0, "Deepen specialization in your strongest areas.")
    else:
        education_actions.insert(0, "Build adjacent skills that improve role flexibility.")

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
            "Prayash runs local ML for historical occupation reference, role match, E0/E1/E2 task retrieval, roadmap, and RIASEC fit.",
            "Advanced mode adds optional local Ollama explanation while preserving deterministic outputs.",
        ],
        "what_your_report_means": [
            f"Historical occupation reference band: {risk_label}. Occupation-level only; not a personal job-loss probability.",
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


def _run_analysis_workflow(
    resume_text: str,
    mode: str,
    *,
    confirmed_occupation_code: str | None = None,
    confirmation_method: str | None = None,
) -> dict[str, Any]:
    """Run the full analysis pipeline.

    Model artifacts are expected to have been prepared at startup via
    ``ensure_model_artifacts()``.  If the artifacts are missing the
    analysis will raise ``RuntimeError``, which the caller should handle.
    """
    analysis = assess_resume(
        resume_text,
        mode=mode,
        confirmed_occupation_code=confirmed_occupation_code,
        confirmation_method=confirmation_method,
    )
    analysis.setdefault("guided_next_steps", _build_guided_next_steps(analysis))
    analysis.setdefault("support_resources", _build_support_resources())
    analysis.setdefault("report_guide", _build_report_guide(analysis))
    return analysis


# ── SSE: Real-time analysis streaming ──
@app.get("/api/analyze-stream")
@rate_limit
def api_analyze_stream():
    text = request.args.get("text", "").strip()
    mode = request.args.get("mode", "standard") or "standard"
    if mode not in {"standard", "advanced"}: mode = "standard"
    if not text or len(text.strip()) < 20:
        return jsonify({"success": False, "error": "Resume text is required."}), 400

    def generate() -> Generator[str, None, None]:
        aid = uuid.uuid4().hex[:8]
        def emit(step: str, status: str, pct: int, data: dict | None = None):
            yield f"data: {json.dumps({'id': aid, 'step': step, 'status': status, 'percent': pct, 'data': data})}\n\n"
        yield from emit("init", "Starting analysis...", 0)
        try:
            yield from emit("parse", "Parsing resume text...", 10)
            analysis = _run_analysis_workflow(text, mode)
            yield from emit("risk", "Computing historical occupation reference...", 40)
            yield from emit("roles", "Matching to O*NET roles...", 60)
            yield from emit("roadmap", "Generating learning roadmap...", 80)
            if mode == "advanced":
                yield from emit("llama", "Running Llama 3 narrative...", 95)
            record_upload(
                filename="streamed_resume.txt",
                file_type="text",
                mode=mode,
                risk_score=analysis.get("risk_score", 0.0),
                risk_label=analysis.get("risk_label", "Low"),
                reasoning=analysis.get("reasoning", {}),
                user_id=current_user.id if current_user.is_authenticated else None,
            )
            analysis.update({"success": True})
            yield from emit("complete", "Analysis complete!", 100, _attach_occupation_pending(analysis))
        except Exception as exc:
            log.exception("Stream analysis failed")
            yield from emit("error", str(exc), -1, {"error": str(exc)})
    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _attach_occupation_pending(analysis: dict[str, Any]) -> dict[str, Any]:
    occ = analysis.get("occupation_match") or analysis.get("occupation_candidate") or {}
    bound = attach_pending_analysis(
        session,
        candidate_code=occ.get("candidate_code"),
        candidate_title=occ.get("candidate_title"),
        matcher_score=occ.get("matcher_score", occ.get("confidence")),
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    analysis["analysis_id"] = bound["analysis_id"]
    analysis["candidate_id"] = bound["candidate_id"]
    return analysis


def _authorization_response(exc: AuthorizationError):
    body = {
        "success": False,
        "error": exc.message,
        "error_code": exc.code,
        "status": exc.extra.get("status") or "error",
    }
    body.update({key: value for key, value in exc.extra.items() if key != "status"})
    if exc.code == "allowlist_unavailable":
        status_code = 503
    elif exc.code in {
        "analysis_not_owned",
        "candidate_not_owned",
        "candidate_consumed",
        "analysis_expired",
    }:
        status_code = 403
    else:
        status_code = 400
    return jsonify(body), status_code


@app.get("/api/occupations/selectable")
@rate_limit
def api_occupations_selectable():
    try:
        occupations = selectable_occupations()
        stats = allowlist_inventory()
    except AuthorizationError as exc:
        return _authorization_response(exc)
    return jsonify(
        {
            "success": True,
            "occupations": occupations,
            "count": len(occupations),
            "inventory": {
                "source_rows": stats["source_rows"],
                "unique_source_codes": stats["unique_source_codes"],
                "duplicates": stats["duplicates"],
                "benchmark_covered_codes": stats["benchmark_covered_codes"],
                "benchmark_uncovered_codes": stats["benchmark_uncovered_codes"],
                "selectable_codes": stats["selectable_codes"],
            },
        }
    )


@rate_limit
def _handle_upload_request():
    payload = request.get_json(silent=True) if request.is_json else {}
    resume_text = request.form.get("resume_text") or (payload or {}).get("resume_text", "")
    mode = request.form.get("mode") or (payload or {}).get("mode", "standard")
    uploaded_file = request.files.get("resume_file")

    if uploaded_file and uploaded_file.filename:
        resume_text = parse_resume_file(uploaded_file)

    resume_text = clean_text(resume_text)
    mode = clean_text(mode).lower() or "standard"

    if not resume_text:
        return jsonify({"success": False, "error": "Upload a resume or paste resume text first."}), 400

    if mode not in {"standard", "advanced"}:
        mode = "standard"

    try:
        analysis = _run_analysis_workflow(resume_text, mode)
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
        return jsonify(_attach_occupation_pending(analysis))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.post("/api/upload")
def api_upload():
    return _handle_upload_request()


@app.post("/api/analyze")
def api_analyze():
    return _handle_upload_request()


@app.post("/api/confirm-occupation")
@rate_limit
def api_confirm_occupation():
    data = request.get_json(silent=True) if request.is_json else {}
    data = data or {}
    action = clean_text(data.get("action") or "confirm_candidate").lower() or "confirm_candidate"
    if action != "confirm_candidate":
        return jsonify({"success": False, "error": "action must be confirm_candidate"}), 400
    try:
        result = confirm_server_candidate(
            session,
            analysis_id=clean_text(data.get("analysis_id") or ""),
            candidate_id=clean_text(data.get("candidate_id") or ""),
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        return jsonify(result)
    except AuthorizationError as exc:
        return _authorization_response(exc)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.post("/api/select-occupation")
@rate_limit
def api_select_occupation():
    data = request.get_json(silent=True) if request.is_json else {}
    data = data or {}
    action = clean_text(data.get("action") or "select_occupation").lower() or "select_occupation"
    if action != "select_occupation":
        return jsonify({"success": False, "error": "action must be select_occupation"}), 400
    try:
        result = select_supported_occupation(
            session,
            analysis_id=clean_text(data.get("analysis_id") or ""),
            selected_code=clean_text(data.get("selected_code") or ""),
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        return jsonify(result)
    except AuthorizationError as exc:
        return _authorization_response(exc)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ── Comparison Mode ──
# ── Skills Gap Analysis Endpoint ──────────────────────────────────

@app.get("/api/skills-gap/roles")
@rate_limit
def api_skills_gap_roles():
    """Return the list of available target roles for skill gap analysis."""
    return jsonify({"success": True, "roles": get_available_roles()})


@app.post("/api/skills-gap/analyze")
@rate_limit
def api_skills_gap_analyze():
    """Analyze skills gap between resume skills and a target role."""
    data = request.get_json(silent=True) if request.is_json else {}
    resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
    target_role = (request.form.get("target_role") or data.get("target_role", "")).strip()

    if not resume_text or len(resume_text) < 20:
        return jsonify({"success": False, "error": "Resume text is required (min 20 characters)."}), 400
    if not target_role:
        return jsonify({"success": False, "error": "Target role is required."}), 400

    cleaned_text = clean_text(resume_text)

    result = analyze_skills_gap(cleaned_text, target_role)
    if "error" in result:
        return jsonify({"success": False, "error": result["error"], "available_roles": result.get("available_roles", [])}), 400

    return jsonify({"success": True, "analysis": result})


# ── Career Paths API ────────────────────────────────────────────────

@app.post("/api/career-paths")
@rate_limit
def api_career_paths():
    """Suggest career paths based on resume skills."""
    data = request.get_json(silent=True) if request.is_json else {}
    resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
    if not resume_text or len(resume_text) < 20:
        return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400
    paths = suggest_career_paths(resume_text)
    return jsonify({"success": True, "paths": paths, "total": len(paths)})


# ── Learning Roadmap API ────────────────────────────────────────────

@app.post("/api/learning-roadmap")
@rate_limit
def api_learning_roadmap():
    """Generate a structured learning roadmap based on resume skills."""
    data = request.get_json(silent=True) if request.is_json else {}
    resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
    if not resume_text or len(resume_text) < 20:
        return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400
    roadmap = generate_learning_roadmap(resume_text)
    total_weeks = sum(
        int(s.get("duration", "0").split("-")[0] or "0")
        for area in roadmap
        for s in area.get("stages", [])
    )
    return jsonify({"success": True, "roadmap": roadmap, "areas": len(roadmap), "total_weeks": total_weeks})


# ── Career Chat API (SAHAY_AI-inspired AI career advisor) ───────
# Lightweight conversational AI using the existing Ollama pipeline.
# Maintains per-session conversation history for context-aware guidance.

# ── Career Chat Session Management (with TTL-based cleanup) ──

_CAREER_CHAT_SESSIONS: dict[str, list[dict[str, str]]] = {}
"""In-memory conversation history per session ID.
Structure: {session_id: [{"role": "user"|"assistant", "content": str}, ...]}"""

_CAREER_CHAT_LAST_ACTIVE: dict[str, float] = {}
"""Tracks the last active timestamp (time.time) for each session ID.
Used by _cleanup_stale_career_sessions() to evict idle sessions."""

_CAREER_CHAT_TTL = 1800  # 30 minutes in seconds


def _cleanup_stale_career_sessions() -> None:
    """Remove sessions that have been idle for longer than _CAREER_CHAT_TTL.
    Call this before any career-chat session lookup to keep the in-memory
    store from accumulating stale entries."""
    now = time.time()
    stale = [
        sid for sid, last_active in _CAREER_CHAT_LAST_ACTIVE.items()
        if now - last_active > _CAREER_CHAT_TTL
    ]
    for sid in stale:
        _CAREER_CHAT_SESSIONS.pop(sid, None)
        _CAREER_CHAT_LAST_ACTIVE.pop(sid, None)
    if stale:
        log.debug("Cleaned up %d stale career chat session(s)", len(stale))


def _rule_based_career_answer(question: str) -> str:
    """Rule-based fallback answer for the career chat when no LLM is available.

    Order matters — more specific topics are matched first so that, e.g.,
    "Tips for job interviews?" returns interview advice rather than the generic
    job-search answer, and "Help me plan my career path" gets dedicated
    career-path guidance instead of the same job-search text.
    """
    q = (question or "").lower()

    def has_any(keywords: list[str]) -> bool:
        # Word-boundary prefix match: "skill" matches "skills" and "learning"
        # matches "learn", but "earn" never matches inside "learn" or "bearn".
        return any(re.search(rf"\b{re.escape(kw)}", q) for kw in keywords)

    if has_any(["interview", "mock", "crack", "behavioral"]):
        return (
            "To prepare for interviews: 1) Review common questions for your target role, "
            "2) Prepare STAR-format stories from your experience, "
            "3) Practice technical questions with platforms like LeetCode or HackerRank, "
            "4) Research the company's culture and recent news, "
            "5) Do mock interviews with friends or platforms like Pramp, "
            "6) Prepare thoughtful questions to ask the interviewer."
        )
    if has_any(["salary", "pay", "earn", "compensation", "negotiate"]):
        return (
            "Salary ranges vary by location, experience, and industry. "
            "Use sites like Glassdoor, Levels.fyi, and LinkedIn Salary to research "
            "market rates for your target roles. Consider total compensation including "
            "benefits, equity, and bonuses."
        )
    if has_any(["resume", "cv", "ats", "achievement"]):
        return (
            "To improve your resume: 1) Add specific, quantifiable achievements, "
            "2) Use keywords from target job descriptions, "
            "3) Include a professional summary section, "
            "4) Keep your format clean and ATS-friendly (PDF recommended), "
            "5) Ensure your contact info (email, LinkedIn) is clearly visible."
        )
    if has_any(["career", "path", "roadmap", "growth", "goal"]):
        return (
            "Let's map out your career path: 1) Review the top role matches from your "
            "analysis report to see where your profile fits today, "
            "2) Identify the skills you'll need for your target role, "
            "3) Follow the learning roadmap in your report to close skill gaps, "
            "4) Set 3-month and 12-month goals with measurable milestones, "
            "5) Re-run your analysis after each milestone to track progress. "
            "Want me to suggest specific courses or roles to explore?"
        )
    if has_any(["job", "apply", "position", "hiring", "search", "role"]):
        return (
            "For job searching, use your top role matches from the analysis as search keywords. "
            "Tailor your resume summary to highlight the skills most relevant to your target role. "
            "Consider setting up job alerts for your strongest matching positions."
        )
    if has_any(["skill", "learn", "study", "course", "improve"]):
        return (
            "Based on your resume analysis, I recommend focusing on skill development. "
            "Check the learning roadmap in your analysis report for personalized course recommendations. "
            "Start with the top suggested Coursera courses for your skill gaps."
        )
    if has_any(["hello", "hi", "hey", "help"]):
        return (
            "Hi! I'm your AI career assistant. I can help with:\n"
            "• Skill development and learning recommendations\n"
            "• Job search strategies and career advice\n"
            "• Resume improvement tips\n"
            "• Interview preparation\n"
            "• Salary and compensation questions\n"
            "What would you like to know?"
        )
    return (
        "That's a great question! For more personalized advice, "
        "try running a resume analysis first to get tailored recommendations. "
        "To unlock AI-powered career guidance, set your DeepSeek or OpenAI API key "
        "in the server environment variables."
    )


@app.post("/api/career-chat")
@rate_limit
def api_career_chat():
    """
    AI Career Chat endpoint (SAHAY_AI-inspired).
    Accepts a user question and optional resume context, returns AI-generated career advice.
    Uses Ollama when available, falls back to a rule-based response.
    """
    data = request.get_json(silent=True) or {}
    question = (data.get("message") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    resume_text = (data.get("resume_text") or "").strip()

    if not question:
        return jsonify({"success": False, "error": "Please enter a question."}), 400

    # Clean stale sessions before looking up/creating the current one
    _cleanup_stale_career_sessions()

    # Create or retrieve session
    if not session_id:
        session_id = str(uuid.uuid4())

    if session_id not in _CAREER_CHAT_SESSIONS:
        _CAREER_CHAT_SESSIONS[session_id] = []

    # Track this session's last-active timestamp
    _CAREER_CHAT_LAST_ACTIVE[session_id] = time.time()

    history = _CAREER_CHAT_SESSIONS[session_id]

    # Limit history to last 10 messages to manage context window
    recent_history = history[-10:] if len(history) > 10 else history

    # Try Ollama for AI-powered response (same pipeline as Advanced mode).
    # Ollama is optional: connection, timeout, HTTP, and payload failures fall
    # through to the configured API provider and then the local rule-based answer.
    ollama_host = (os.environ.get("OLLAMA_HOST") or "http://localhost:11434").strip()
    ollama_model = (os.environ.get("OLLAMA_MODEL") or "llama3").strip()
    llm_available = False
    answer = ""
    system_prompt = (
        "You are a helpful AI career advisor assistant. "
        "Answer career-related questions concisely and practically. "
        "Give specific, actionable advice based on the user's resume and question."
    )

    # If Ollama is running, use it
    try:

        # Build RAG-enhanced context from resume if provided
        context_parts = [system_prompt]
        if resume_text:
            rag_context, _rag_meta = build_rag_context(
                resume_text, question, top_k=3, max_context_chars=1500, session_id=session_id
            )
            if rag_context:
                context_parts.append(f"\n{rag_context}")
            else:
                context_parts.append(f"\nUser's resume context:\n{resume_text[:2000]}")

        # Add recent conversation history
        if recent_history:
            context_parts.append("\nConversation history:")
            for msg in recent_history[-6:]:  # Last 6 messages for relevance
                role_label = "User" if msg["role"] == "user" else "Assistant"
                context_parts.append(f"{role_label}: {msg['content'][:500]}")

        context_parts.append(f"\nUser question: {question}")
        context_parts.append("\nAssistant:")
        full_prompt = "\n".join(context_parts)

        resp = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": ollama_model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": 0.3, "max_length": 300},
            },
            timeout=30,
        )
        if resp.ok:
            result = resp.json()
            if isinstance(result, dict):
                answer = (result.get("response") or "").strip()
                llm_available = bool(answer)
            else:
                log.warning("Ollama career chat returned a non-object response")
        else:
            log.warning("Ollama career chat returned HTTP %s", resp.status_code)
    except Exception as exc:
        log.warning("Ollama career chat unavailable (%s)", type(exc).__name__)
    # ── Try API Key Provider (DeepSeek / OpenAI) as second LLM tier ──
    if not llm_available:
        try:
            _llm_provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
            _deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
            _openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
            _openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

            # Determine which provider to use
            _api_key = None
            _base_url = None
            _model = None

            if _llm_provider == "openrouter" and _openrouter_key:
                _api_key = _openrouter_key
                _base_url = "https://openrouter.ai/api/v1"
                _model = os.environ.get("LLM_MODEL", "openai/gpt-4o")
            elif _llm_provider == "deepseek" and _deepseek_key:
                _api_key = _deepseek_key
                _base_url = "https://api.deepseek.com/v1"
                _model = os.environ.get("LLM_MODEL", "deepseek-chat")
            elif _llm_provider == "openai" and _openai_key:
                _api_key = _openai_key
                _base_url = "https://api.openai.com/v1"
                _model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
            elif not _llm_provider and _openrouter_key:
                _api_key = _openrouter_key
                _base_url = "https://openrouter.ai/api/v1"
                _model = os.environ.get("LLM_MODEL", "openai/gpt-4o")
            elif not _llm_provider and _deepseek_key:
                _api_key = _deepseek_key
                _base_url = "https://api.deepseek.com/v1"
                _model = os.environ.get("LLM_MODEL", "deepseek-chat")
            elif not _llm_provider and _openai_key:
                _api_key = _openai_key
                _base_url = "https://api.openai.com/v1"
                _model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

            if _api_key and _HAS_OPENAI:
                # Build optional default headers (used by OpenRouter for analytics)
                _default_headers: dict[str, str] = {}
                if os.environ.get("OPENROUTER_SITE_URL"):
                    _default_headers["HTTP-Referer"] = os.environ["OPENROUTER_SITE_URL"]
                if os.environ.get("OPENROUTER_SITE_NAME"):
                    _default_headers["X-Title"] = os.environ["OPENROUTER_SITE_NAME"]

                _client = _openai_module.OpenAI(
                    api_key=_api_key,
                    base_url=_base_url,
                    default_headers=_default_headers or None,
                )

                # Build message list with system prompt, resume, history, and question
                _messages: list[dict[str, str]] = [
                    {"role": "system", "content": system_prompt}
                ]
                if resume_text:
                    rag_context, _rag_meta = build_rag_context(
                        resume_text, question, top_k=3, max_context_chars=1500
                    )
                    _messages.append({
                        "role": "system",
                        "content": rag_context if rag_context else f"User's resume context:\n{resume_text[:2000]}"
                    })
                for _msg in recent_history[-6:]:
                    _messages.append({
                        "role": _msg["role"],
                        "content": _msg["content"][:500]
                    })
                _messages.append({"role": "user", "content": question})

                _completion = _client.chat.completions.create(
                    model=_model,
                    messages=_messages,
                    temperature=0.3,
                    max_tokens=300,
                    timeout=30,
                )
                _api_answer = (_completion.choices[0].message.content or "").strip()
                if _api_answer:
                    answer = _api_answer
                    llm_available = True
                    # Resolve provider name for logging (handles auto-detection)
                    _provider_name = (
                        _llm_provider
                        or (_openrouter_key and "openrouter")
                        or (_deepseek_key and "deepseek")
                        or (_openai_key and "openai")
                        or "unknown"
                    )
                    _log_openai.info(
                        "Career chat via %s (%s), session=%s",
                        _provider_name,
                        _model,
                        session_id,
                    )
        except Exception as _llm_err:
            _log_openai.warning("API provider (%s) failed (%s)", _llm_provider or "auto", type(_llm_err).__name__)

    # ── Fallback: rule-based response when no LLM is available ──
    if not llm_available:
        answer = _rule_based_career_answer(question)

    # Store in conversation history
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})

    # Trim history to prevent memory growth
    if len(history) > 50:
        _CAREER_CHAT_SESSIONS[session_id] = history[-50:]

    return jsonify({
        "success": True,
        "reply": answer,
        "answer": answer,
        "session_id": session_id,
        "llm_powered": llm_available,
    })


# ── Insights Summary API ────────────────────────────────────────────


# Career Chat Streaming SSE Endpoint

@app.post("/api/career-chat/stream")
@rate_limit
def api_career_chat_stream():
    """Streaming SSE endpoint for AI Career Chat.
    Accepts the same input as POST /api/career-chat but streams tokens
    back as server-sent events using the OpenRouter API."""
    data = request.get_json(silent=True) or {}
    question = (data.get("message") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    resume_text = (data.get("resume_text") or "").strip()

    if not question:
        return jsonify({"success": False, "error": "Please enter a question."}), 400

    _cleanup_stale_career_sessions()

    if not session_id:
        session_id = str(uuid.uuid4())

    if session_id not in _CAREER_CHAT_SESSIONS:
        _CAREER_CHAT_SESSIONS[session_id] = []

    _CAREER_CHAT_LAST_ACTIVE[session_id] = time.time()
    history = _CAREER_CHAT_SESSIONS[session_id]
    recent_history = history[-10:] if len(history) > 10 else history

    system_prompt = (
        "You are Prayash, a helpful AI career advisor assistant. "
        "Answer career-related questions concisely and practically. "
        "Give specific, actionable advice based on the user's resume and question."
    )

    def generate():
        def sse(event, data_dict):
            yield f"event: {event}\ndata: {json.dumps(data_dict)}\n\n"

        full_answer = ""

        try:
            # Try OpenRouter via OpenAI SDK with streaming
            if _HAS_OPENAI:
                _api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
                _llm_provider = os.environ.get("LLM_PROVIDER", "").strip().lower()

                if _llm_provider or _api_key:
                    _base_url = "https://openrouter.ai/api/v1"
                    _model = os.environ.get("LLM_MODEL", "anthropic/claude-opus-5-fast")

                    _default_headers = {}
                    if os.environ.get("OPENROUTER_SITE_URL"):
                        _default_headers["HTTP-Referer"] = os.environ["OPENROUTER_SITE_URL"]
                    if os.environ.get("OPENROUTER_SITE_NAME"):
                        _default_headers["X-Title"] = os.environ["OPENROUTER_SITE_NAME"]

                    _client = _openai_module.OpenAI(
                        api_key=_api_key,
                        base_url=_base_url,
                        default_headers=_default_headers or None,
                    )

                    _messages = [
                        {"role": "system", "content": system_prompt}
                    ]
                    if resume_text:
                        rag_context, _rag_meta = build_rag_context(
                            resume_text, question, top_k=3, max_context_chars=1500
                        )
                        _messages.append({
                            "role": "system",
                            "content": rag_context if rag_context else f"User's resume context:\n{resume_text[:2000]}"
                        })
                    for _msg in recent_history[-6:]:
                        _messages.append({
                            "role": _msg["role"],
                            "content": _msg["content"][:500]
                        })
                    _messages.append({"role": "user", "content": question})

                    yield from sse("meta", {"session_id": session_id})

                    _stream = _client.chat.completions.create(
                        model=_model,
                        messages=_messages,
                        temperature=0.3,
                        max_tokens=400,
                        stream=True,
                        timeout=30,
                    )

                    for _chunk in _stream:
                        _delta = _chunk.choices[0].delta if _chunk.choices else None
                        if _delta and _delta.content:
                            full_answer += _delta.content
                            yield from sse("token", {"content": _delta.content})

                    yield from sse("done", {"answer": full_answer, "session_id": session_id})
                    log.info("Streaming career chat via OpenRouter (%s), session=%s", _model, session_id)
                    return

        except Exception as exc:
            log.warning("Streaming career chat failed (%s)", type(exc).__name__)

        # Fallback: rule-based answer (sent as one event)
        full_answer = _rule_based_career_answer(question)

        yield from sse("meta", {"session_id": session_id})
        yield from sse("token", {"content": full_answer})
        yield from sse("done", {"answer": full_answer, "session_id": session_id})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/insights-summary")
@rate_limit
def api_insights_summary():
    """Get a full insights summary: parsed data, career paths, roadmap."""
    data = request.get_json(silent=True) if request.is_json else {}
    resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
    if not resume_text or len(resume_text) < 20:
        return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400

    parsed = parse_resume_enhanced(resume_text)
    quality = analyze_resume_quality(parsed)
    skills = extract_skills_from_text(resume_text)
    paths = suggest_career_paths(resume_text)
    roadmap = generate_learning_roadmap(resume_text)
    try:
        layered = assess_resume(resume_text, mode="standard")
    except Exception:
        layered = {}
    total_weeks = sum(
        int(s.get("duration", "0").split("-")[0] or "0")
        for area in roadmap
        for s in area.get("stages", [])
    )
    skill_categories = skills.get("by_category", {})
    top_skills_sample = skills.get("all_skills", [])[:20]

    return jsonify({
        "success": True,
        "skills": {
            "count": skills.get("count", 0),
            "categories": len(skill_categories),
            "by_category": skill_categories,
            "top_skills": top_skills_sample,
        },
        "quality": {
            "score": quality.get("completeness_score", 0),
            "grade": quality.get("grade", "N/A"),
            "strengths": quality.get("strengths", []),
            "missing": quality.get("missing_sections", []),
        },
        "parsed": {
            "sections_found": parsed.get("sections_found", []),
            "contact": bool(parsed.get("contact", {})),
            "education": len(parsed.get("education", [])),
            "experience": len(parsed.get("experience", [])),
            "projects": len(parsed.get("projects", [])),
        },
        "career_paths": {"paths": paths, "total": len(paths)},
        "learning_roadmap": {"roadmap": roadmap, "areas": len(roadmap), "total_weeks": total_weeks},
        "occupation_candidate": layered.get("occupation_candidate"),
        "occupation_match": layered.get("occupation_match"),
        "historical_occupation_reference": layered.get("historical_occupation_reference"),
        "task_exposure": layered.get("task_exposure"),
        "contextual_task_exposure": layered.get("contextual_task_exposure"),
    })


@app.post("/api/compare")
@rate_limit
def api_compare():
    payload = request.get_json(silent=True) if request.is_json else {}
    a = (request.form.get("text_a") or (payload or {}).get("text_a", "")).strip()
    b = (request.form.get("text_b") or (payload or {}).get("text_b", "")).strip()
    mode = (request.form.get("mode") or (payload or {}).get("mode", "standard") or "standard")
    if mode not in {"standard", "advanced"}: mode = "standard"
    if not a or not b: return jsonify({"success": False, "error": "Both texts required"}), 400
    try:
        ra = _run_analysis_workflow(a, mode)
        rb = _run_analysis_workflow(b, mode)
        dist_a = (ra.get("task_exposure") or {}).get("distribution")
        dist_b = (rb.get("task_exposure") or {}).get("distribution")
        exposure_delta = None
        if isinstance(dist_a, dict) and isinstance(dist_b, dict):
            exposure_delta = {
                key: round(float(dist_a.get(key) or 0) - float(dist_b.get(key) or 0), 4)
                for key in ("E0", "E1", "E2")
            }
        hist_a = ra.get("historical_occupation_reference") or {}
        hist_b = rb.get("historical_occupation_reference") or {}
        return jsonify({"success": True, "mode": mode,
            "risk_delta": round(abs(ra["risk_score"] - rb["risk_score"]), 3),
            "historical_occupation_reference_delta": round(abs(ra["risk_score"] - rb["risk_score"]), 3),
            "risk_delta_interpretation": "Historical occupation reference difference, not personal job-loss probability.",
            "risk_a": ra["risk_score"], "risk_b": rb["risk_score"],
            "label_a": ra["risk_label"], "label_b": rb["risk_label"],
            "historical_occupation_reference_a": hist_a,
            "historical_occupation_reference_b": hist_b,
            "task_exposure_a": ra.get("task_exposure"),
            "task_exposure_b": rb.get("task_exposure"),
            "task_exposure_distribution_delta": exposure_delta,
            "occupation_match_a": ra.get("occupation_match"),
            "occupation_match_b": rb.get("occupation_match"),
            "top_role_a": (ra.get("top_roles") or [{}])[0].get("job_role", "N/A"),
            "top_role_b": (rb.get("top_roles") or [{}])[0].get("job_role", "N/A"),
            "riasec_a": ra.get("riasec", {}).get("primary", "N/A"),
            "riasec_b": rb.get("riasec", {}).get("primary", "N/A"),
            "legacy_fields": {"risk_delta": round(abs(ra["risk_score"] - rb["risk_score"]), 3), "note": "Alias of historical_occupation_reference_delta."},
        })
    except Exception as exc:
        log.exception("Comparison failed")
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    log.info("Prayash starting up...")
    ensure_model_artifacts()
    _debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=_debug, use_reloader=_debug, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))