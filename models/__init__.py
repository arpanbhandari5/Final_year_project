"""
Prayash — Models Package
=========================
Holds the SQLAlchemy models for the ChatGPT-style career assistant.

Importing this package registers every model on the shared ``db`` instance
so that ``db.create_all()`` (and Alembic-style metadata) includes the new
tables. The legacy models (User, Upload, Feedback, VerificationOTP) live in
``storage.py`` for backward compatibility.
"""

from __future__ import annotations

from datetime import UTC, datetime

from extensions import db


def utc_now() -> datetime:
    """Naive UTC datetime, consistent with what SQLite stores/returns."""
    return datetime.now(UTC).replace(tzinfo=None)


# Register the chatbot + profile models so create_all() knows about them.
from . import chat, profile, upload  # noqa: E402

__all__ = ["chat", "db", "profile", "upload", "utc_now"]
