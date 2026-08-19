"""
Prayash — Chat Models
======================
Persistent conversation storage for the career AI assistant.

These models keep every conversation per-user so a logged-in member can
load, continue, rename, delete and export their chat history. They are
database-agnostic (PostgreSQL in production, SQLite in development).

Models:
    - ChatConversation  a named thread of messages owned by a user
    - ChatMessage       a single user/assistant turn inside a conversation
    - AIFeedback        like/dislike rating recorded against a message
"""

from __future__ import annotations

from extensions import db
from models import utc_now


class ChatConversation(db.Model):
    """A user-owned conversation thread."""

    __tablename__ = "chat_conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, default="New conversation")
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    messages = db.relationship(
        "ChatMessage",
        backref="conversation",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="ChatMessage.created_at",
    )
    files = db.relationship(
        "UploadedFile",
        backref="conversation",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ChatConversation {self.id} user={self.user_id}>"


class ChatMessage(db.Model):
    """A single turn (user or assistant) within a conversation."""

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("chat_conversations.id"), nullable=False, index=True
    )
    role = db.Column(db.String(10), nullable=False)  # "user" | "assistant"
    content = db.Column(db.Text, nullable=False, default="")
    edited = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    feedback = db.relationship(
        "AIFeedback",
        backref="message",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ChatMessage {self.id} role={self.role}>"


class AIFeedback(db.Model):
    """Like/dislike rating captured for an assistant message."""

    __tablename__ = "ai_feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    message_id = db.Column(
        db.Integer, db.ForeignKey("chat_messages.id"), nullable=False, index=True
    )
    value = db.Column(db.String(10), nullable=False)  # "like" | "dislike"
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    __table_args__ = (
        db.UniqueConstraint("user_id", "message_id", name="uq_ai_feedback_user_message"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AIFeedback {self.id} value={self.value}>"
