"""
Prayash — Chat Services
========================
Persistence layer for conversations, messages and feedback.

All queries are scoped to the current user so one user can never read,
modify or delete another user's conversations (multi-tenant safety).
"""

from __future__ import annotations

import logging
from typing import Any

from extensions import db
from models.chat import AIFeedback, ChatConversation, ChatMessage
from services import upload_service

log = logging.getLogger("prayash.chat")

MAX_TITLE_CHARS = 60


def suggest_title(text: str) -> str:
    """Derive a short, human-friendly conversation title from a message."""
    cleaned = (text or "").strip().replace("\n", " ")
    words = cleaned.split()
    title = " ".join(words[:8])
    if len(title) > MAX_TITLE_CHARS:
        title = title[: MAX_TITLE_CHARS - 1] + "…"
    return title or "New conversation"


def _owned_conversation(user_id: int, conversation_id: int) -> ChatConversation | None:
    """Fetch a conversation only if it belongs to *user_id*."""
    return ChatConversation.query.filter_by(id=conversation_id, user_id=user_id).first()


def list_conversations(user_id: int, search: str = "") -> list[dict[str, Any]]:
    """Return the user's conversations (newest first), optionally filtered
    by a case-insensitive title search."""
    query = ChatConversation.query.filter_by(user_id=user_id)
    search = (search or "").strip()
    if search:
        query = query.filter(ChatConversation.title.ilike(f"%{search}%"))
    conversations = query.order_by(ChatConversation.updated_at.desc()).limit(100).all()
    return [conversation_to_dict(c) for c in conversations]


def conversation_to_dict(conversation: ChatConversation) -> dict[str, Any]:
    """Serialise a conversation without loading every message."""
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "message_count": conversation.messages.count(),
        "file_count": conversation.files.count(),
    }


def create_conversation(user_id: int, title: str | None = None) -> ChatConversation:
    """Create a new conversation for the user."""
    conversation = ChatConversation(
        user_id=user_id,
        title=(title or "New conversation")[:200],
    )
    db.session.add(conversation)
    db.session.commit()
    return conversation


def get_conversation(user_id: int, conversation_id: int) -> ChatConversation | None:
    """Fetch a conversation owned by *user_id*."""
    return _owned_conversation(user_id, conversation_id)


def get_conversation_detail(user_id: int, conversation_id: int) -> dict[str, Any] | None:
    """Fetch a conversation including its messages and attached files."""
    conversation = _owned_conversation(user_id, conversation_id)
    if conversation is None:
        return None
    data = conversation_to_dict(conversation)
    data["messages"] = [message_to_dict(m) for m in conversation.messages.order_by(ChatMessage.created_at.asc()).all()]
    data["files"] = [upload_service.file_to_dict(f) for f in conversation.files.all()]
    return data


def rename_conversation(user_id: int, conversation_id: int, title: str) -> bool:
    """Rename a conversation. Returns False if not found / not owned."""
    conversation = _owned_conversation(user_id, conversation_id)
    if conversation is None:
        return False
    conversation.title = (title or "").strip()[:200] or "New conversation"
    db.session.commit()
    return True


def touch_conversation(conversation: ChatConversation) -> None:
    """Bump updated_at so the conversation floats to the top of the list."""
    conversation.updated_at = conversation.updated_at  # rely on onupdate
    db.session.add(conversation)
    db.session.commit()


def delete_conversation(user_id: int, conversation_id: int) -> bool:
    """Delete a conversation and its files from disk + DB."""
    conversation = _owned_conversation(user_id, conversation_id)
    if conversation is None:
        return False
    for file_record in conversation.files.all():
        try:
            upload_service.delete_upload(file_record.id, user_id)
        except Exception:
            log.warning("Could not delete file for conversation %s", conversation_id)
    db.session.delete(conversation)
    db.session.commit()
    return True


def clear_history(user_id: int) -> int:
    """Delete every conversation owned by the user. Returns count removed."""
    conversations = ChatConversation.query.filter_by(user_id=user_id).all()
    count = 0
    for conversation in conversations:
        for file_record in conversation.files.all():
            try:
                upload_service.delete_upload(file_record.id, user_id)
            except Exception:
                log.warning("Could not delete file %s", file_record.id)
        db.session.delete(conversation)
        count += 1
    db.session.commit()
    return count


# ── Messages ──────────────────────────────────────────────────────────

def add_message(conversation: ChatConversation, role: str, content: str) -> ChatMessage:
    """Append a message to a conversation."""
    message = ChatMessage(
        conversation_id=conversation.id,
        role=role,
        content=content or "",
    )
    db.session.add(message)
    db.session.commit()
    return message


def get_message(conversation: ChatConversation, message_id: int) -> ChatMessage | None:
    """Fetch a message that belongs to *conversation*."""
    return ChatMessage.query.filter_by(id=message_id, conversation_id=conversation.id).first()


def update_message(message: ChatMessage, content: str) -> None:
    """Replace a message's content (marks it as edited)."""
    message.content = content or ""
    message.edited = True
    db.session.commit()


def delete_messages_after(conversation: ChatConversation, message_id: int) -> None:
    """Delete every message created after *message_id* (used when editing or
    regenerating so the thread stays coherent)."""
    anchor = get_message(conversation, message_id)
    if anchor is None:
        return
    ChatMessage.query.filter(
        ChatMessage.conversation_id == conversation.id,
        ChatMessage.created_at > anchor.created_at,
    ).delete(synchronize_session=False)
    db.session.commit()


def pop_last_assistant(conversation: ChatConversation) -> ChatMessage | None:
    """Remove and return the trailing assistant message (for regenerate)."""
    message = (
        ChatMessage.query.filter_by(
            conversation_id=conversation.id, role="assistant"
        )
        .order_by(ChatMessage.created_at.desc())
        .first()
    )
    if message is None:
        return None
    db.session.delete(message)
    db.session.commit()
    return message


def build_history(conversation: ChatConversation, limit: int = 20) -> list[dict[str, str]]:
    """Recent messages as ``{role, content}`` for the LLM."""
    messages = conversation.messages.order_by(ChatMessage.created_at.asc()).all()
    return [{"role": m.role, "content": m.content} for m in messages[-limit:]]


def message_to_dict(message: ChatMessage) -> dict[str, Any]:
    """Serialise a message including its feedback state."""
    feedback = None
    if message.feedback is not None:
        feedback = message.feedback.value
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "edited": message.edited,
        "feedback": feedback,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


# ── Feedback ──────────────────────────────────────────────────────────

def set_feedback(user_id: int, message_id: int, value: str) -> bool:
    """Record or update like/dislike for a message (idempotent per user)."""
    if value not in ("like", "dislike"):
        return False
    record = AIFeedback.query.filter_by(user_id=user_id, message_id=message_id).first()
    if record is None:
        record = AIFeedback(user_id=user_id, message_id=message_id, value=value)
        db.session.add(record)
    else:
        record.value = value
    db.session.commit()
    return True


# ── Context & files ───────────────────────────────────────────────────

def link_files(conversation: ChatConversation, file_ids: list[int], user_id: int) -> list[int]:
    """Attach a set of uploads (owned by *user_id*) to a conversation.
    Returns the ids that were successfully linked."""
    linked: list[int] = []
    for fid in file_ids or []:
        record = upload_service.get_upload(fid, user_id)
        if record is None:
            continue
        record.conversation_id = conversation.id
        linked.append(record.id)
    if linked:
        db.session.commit()
    return linked


def context_for_conversation(
    conversation: ChatConversation, file_ids: list[int] | None = None, user_id: int | None = None
) -> str:
    """Extract LLM context from the conversation's attached files plus any
    freshly referenced uploads."""
    files = list(conversation.files.all())
    if user_id is not None:
        for fid in file_ids or []:
            record = upload_service.get_upload(fid, user_id)
            if record is not None and record.id not in {f.id for f in files}:
                files.append(record)
    return upload_service.context_from_files(files)
