from __future__ import annotations

import logging
import os
import secrets
from typing import Any

from flask import Flask, Response, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from bootstrap import ensure_model_artifacts
from config import Config
from extensions import compress, csrf, login_manager

# ── Route modules (plain-route registration keeps endpoint names stable,
#    e.g. ``login``, ``workspace``, ``methodology``, used by templates) ──
from routes.admin import register_admin
from routes.api import register_api
from routes.auth import LINKEDIN_AVAILABLE, _oauth_is_configured, register_auth

# ── Career Assistant Chat Blueprint (ChatGPT-style page) ──
# Imported early so the chat models (ChatConversation, ChatMessage,
# UploadedFile, AIFeedback) register on ``db`` BEFORE ``db.create_all()``
# runs in initialize_database() — otherwise the chat tables would never exist.
from routes.chat import chat_bp
from routes.pages import register_pages
from storage import User, init_database
from utils import get_cache_bust_hash

# ── Project root ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path)
        log.info("Loaded environment variables from %s", env_path)
    else:
        log.info("No .env file found at %s — using environment variables", env_path)
except ImportError:
    log.info("python-dotenv not installed — using system environment variables")

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


app = Flask(__name__, template_folder="templates", static_folder="static")
# Runtime configuration comes from config.py (12-factor style) — see
# .env.example for the full list of environment variables.
app.config.from_object(Config)

# ── Extensions (bound here from extensions.py so blueprints share one instance) ──
compress.init_app(app)
csrf.init_app(app)
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


# ── Route registration (endpoint names preserved) ─────────────
register_pages(app)
register_auth(app)  # also registers the OAuth blueprints under /login
register_admin(app)
register_api(app)
app.register_blueprint(chat_bp)


@app.before_request
def _set_csp_nonce() -> None:
    g.csp_nonce = secrets.token_urlsafe(16)


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "site_name": "Prayash",
        "site_tagline": "Learning for better future",
        "is_authenticated": bool(current_user.is_authenticated),
        "admin_authenticated": bool(current_user.is_authenticated and getattr(current_user, "is_admin_email", False)),
        "static_version": get_cache_bust_hash(),
        "csp_nonce": getattr(g, "csp_nonce", secrets.token_urlsafe(16)),
        "csrf_token": lambda: generate_csrf(),
        # OAuth provider configuration status for the auth template
        "oauth_google_configured": _oauth_is_configured("google"),
        "oauth_github_configured": _oauth_is_configured("github"),
        "oauth_linkedin_configured": _oauth_is_configured("linkedin") and LINKEDIN_AVAILABLE,
    }


def initialize_database() -> None:
    init_database(app)


initialize_database()


@app.get("/__audit")
def audit_page():
    """TEMP: layout-audit harness (remove after UI verification)."""
    from flask_login import login_user

    from storage import get_user_by_email

    user = get_user_by_email("student@prayash.local")
    if user:
        login_user(user, remember=False)
    page = request.args.get("page", "/")
    pages = {
        "/": ("index.html", "home", "Prayash: Learning for better future"),
        "/workspace": ("workspace.html", "workspace", "Workspace | Prayash"),
        "/chatbot": ("chatbot.html", "chatbot", "AI Career Assistant | Prayash"),
        "/methodology": ("methodology.html", "methodology", "Methodology | Prayash"),
        "/insights": ("insights.html", "insights", "Insights | Prayash"),
    }
    if page not in pages:
        return Response("unknown page", mimetype="text/plain")
    tpl, active, title = pages[page]
    body = render_template(tpl, active_page=active, title=title)
    script = """<script nonce="{{ csp_nonce }}">
(function() {
  var out = document.createElement('pre'); out.id = 'out';
  document.body.appendChild(out);
  function run() {
    var doc = document.documentElement;
    function rect(el) { var r = el.getBoundingClientRect(); return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height),t:Math.round(r.top),b:Math.round(r.bottom),l:Math.round(r.left),r:Math.round(r.right)}; }
    var over = [];
    document.querySelectorAll('body *').forEach(function(el) {
      var r = el.getBoundingClientRect();
      if (r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1)) {
        over.push({tag: el.tagName, cls: String(el.className||'').slice(0,50), l:Math.round(r.left), r:Math.round(r.right), w:Math.round(r.width)});
      }
    });
    var m = {
      viewport: [window.innerWidth, window.innerHeight],
      docW: doc.scrollWidth, docH: doc.scrollHeight,
      hOverflow: doc.scrollWidth - window.innerWidth,
      navbar: rect(document.querySelector('.navbar')),
      chatPanel: (function(){var e=document.querySelector('.career-chat-panel'); return e?rect(e):null;})(),
      chatToggle: (function(){var e=document.querySelector('.career-chat-toggle'); return e?rect(e):null;})(),
      chatbotApp: (function(){var e=document.querySelector('.chatbot-app'); return e?rect(e):null;})(),
      composer: (function(){var e=document.querySelector('.chatbot-composer'); return e?rect(e):null;})(),
      footerTop: (function(){var e=document.querySelector('.footer'); return e?rect(e).t:null;})(),
      overflowers: over.slice(0, 14),
    };
    out.textContent = JSON.stringify(m);
  }
  if (document.readyState === 'complete') { run(); }
  else { window.addEventListener('load', function(){ setTimeout(run, 50); }); }
})();
</script>"""
    html = body.replace("</body>", script.replace("{{ csp_nonce }}", getattr(g, "csp_nonce", "")) + "</body>")
    return Response(html, mimetype="text/html")


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


if __name__ == "__main__":
    log.info("Prayash starting up...")
    ensure_model_artifacts()
    app.run(debug=True, threaded=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
