"""
Prayash — Forgot Password (Email OTP) Tests
=============================================
End-to-end tests for the OTP-based password reset flow:

    /forgot-password/otp   request a reset code
    /reset-password/otp    verify the code and set a new password
    /resend-otp            resend a code (with cooldown)

Run with::

    pytest tests/test_forgot_password_otp.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL",
                       f"sqlite:///{PROJECT_ROOT / 'instance' / 'test_prayash.db'}")

STRONG_PASSWORD = "NewStrongP@ss1"


@pytest.fixture
def app():
    """Create and configure a fresh Flask application for each test."""
    from app import app as flask_app

    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True

    with flask_app.app_context():
        from storage import db, init_database
        db.create_all()
        from storage import seed_default_users
        seed_default_users()
        yield flask_app
        db.drop_all()
        try:
            db_path = PROJECT_ROOT / "instance" / "test_prayash.db"
            if db_path.exists():
                db_path.unlink()
        except PermissionError:
            pass


@pytest.fixture
def client(app, monkeypatch):
    """A Flask test client with fresh global OTP/cooldown state."""
    import app as app_module

    app_module._OTP_REQUEST_STORE.clear()
    app_module._RATE_LIMIT_STORE.clear()
    app_module._LOGIN_ATTEMPT_STORE.clear()
    monkeypatch.setattr(app_module, "send_email", lambda *a, **k: True)
    return app.test_client()


@pytest.fixture
def user(app):
    """A verified student user for the password-reset flow."""
    from storage import User, create_user, db

    u = create_user("resetuser@example.com", "OldPass123!")
    u.email_verified = True
    db.session.commit()
    return u


def _latest_otp(app, user, purpose: str = "reset_password"):
    """Fetch the most recent OTP row for a user + purpose from the DB."""
    from storage import VerificationOTP

    with app.app_context():
        return (
            VerificationOTP.query.filter_by(user_id=user.id, purpose=purpose)
            .order_by(VerificationOTP.id.desc())
            .first()
        )


def _request_reset(client, email: str):
    """POST the forgot-password form; returns the response."""
    return client.post("/forgot-password/otp", data={"email": email})


def _submit_otp(client, otp_code: str):
    """POST step=otp to /reset-password/otp."""
    return client.post("/reset-password/otp", data={"step": "otp", "otp": otp_code})


def _submit_new_password(client, password: str, confirm: str | None = None):
    """POST step=password to /reset-password/otp."""
    return client.post(
        "/reset-password/otp",
        data={"step": "password", "password": password, "confirm_password": confirm or password},
    )


# ── Request a reset code ───────────────────────────────────────────


def test_forgot_password_known_email(client, user) -> None:
    """An existing email gets the success page and an OTP row is created."""
    resp = _request_reset(client, user.email)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "sent" in body.lower() or "reset code" in body.lower()

    otp = _latest_otp(client.application, user)
    assert otp is not None
    assert otp.purpose == "reset_password"
    assert otp.used is False
    assert len(otp.otp) == 6 and otp.otp.isdigit()

    with client.session_transaction() as sess:
        assert sess.get("reset_email") == user.email


def test_forgot_password_unknown_email(client, user) -> None:
    """Unknown emails still render the success page (anti-enumeration)."""
    resp = _request_reset(client, "nobody@example.com")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "sent" in body.lower() or "reset code" in body.lower()

    otp = _latest_otp(client.application, user)
    assert otp is None


def test_forgot_password_invalid_email(client) -> None:
    """Malformed emails are rejected with an error."""
    resp = client.post("/forgot-password/otp", data={"email": "not-an-email"})
    assert resp.status_code == 200
    assert b"valid email" in resp.data.lower()


def test_forgot_password_cooldown(client, user) -> None:
    """Repeated requests within the cooldown window are throttled."""
    _request_reset(client, user.email)
    resp = _request_reset(client, user.email)
    assert resp.status_code == 200
    assert b"wait" in resp.data.lower()


def test_reset_page_requires_session(client) -> None:
    """GET /reset-password/otp without a session redirects to the form."""
    resp = client.get("/reset-password/otp")
    assert resp.status_code in (302, 303)
    assert "forgot-password" in resp.headers.get("Location", "")


# ── Verify the OTP ─────────────────────────────────────────────────


def test_otp_invalid_code_decrements_attempts(client, user) -> None:
    """A wrong code shows remaining-attempt feedback and consumes an attempt."""
    _request_reset(client, user.email)
    resp = _submit_otp(client, "000000")
    assert resp.status_code == 200
    body = resp.data.lower()
    assert b"incorrect code" in body
    assert b"attempt" in body

    otp = _latest_otp(client.application, user)
    assert otp.attempts == 1
    assert otp.used is False


def test_otp_max_attempts_locks_code(client, user) -> None:
    """Five wrong codes lock the OTP and tell the user to request a new one."""
    from app import OTP_MAX_ATTEMPTS

    _request_reset(client, user.email)
    for _ in range(OTP_MAX_ATTEMPTS - 1):
        _submit_otp(client, "000000")
    resp = _submit_otp(client, "000000")
    assert resp.status_code == 200
    assert b"too many incorrect attempts" in resp.data.lower()

    otp = _latest_otp(client.application, user)
    assert otp.used is True


def test_otp_expired_code(client, user) -> None:
    """An expired code is rejected with a specific message."""
    from storage import VerificationOTP, db

    _request_reset(client, user.email)
    otp = _latest_otp(client.application, user)
    with client.application.app_context():
        row = db.session.get(VerificationOTP, otp.id)
        assert row is not None
        code = row.otp
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

    db.session.expire_all()

    resp = _submit_otp(client, code)
    assert resp.status_code == 200
    assert b"expired" in resp.data.lower()


def test_otp_correct_code_shows_password_form(client, user) -> None:
    """A valid code unlocks the new-password step."""
    _request_reset(client, user.email)
    otp = _latest_otp(client.application, user)

    resp = _submit_otp(client, otp.otp)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Create New Password" in body
    assert "reset-password-submit" in body

    with client.session_transaction() as sess:
        assert sess.get("otp_verified") is True


def test_otp_cannot_be_reused(client, user) -> None:
    """A consumed OTP cannot be replayed (one-time use)."""
    _request_reset(client, user.email)
    otp = _latest_otp(client.application, user)

    assert _submit_otp(client, otp.otp).status_code == 200
    resp = _submit_otp(client, otp.otp)
    body = resp.data.lower()
    assert b"incorrect" in body or b"already been used" in body


# ── Reset the password ─────────────────────────────────────────────


def test_password_reset_full_flow(client, user) -> None:
    """End-to-end: request code, verify, set new password, old one invalid."""
    _request_reset(client, user.email)
    otp = _latest_otp(client.application, user)
    _submit_otp(client, otp.otp)

    resp = _submit_new_password(client, STRONG_PASSWORD)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "success" in body.lower()

    with client.application.app_context():
        from storage import User, db
        fresh = db.session.get(User, user.id)
        assert fresh is not None
        assert fresh.check_password(STRONG_PASSWORD)
        assert not fresh.check_password("OldPass123!")

    # Outstanding reset OTPs are invalidated
    otp = _latest_otp(client.application, user)
    assert otp.used is True

    with client.session_transaction() as sess:
        assert "reset_email" not in sess
        assert "otp_verified" not in sess


def test_password_reset_requires_verified_step(client, user) -> None:
    """Submitting a password without verifying the code is rejected."""
    _request_reset(client, user.email)
    resp = _submit_new_password(client, STRONG_PASSWORD)
    assert resp.status_code == 200
    assert b"verify your code" in resp.data.lower()


def test_password_reset_weak_password(client, user) -> None:
    """Weak passwords are rejected by the strength validator."""
    _request_reset(client, user.email)
    otp = _latest_otp(client.application, user)
    _submit_otp(client, otp.otp)

    resp = _submit_new_password(client, "short")
    assert resp.status_code == 200
    assert b"password" in resp.data.lower()


def test_password_reset_mismatch(client, user) -> None:
    """Mismatched confirmation is rejected."""
    _request_reset(client, user.email)
    otp = _latest_otp(client.application, user)
    _submit_otp(client, otp.otp)

    resp = _submit_new_password(client, STRONG_PASSWORD, "DifferentP@ss1")
    assert resp.status_code == 200
    assert b"do not match" in resp.data.lower()


# ── Resend OTP ─────────────────────────────────────────────────────


def test_resend_otp_reset_password(client, user) -> None:
    """Resending issues a fresh code and supersedes the previous one."""
    _request_reset(client, user.email)
    old_otp = _latest_otp(client.application, user)

    # Cooldown applies; bypass it to prove the resend itself works.
    import app as app_module
    app_module._OTP_REQUEST_STORE.clear()

    resp = client.post("/resend-otp", data={"purpose": "reset_password"})
    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()
    assert data["success"] is True

    new_otp = _latest_otp(client.application, user)
    assert new_otp.id != old_otp.id
    assert new_otp.used is False

    with client.application.app_context():
        from storage import VerificationOTP, db
        fresh_old = db.session.get(VerificationOTP, old_otp.id)
        assert fresh_old is not None
        assert fresh_old.used is True


def test_resend_otp_cooldown(client, user) -> None:
    """Resending within the cooldown window returns 429."""
    _request_reset(client, user.email)
    resp = client.post("/resend-otp", data={"purpose": "reset_password"})
    assert resp.status_code in (200, 429)
    if resp.status_code == 200:
        resp = client.post("/resend-otp", data={"purpose": "reset_password"})
    assert resp.status_code == 429
    assert resp.is_json
    assert resp.get_json()["success"] is False


def test_resend_otp_requires_email(client) -> None:
    """Resend without any session/email context fails gracefully."""
    resp = client.post("/resend-otp", data={"purpose": "reset_password"})
    assert resp.status_code in (400, 404)
    assert resp.is_json
    assert resp.get_json()["success"] is False
