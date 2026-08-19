"""
Prayash — Login Brute-Force Lockout Tests
==========================================
Unit tests for the IP+email login lockout protection in ``security.py``:

    - 5 failed attempts within 5 minutes lock the IP+email combo
    - Locked requests are rejected even with the correct password
    - Lockout is scoped per IP+email (other emails / IPs unaffected)
    - A successful login clears the failure counter
    - The lockout expires after the 5-minute window
    - Attempts-remaining feedback is shown while approaching lockout

Run with::

    pytest tests/test_login_lockout.py -v
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure email sending is always mocked to avoid real SMTP calls in tests.
os.environ.setdefault("MAIL_USERNAME", "")
os.environ.setdefault("MAIL_PASSWORD", "")
os.environ.setdefault("SMTP_USERNAME", "")
os.environ.setdefault("SMTP_PASSWORD", "")

from security import (  # noqa: E402
    _LOGIN_ATTEMPT_STORE,
    _LOGIN_LOCKOUT_WINDOW,
    _LOGIN_MAX_ATTEMPTS,
)


@pytest.fixture
def client(app, monkeypatch):
    """A Flask test client with email sending neutralised."""
    import storage

    monkeypatch.setattr(storage, "send_email", lambda *a, **k: True)
    return app.test_client()


@pytest.fixture
def user(app):
    """A verified user with known credentials for the lockout tests."""
    from storage import create_user, db

    u = create_user("lockoutuser@example.com", "CorrectPass1!")
    u.email_verified = True
    db.session.commit()
    return u


def _login(client, email: str = "lockoutuser@example.com", password: str = "WrongPass1!", xff: str | None = None):
    """POST the login form; optionally simulate a client IP via X-Forwarded-For."""
    headers = {"X-Forwarded-For": xff} if xff else None
    return client.post("/login", data={"email": email, "password": password}, headers=headers)


def _attempt_key(email: str = "lockoutuser@example.com", ip: str = "127.0.0.1") -> str:
    """The lockout store key the app derives for an IP+email combo."""
    return f"{ip}:{email}"


# ── Core lockout: 5 failed attempts ────────────────────────────────


def test_five_failures_then_correct_password_still_locked(client, user) -> None:
    """After 5 wrong passwords, even the correct password is rejected."""
    for _ in range(_LOGIN_MAX_ATTEMPTS):
        resp = _login(client, password="WrongPass1!")
        assert resp.status_code == 200

    # The 6th attempt carries the CORRECT password — still locked.
    resp = _login(client, password="CorrectPass1!")
    assert resp.status_code == 200
    body = resp.data.lower()
    assert b"too many failed attempts" in body
    assert b"try again in" in body

    # The store recorded exactly the max attempts.
    entry = _LOGIN_ATTEMPT_STORE.get(_attempt_key())
    assert entry is not None
    count, _ = entry
    assert count == _LOGIN_MAX_ATTEMPTS


def test_lockout_remaining_countdown_present(client, user) -> None:
    """The locked page surfaces the remaining cooldown seconds."""
    for _ in range(_LOGIN_MAX_ATTEMPTS):
        _login(client)

    resp = _login(client, password="CorrectPass1!")
    body = resp.data.lower()
    assert b"too many failed attempts" in body
    # A numeric countdown should be rendered (e.g. "Try again in 285 seconds").
    match = re.search(rb"try again in (\d+) seconds", body)
    assert match, f"Missing countdown in: {body[:300]}"
    assert 0 < int(match.group(1)) <= _LOGIN_LOCKOUT_WINDOW


def test_attempts_remaining_feedback(client, user) -> None:
    """Before lockout, the user sees how many attempts remain."""
    _login(client)
    _login(client)
    resp = _login(client)  # 3 failures so far → 2 remaining
    assert resp.status_code == 200
    body = resp.data.lower()
    assert b"attempt" in body and b"remaining" in body
    entry = _LOGIN_ATTEMPT_STORE.get(_attempt_key())
    assert entry is not None
    count, _ = entry
    assert count == 3
    remaining = _LOGIN_MAX_ATTEMPTS - count
    assert remaining == 2
    assert f"{remaining} attempt".encode() in body


# ── Lockout scope ──────────────────────────────────────────────────


def test_lockout_scoped_per_email(client, app, user) -> None:
    """Failures against one account do not lock a different account."""
    from storage import create_user, db

    with app.app_context():
        second = create_user("second@example.com", "SecondPass1!")
        second.email_verified = True
        db.session.commit()

    for _ in range(_LOGIN_MAX_ATTEMPTS):
        _login(client, email=user.email)

    # A different account (correct password, same IP) is NOT locked out.
    resp = _login(client, email="second@example.com", password="SecondPass1!")
    assert resp.status_code in (302, 303)
    assert "workspace" in resp.headers.get("Location", "")

    # The locked account remains locked even with the correct password.
    resp = _login(client, email=user.email, password="CorrectPass1!")
    assert b"too many failed attempts" in resp.data.lower()


def test_lockout_scoped_per_ip(client, user) -> None:
    """Failures from one IP do not lock the same account from another IP."""
    for _ in range(_LOGIN_MAX_ATTEMPTS):
        _login(client, xff="203.0.113.9")

    # Correct password from a DIFFERENT IP is allowed.
    resp = _login(client, password="CorrectPass1!", xff="198.51.100.7")
    assert resp.status_code in (302, 303)
    assert "workspace" in resp.headers.get("Location", "")

    # The original IP remains locked.
    resp = _login(client, password="CorrectPass1!", xff="203.0.113.9")
    assert b"too many failed attempts" in resp.data.lower()


# ── Reset / expiry ─────────────────────────────────────────────────


def test_successful_login_clears_failure_count(client, user) -> None:
    """A correct login resets the failure counter for that IP+email."""
    for _ in range(3):
        _login(client)
    assert _attempt_key() in _LOGIN_ATTEMPT_STORE

    resp = _login(client, password="CorrectPass1!")
    assert resp.status_code in (302, 303)
    assert "workspace" in resp.headers.get("Location", "")

    # The counter was cleared on success.
    assert _attempt_key() not in _LOGIN_ATTEMPT_STORE


def test_lockout_expires_after_window(client, user) -> None:
    """Once the lockout window elapses, login is allowed again."""
    for _ in range(_LOGIN_MAX_ATTEMPTS):
        _login(client)
    assert b"too many failed attempts" in _login(client, password="CorrectPass1!").data.lower()

    # Simulate the window expiring by ageing the stored attempt timestamp.
    _LOGIN_ATTEMPT_STORE[_attempt_key()] = (
        _LOGIN_MAX_ATTEMPTS,
        time.time() - _LOGIN_LOCKOUT_WINDOW - 1,
    )

    resp = _login(client, password="CorrectPass1!")
    assert resp.status_code in (302, 303)
    assert "workspace" in resp.headers.get("Location", "")
    assert _attempt_key() not in _LOGIN_ATTEMPT_STORE


def test_unverified_email_login_does_not_count_failure(client, app) -> None:
    """A correct password on an unverified account routes to OTP and is
    NOT recorded as a failed attempt (regression guard)."""
    from storage import create_user, db

    with app.app_context():
        unverified = create_user("unverified.lockout@example.com", "CorrectPass1!")
        unverified.email_verified = False
        db.session.commit()

    for _ in range(3):
        resp = _login(client, email="unverified.lockout@example.com", password="CorrectPass1!")
        assert resp.status_code == 200
        assert b"verify your email" in resp.data.lower() or b"verification code" in resp.data.lower()

    # No failed attempts recorded — the counter stays empty.
    assert _attempt_key(email="unverified.lockout@example.com") not in _LOGIN_ATTEMPT_STORE
