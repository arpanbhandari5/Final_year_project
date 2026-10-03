"""
Prayash — Application Configuration
====================================
Single source of truth for Flask configuration. Values are read from
environment variables (see ``.env.example``) with sensible development
defaults so the application runs out of the box.

The existing monolithic ``app.py`` imports these settings via
``app.config.from_object(Config)`` so that runtime configuration is kept
separate from application code (clean architecture, 12-factor style).
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

BASE_DIR = Path(__file__).resolve().parent
"""Project root (parent of this file)."""


def _is_production() -> bool:
    """True when ``FLASK_ENV=production`` is set."""
    return os.environ.get("FLASK_ENV", "development") == "production"


class Config:
    """Default application configuration (mirrors the legacy defaults)."""

    # ── Flask Core ────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "prayash-local-development-secret")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Must be True in production behind HTTPS; off by default for local dev.
    SESSION_COOKIE_SECURE = _is_production()
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # "Remember me" duration
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB global upload ceiling

    # ── Database ──────────────────────────────────────────────────
    # SQLite by default; set DATABASE_URL to a PostgreSQL DSN in production.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'instance' / 'prayash.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Redis (shared security stores) ─────────────────────────────
    # Backs the rate-limit / login-lockout / OTP-cooldown counters so limits
    # apply across gunicorn workers. Empty ⇒ in-memory fallback (single
    # process). Any Redis-compatible URL works (self-hosted, Upstash, …).
    REDIS_URL = os.environ.get("REDIS_URL", "")

    # ── CSRF (Flask-WTF) ──────────────────────────────────────────
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # ── Chat file attachment storage ──────────────────────────────
    CAREER_CHAT_UPLOAD_DIR = str(BASE_DIR / "uploads")
    CHAT_UPLOAD_DIR = str(BASE_DIR / "uploads")
    MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB per file (matches MAX_CONTENT_LENGTH)

    # Allowed file types for the chatbot (extension -> human label).
    CHAT_ALLOWED_EXTENSIONS: ClassVar[dict[str, str]] = {
        "pdf": "PDF",
        "docx": "Word Document",
        "txt": "Text",
        "csv": "CSV",
        "xlsx": "Excel",
        "png": "Image",
        "jpg": "Image",
        "jpeg": "Image",
    }
    CHAT_IMAGE_EXTENSIONS: ClassVar[set[str]] = {"png", "jpg", "jpeg"}

    # ── Compression (Flask-Compress) ──────────────────────────────
    COMPRESS_REGISTER = True
    COMPRESS_MIMETYPES: ClassVar[list[str]] = [
        "text/html",
        "text/css",
        "text/javascript",
        "application/json",
        "application/javascript",
        "image/svg+xml",
    ]
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500

    # ── LLM Provider (Ollama / OpenRouter / DeepSeek / OpenAI) ────
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "").strip().lower()
    LLM_MODEL = os.environ.get("LLM_MODEL", "")
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
    OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "")
    OPENROUTER_SITE_NAME = os.environ.get("OPENROUTER_SITE_NAME", "")
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

    # ── Chat behaviour ────────────────────────────────────────────
    CHAT_HISTORY_MAX_MESSAGES = 20  # context window fed to the LLM
    CHAT_CONTEXT_MAX_CHARS = 15000  # max chars of document context sent to LLM
    CHAT_RULE_FALLBACK_ENABLED = True  # use rule-based answers when no LLM is up
    CHAT_MAX_GENERATION_TOKENS = 600  # default cap for chat responses
