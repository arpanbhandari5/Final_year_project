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
from extensions import compress, csrf, db, login_manager

# ── Route modules (plain-route registration keeps endpoint names stable,
#    e.g. ``login``, ``workspace``, ``methodology``, used by templates) ──
from routes.admin import register_admin
from routes.api import register_api
from routes.extension_api import register_extension_api
from routes.auth import LINKEDIN_AVAILABLE, _oauth_is_configured, register_auth

# ── Career Assistant Chat Blueprint (ChatGPT-style page) ──
# Imported early so the chat models (ChatConversation, ChatMessage,
# UploadedFile, AIFeedback) register on ``db`` BEFORE ``db.create_all()``
# runs in initialize_database() — otherwise the chat tables would never exist.
from routes.chat import chat_bp
from routes.pages import register_pages
from storage import User, get_linked_providers, init_database
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
        return db.session.get(User, int(user_id))
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
register_extension_api(app)
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
        # Providers already attached to the signed-in account (Linked Accounts UI)
        "linked_providers": (get_linked_providers(current_user) if current_user.is_authenticated else []),
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
    app.run(debug=True, threaded=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
