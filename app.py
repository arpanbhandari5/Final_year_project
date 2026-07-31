from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Generator

from flask import Flask, Response, g, jsonify, redirect, render_template, request, session, stream_with_context, url_for

from flask_compress import Compress
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect, generate_csrf

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
from risk_assessor import analyze_resume as assess_resume, analyze_skills_gap, get_available_roles, suggest_career_paths, generate_learning_roadmap
from resume_parser import extract_resume_text as parse_resume_file
from storage import (
    User, authenticate_user, create_user, create_oauth_user,
    dashboard_metrics, get_detailed_metrics, get_all_users,
    get_user_by_email, get_user_by_username, init_database, record_feedback, record_upload,
    create_password_reset_token, verify_reset_token, consume_reset_token, update_user_password,
    create_otp, verify_otp, mark_email_verified, send_email,
    check_otp, invalidate_user_otps, get_otp_attempts_remaining,
    OTP_LENGTH, OTP_MAX_ATTEMPTS,
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


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "prayash-local-development-secret"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'instance' / 'prayash.db').as_posix()}"),
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
    return jsonify({"success": True, "message": message})


# ── Forgot Password with OTP ──

@app.route("/forgot-password/otp", methods=["GET", "POST"])
@rate_limit
def forgot_password_otp():
    """Handle forgot password flow with OTP."""
    error = None
    sent = False
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
                # Always show success to prevent email enumeration
                sent = True

    return render_template(
        "forgot_password.html",
        active_page="",
        title="Forgot Password | Prayash",
        error=error,
        sent=sent,
        email=email if sent else "",
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


@app.get("/workspace/skills-gap")
@login_required
def skills_gap() -> str:
    """Dedicated skills gap analysis page (SAHAY_AI-inspired)."""
    return render_template("skills_gap.html", active_page="workspace", title="Skills Gap Analysis | Prayash")


@app.get("/methodology")
def methodology() -> str:
    return render_template("methodology.html", active_page="methodology", title="Methodology | Prayash")


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
            log.info("Partnership inquiry: org=%s, contact=%s, use_case=%s", org, contact, use_case)
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
    # Security headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-XSS-Protection", "0")  # Deprecated but harmless
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    nonce = getattr(g, "csp_nonce", secrets.token_urlsafe(16))
    response.headers.setdefault("Content-Security-Policy", _make_csp(nonce))
    # Cache static assets aggressively
    if request.path.startswith("/static/") and not request.path.endswith(".html"):
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


def _run_analysis_workflow(resume_text: str, mode: str) -> dict[str, Any]:
    """Run the full analysis pipeline.

    Model artifacts are expected to have been prepared at startup via
    ``ensure_model_artifacts()``.  If the artifacts are missing the
    analysis will raise ``RuntimeError``, which the caller should handle.
    """
    analysis = assess_resume(resume_text, mode=mode)
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
            yield from emit("risk", "Running automation risk prediction...", 40)
            yield from emit("roles", "Matching to O*NET roles...", 60)
            yield from emit("roadmap", "Generating learning roadmap...", 80)
            if mode == "advanced": yield from emit("llama", "Running Llama 3 narrative...", 95)
            record_upload(filename="streamed_resume.txt", file_type="text", mode=mode, risk_score=analysis.get("risk_score", 0.0), risk_label=analysis.get("risk_label", "Low"), reasoning=analysis.get("reasoning", {}), user_id=current_user.id if current_user.is_authenticated else None)
            analysis.update({"success": True})
            yield from emit("complete", "Analysis complete!", 100, analysis)
        except Exception as exc:
            log.exception("Stream analysis failed")
            yield from emit("error", str(exc), -1, {"error": str(exc)})
    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
        return jsonify(analysis)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

@app.post("/api/upload")
def api_upload():
    return _handle_upload_request()


@app.post("/api/analyze")
def api_analyze():
    return _handle_upload_request()


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

    # Try Ollama for AI-powered response (same pipeline as Advanced mode)
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3")
    llm_available = False
    answer = ""

    # If Ollama is running, use it
    try:
        system_prompt = (
            "You are a helpful AI career advisor assistant. "
            "Answer career-related questions concisely and practically. "
            "Give specific, actionable advice based on the user's resume and question."
        )

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
            answer = (result.get("response") or "").strip()
            llm_available = bool(answer)
    except Exception:
        log.debug("Ollama not available for career chat, using fallback")    # ── Try API Key Provider (DeepSeek / OpenAI) as second LLM tier ──
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
            _log_openai.warning("API provider (%s) failed: %s", _llm_provider or "auto", _llm_err)
            _log_openai.debug("API provider not available for career chat, using rule-based fallback")

    # ── Fallback: rule-based response when no LLM is available ──
    if not llm_available:
        question_lower = question.lower()

        if any(kw in question_lower for kw in ["skill", "learn", "study", "course", "improve"]):
            answer = (
                "Based on your resume analysis, I recommend focusing on skill development. "
                "Check the learning roadmap in your analysis report for personalized course recommendations. "
                "Start with the top suggested Coursera courses for your skill gaps."
            )
        elif any(kw in question_lower for kw in ["job", "career", "role", "position", "apply"]):
            answer = (
                "For job searching, use your top role matches from the analysis as search keywords. "
                "Tailor your resume summary to highlight the skills most relevant to your target role. "
                "Consider setting up job alerts for your strongest matching positions."
            )
        elif any(kw in question_lower for kw in ["resume", "cv", "improve", "better", "weak"]):
            answer = (
                "To improve your resume: 1) Add specific, quantifiable achievements, "
                "2) Use keywords from target job descriptions, "
                "3) Include a professional summary section, "
                "4) Keep your format clean and ATS-friendly (PDF recommended), "
                "5) Ensure your contact info (email, LinkedIn) is clearly visible."
            )
        elif any(kw in question_lower for kw in ["salary", "pay", "earn", "compensation"]):
            answer = (
                "Salary ranges vary by location, experience, and industry. "
                "Use sites like Glassdoor, Levels.fyi, and LinkedIn Salary to research "
                "market rates for your target roles. Consider total compensation including "
                "benefits, equity, and bonuses."
            )
        elif any(kw in question_lower for kw in ["interview", "prepare", "questions"]):
            answer = (
                "To prepare for interviews: 1) Review common questions for your target role, "
                "2) Prepare STAR-format stories from your experience, "
                "3) Practice technical skills with platforms like LeetCode or HackerRank, "
                "4) Research the company's culture and recent news, "
                "5) Prepare thoughtful questions to ask the interviewer."
            )
        elif any(kw in question_lower for kw in ["hello", "hi ", "hey", "help"]):
            answer = (
                "Hi! I'm your AI career assistant. I can help with:\n"
                "• Skill development and learning recommendations\n"
                "• Job search strategies and career advice\n"
                "• Resume improvement tips\n"
                "• Interview preparation\n"
                "• Salary and compensation questions\n"
                "What would you like to know?"
            )
        else:
            answer = (
                "That's a great question! For more personalized advice, "
                "try running a resume analysis first to get tailored recommendations. "
                "To unlock AI-powered career guidance, set your DeepSeek or OpenAI API key "
                "in the server environment variables."
            )

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
            log.warning("Streaming career chat failed: %s", exc)

        # Fallback: rule-based answer (sent as one event)
        question_lower = question.lower()
        if any(kw in question_lower for kw in ["skill", "learn", "study", "course", "improve"]):
            full_answer = (
                "Based on your resume analysis, I recommend focusing on skill development. "
                "Check the learning roadmap in your analysis report for personalized course recommendations. "
                "Start with the top suggested Coursera courses for your skill gaps."
            )
        elif any(kw in question_lower for kw in ["job", "career", "role", "position", "apply"]):
            full_answer = (
                "For job searching, use your top role matches from the analysis as search keywords. "
                "Tailor your resume summary to highlight the skills most relevant to your target role. "
                "Consider setting up job alerts for your strongest matching positions."
            )
        elif any(kw in question_lower for kw in ["resume", "cv", "improve", "better", "weak"]):
            full_answer = (
                "To improve your resume: 1) Add specific, quantifiable achievements, "
                "2) Use keywords from target job descriptions, "
                "3) Include a professional summary section, "
                "4) Keep your format clean and ATS-friendly (PDF recommended), "
                "5) Ensure your contact info (email, LinkedIn) is clearly visible."
            )
        elif any(kw in question_lower for kw in ["salary", "pay", "earn", "compensation"]):
            full_answer = (
                "Salary ranges vary by location, experience, and industry. "
                "Use sites like Glassdoor, Levels.fyi, and LinkedIn Salary to research "
                "market rates for your target roles. Consider total compensation including "
                "benefits, equity, and bonuses for a complete picture."
            )
        elif any(kw in question_lower for kw in ["interview", "prepare", "mock", "crack"]):
            full_answer = (
                "To prepare for interviews: 1) Research the company and role thoroughly, "
                "2) Practice common questions with the STAR method, "
                "3) Prepare your own questions to ask the interviewer, "
                "4) Review technical fundamentals for your target role, "
                "5) Do mock interviews with friends or platforms like Pramp."
            )
        else:
            full_answer = (
                "That's a great question! Based on your profile, I recommend exploring the "
                "analysis report for personalized insights. You can also ask me about skills "
                "development, job search strategies, resume improvement, interview preparation, "
                "or salary negotiation. What would you like to know more about?"
            )

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
        return jsonify({"success": True, "mode": mode,
            "risk_delta": round(abs(ra["risk_score"] - rb["risk_score"]), 3),
            "risk_a": ra["risk_score"], "risk_b": rb["risk_score"],
            "label_a": ra["risk_label"], "label_b": rb["risk_label"],
            "top_role_a": (ra.get("top_roles") or [{}])[0].get("job_role", "N/A"),
            "top_role_b": (rb.get("top_roles") or [{}])[0].get("job_role", "N/A"),
            "riasec_a": ra.get("riasec", {}).get("primary", "N/A"),
            "riasec_b": rb.get("riasec", {}).get("primary", "N/A"),
        })
    except Exception as exc:
        log.exception("Comparison failed")
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    log.info("Prayash starting up...")
    ensure_model_artifacts()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))