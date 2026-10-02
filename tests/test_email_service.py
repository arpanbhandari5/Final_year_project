"""
Prayash — Email Service Tests
==============================
Unit tests for the SMTP/email configuration and delivery helpers in
``storage.py`` (OTP verification and password-reset emails).

Run with::

    pytest tests/test_email_service.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL",
                       f"sqlite:///{PROJECT_ROOT / 'instance' / 'test_prayash.db'}")


def test_resolve_from_email_explicit_wins() -> None:
    """An explicit, real From address is kept as-is."""
    from storage import _resolve_from_email

    assert _resolve_from_email("hello@example.org", "user@gmail.com") == "hello@example.org"


def test_resolve_from_email_empty_falls_back_to_username() -> None:
    """Empty From falls back to the authenticated SMTP username."""
    from storage import _resolve_from_email

    assert _resolve_from_email("", "user@gmail.com") == "user@gmail.com"


def test_resolve_from_email_placeholder_falls_back_to_username() -> None:
    """Placeholder domains (prayash.local etc.) fall back to the username."""
    from storage import _resolve_from_email

    assert _resolve_from_email("noreply@prayash.local", "user@gmail.com") == "user@gmail.com"
    assert _resolve_from_email("noreply@localhost", "user@gmail.com") == "user@gmail.com"
    assert _resolve_from_email("noreply@example.com", "user@gmail.com") == "user@gmail.com"


def test_resolve_from_email_no_username() -> None:
    """Without a username, the placeholder is returned rather than crashing."""
    from storage import _resolve_from_email

    assert _resolve_from_email("noreply@prayash.local", "") == ""


def test_send_email_without_credentials_returns_true(monkeypatch) -> None:
    """With no SMTP credentials, send_email logs to console but still returns
    True so the caller never reveals whether an account exists."""
    import storage

    monkeypatch.setattr(
        storage,
        "_MAIL_CONFIG",
        {**storage._MAIL_CONFIG,
         "username": "",
         "password": ""},
    )

    result = storage.send_email(
        "test@example.com",
        "Test subject",
        "<html><body>Test</body></html>",
        "Test body",
    )
    assert result is True


def test_send_email_uses_flask_mail_when_credentials_set(monkeypatch) -> None:
    """With credentials configured, send_email builds a Flask-Mail Message
    addressed to the recipient with the OTP payload."""
    import storage

    captured: dict = {}

    def fake_mail_send(msg):
        captured["recipients"] = msg.recipients
        captured["subject"] = msg.subject
        captured["html"] = msg.html
        captured["text"] = msg.body

    monkeypatch.setattr(
        storage,
        "_MAIL_CONFIG",
        {**storage._MAIL_CONFIG,
         "username": "sender@gmail.com",
         "password": "app-password",
         "from_email": "sender@gmail.com",
         "from_name": "Prayash"},
    )
    monkeypatch.setattr(storage.mail, "send", fake_mail_send)

    from app import app as flask_app
    with flask_app.app_context():
        result = storage.send_email(
            "to@example.com",
            "Reset your Prayash password",
            "<html><body>Your code: 123456</body></html>",
            "Your code: 123456",
        )
    assert result is True
    assert captured["recipients"] == ["to@example.com"]
    assert captured["subject"] == "Reset your Prayash password"
    assert "123456" in captured["html"] and "123456" in captured["text"]
