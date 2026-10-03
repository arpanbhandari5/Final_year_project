"""
Prayash — Shared Test Fixtures
===============================
One session-scoped Flask app + one shared temp database for the whole test
run, with a per-test reset (drop/recreate tables, clear in-memory stores).

Previously every test file built its own app and database per test, which
made the 120-test suite take several minutes (importing the heavy ML stack
happened once per file, and scrypt password hashing ran on every seed and
login). This conftest fixes both:

- ``app`` (session scope)  → the app + heavy imports happen exactly once.
- fast hashing            → ``storage.generate_password_hash`` is patched to
                            use cheap pbkdf2 iterations, so seeding and login
                            checks are near-instant. Hashing strength is not
                            what these tests exercise.
- ``_reset_test_state``   → before every test the tables are emptied with
                            row deletes (not ``drop_all``/``create_all`` —
                            SQLite DDL per test measured ~0.5s vs ~0.09s for
                            deletes) and the in-memory rate-limit / lockout /
                            chat-session stores are cleared, keeping tests
                            isolated. The ML artifacts are loaded once per
                            process via ``risk_assessor.load_artifacts``'s
                            ``lru_cache``, so no per-test model loading.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Environment: point the DB at a disposable temp file and neutralise
#    email + LLM providers BEFORE the app module is first imported. ──
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="prayash_test_"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(_TEST_DB_DIR / 'prayash_test.db').as_posix()}")
os.environ.setdefault("MAIL_USERNAME", "")
os.environ.setdefault("MAIL_PASSWORD", "")
os.environ.setdefault("SMTP_USERNAME", "")
os.environ.setdefault("SMTP_PASSWORD", "")
os.environ.setdefault("LLM_PROVIDER", "")
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:1")  # unreachable
# Force the in-memory security-store backend so tests never touch a real
# Redis server (rate-limit / lockout state is cleared per test via .clear()).
os.environ["REDIS_URL"] = ""

# ── Fast password hashing for tests ──
# Werkzeug's default scrypt (n=32768) is deliberately slow; that cost is not
# what these tests assert on. Patch storage's generate_password_hash so
# seeding and login checks run in milliseconds instead of seconds. The
# method is embedded in the hash string, so check_password_hash verifies
# these hashes exactly as it would production ones.
import storage as _storage  # noqa: E402

_orig_hash = _storage.generate_password_hash


def _fast_hash(password: str, method: str | None = None, salt_length: int | None = None) -> str:
    if salt_length is None:
        return _orig_hash(password, method or "pbkdf2:sha256:1000")
    return _orig_hash(password, method or "pbkdf2:sha256:1000", salt_length)


_storage.generate_password_hash = _fast_hash

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """The Flask app, configured for testing and created once per session."""
    from app import app as flask_app

    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["CAREER_CHAT_UPLOAD_DIR"] = str(_TEST_DB_DIR / "chat_uploads")
    flask_app.config["CHAT_UPLOAD_DIR"] = str(_TEST_DB_DIR / "chat_uploads")

    with flask_app.app_context():
        from storage import db, seed_default_users

        db.create_all()
        seed_default_users()

    yield flask_app

    with flask_app.app_context():
        from storage import db

        db.drop_all()


@pytest.fixture(autouse=True)
def _skip_ollama(monkeypatch):
    """Never attempt an Ollama connection in tests.

    The unreachable OLLAMA_HOST (127.0.0.1:1) is silently dropped rather than
    refused on some platforms, so the first connection attempt blocks for the
    full TCP connect timeout (~2s) before falling back. Short-circuit the
    availability check so every endpoint (career chat, chat blueprint,
    analysis narrative) goes straight to its rule-based fallback.
    """
    import risk_assessor as _risk_assessor
    import routes.api as routes_api
    import services.ai_service as ai_service

    for mod in (routes_api, _risk_assessor, ai_service):
        monkeypatch.setattr(mod, "is_ollama_on_cooldown", lambda: True)


@pytest.fixture(autouse=True)
def _reset_test_state(app):
    """Reset the database and in-memory stores before every test.

    The app context is pushed here and kept open for the whole test (the
    same pattern the previous per-file fixtures used) so helpers like
    ``create_user`` work without their own context.
    """
    import services.ai_service as ai_service
    from routes.api import _CAREER_CHAT_LAST_ACTIVE, _CAREER_CHAT_SESSIONS
    from security import _LOGIN_ATTEMPT_STORE, _OTP_REQUEST_STORE, _RATE_LIMIT_STORE

    _OTP_REQUEST_STORE.clear()
    _RATE_LIMIT_STORE.clear()
    _LOGIN_ATTEMPT_STORE.clear()
    _CAREER_CHAT_SESSIONS.clear()
    _CAREER_CHAT_LAST_ACTIVE.clear()
    ai_service._CANCELLED.clear()

    from sqlalchemy import text

    from storage import db, seed_default_users

    with app.app_context():
        db.session.remove()
        # Wipe rows rather than recreate tables — per-test SQLite DDL was the
        # dominant cost (drop_all+create_all ~0.5s/test). Tables keep their
        # schema; only data is cleared, which is all these tests need.
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(text(f'DELETE FROM "{table.name}"'))
        db.session.commit()
        seed_default_users()
        yield


@pytest.fixture
def client(app):
    """A Flask test client bound to the shared app."""
    return app.test_client()
