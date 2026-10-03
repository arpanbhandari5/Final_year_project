"""
Prayash — Shared Security Helpers
==================================
Single source of truth for the request-guard helpers used across the
application:

    - ``rate_limit``            sliding-window per-IP limiter
    - login brute-force lockout (per IP+email)
    - OTP request cooldown (per email)
    - ``validate_password_strength``

These used to live duplicated in ``app.py`` and ``routes/chat.py``; both now
import from here.

Stores
------
The counters behind the rate limiter, lockout and OTP cooldown live in a
shared store. When ``REDIS_URL`` is configured **and** reachable the stores
are backed by Redis so limits apply across gunicorn workers / processes;
otherwise they transparently fall back to in-memory dicts (single-process
dev server). See SECURITY.md for deployment notes.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import urlparse

from flask import current_app, jsonify, request

from config import Config

log = logging.getLogger("prayash.security")

# ── Limits (shared by both backends) ────────────────────────────────
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX_REQUESTS = 30  # requests per window
_OTP_REQUEST_WINDOW = 60  # seconds between OTP requests for the same email
_LOGIN_LOCKOUT_WINDOW = 300  # 5 minutes
_LOGIN_MAX_ATTEMPTS = 5  # max failed attempts before lockout


# ── Store backends ──────────────────────────────────────────────────
class _MemoryStore(dict):
    """In-memory fallback store (a plain dict) plus the rate-limit helper.

    A ``dict`` subclass so every call site (``get`` / ``in`` / item
    assignment / ``pop`` / ``clear``) behaves exactly like the original
    in-memory implementation — used whenever Redis is not configured or
    unreachable, and in the test suite.
    """

    def record_sliding(self, key: str, window: int, max_requests: int) -> bool:
        """Record ``now`` under *key*; return True if still within the limit."""
        now = time.time()
        window_start = now - window
        timestamps = self.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= max_requests:
            return False
        timestamps.append(now)
        self[key] = timestamps
        return True


class _RedisStore:
    """Redis-backed store exposing the same dict-like API as ``_MemoryStore``.

    Values are JSON-encoded with a TTL matching the relevant window so stale
    keys are reclaimed automatically. ``record_sliding`` uses an atomic
    sorted-set pipeline, which is what makes the rate limit correct across
    multiple workers.
    """

    def __init__(self, client: Any, prefix: str, ttl: int) -> None:
        self._client = client
        self._prefix = prefix
        self._ttl = ttl

    def _key(self, key: str) -> str:
        return f"prayash:{self._prefix}:{key}"

    def get(self, key: str, default: Any = None) -> Any:
        raw = self._client.get(self._key(key))
        if raw is None:
            return default
        return json.loads(raw)

    def __setitem__(self, key: str, value: Any) -> None:
        self._client.set(self._key(key), json.dumps(value), ex=self._ttl)

    def __contains__(self, key: str) -> bool:
        return bool(self._client.exists(self._key(key)))

    def pop(self, key: str, default: Any = None) -> Any:
        rkey = self._key(key)
        raw = self._client.get(rkey)
        self._client.delete(rkey)
        if raw is None:
            return default
        return json.loads(raw)

    def clear(self) -> None:
        for rkey in self._client.scan_iter(match=f"prayash:{self._prefix}:*"):
            self._client.delete(rkey)

    def record_sliding(self, key: str, window: int, max_requests: int) -> bool:
        """Atomically record ``now`` and report whether the limit is exceeded.

        Uses a Redis sorted set (member = ``<timestamp>:<nonce>``) so the
        prune / add / count sequence is atomic across processes.
        """
        now = time.time()
        rkey = self._key(key)
        member = f"{now}:{secrets.token_hex(4)}"
        pipe = self._client.pipeline(transaction=True)
        pipe.zremrangebyscore(rkey, "-inf", now - window)
        pipe.zadd(rkey, {member: now})
        pipe.zcard(rkey)
        pipe.expire(rkey, window)
        *_, count, _ = pipe.execute()
        return count <= max_requests


# ── Backend selection ───────────────────────────────────────────────
def _redact_url(url: str) -> str:
    """Strip credentials from a Redis URL for safe logging."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
    except Exception:
        pass
    return url


def _build_redis_client() -> Any | None:
    """Connect to Redis when configured; return None to use in-memory stores."""
    url = (Config.REDIS_URL or "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore[import-not-found]
    except ImportError:
        log.warning("redis-py is not installed (pip install redis) — using in-memory stores")
        return None
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        log.info("Security stores backed by Redis: %s", _redact_url(url))
        return client
    except Exception as exc:  # connection refused, bad URL, etc.
        log.warning("Redis unavailable at %s (%s) — using in-memory stores", _redact_url(url), exc)
        return None


_redis_client = _build_redis_client()
_CACHE_BACKEND = "redis" if _redis_client is not None else "memory"
"""``"redis"`` or ``"memory"`` — reported by ``/healthz``."""

if _redis_client is not None:
    _RATE_LIMIT_STORE = _RedisStore(_redis_client, "rl", _RATE_LIMIT_WINDOW)
    _OTP_REQUEST_STORE = _RedisStore(_redis_client, "otp", _OTP_REQUEST_WINDOW)
    _LOGIN_ATTEMPT_STORE = _RedisStore(_redis_client, "lockout", _LOGIN_LOCKOUT_WINDOW)
else:
    _RATE_LIMIT_STORE = _MemoryStore()
    _OTP_REQUEST_STORE = _MemoryStore()
    _LOGIN_ATTEMPT_STORE = _MemoryStore()


# ── Rate limiter ────────────────────────────────────────────────────
def _rate_limit_key() -> str:
    """Derive a rate-limit key from the client IP."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr or "127.0.0.1"


def rate_limit(fn: Callable) -> Callable:
    """Sliding-window rate limiter backed by the shared store (Redis or in-memory).

    Disabled automatically when ``current_app.config["TESTING"]`` is ``True``
    so that test suites can make many requests without hitting the limit.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Bypass rate limiting entirely during tests
        if current_app.config.get("TESTING"):
            return fn(*args, **kwargs)

        key = _rate_limit_key()
        if not _RATE_LIMIT_STORE.record_sliding(key, _RATE_LIMIT_WINDOW, _RATE_LIMIT_MAX_REQUESTS):
            log.warning("Rate limit exceeded for IP %s", key)
            return jsonify({"success": False, "error": "Too many requests. Please slow down."}), 429

        return fn(*args, **kwargs)

    return wrapper


# ── OTP request cooldown ───────────────────────────────────────────


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


# ── Login brute-force lockout ───────────────────────────────────────


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
            return count >= _LOGIN_MAX_ATTEMPTS
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


# ── Password strength ───────────────────────────────────────────────

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
