"""
Prayash — Career Chat Blueprint Tests
======================================
Tests for the ChatGPT-style assistant blueprint (routes/chat.py):

    GET  /chatbot                          → page (login required)
    POST /api/chat/conversations           → create
    GET  /api/chat/conversations           → list (+ ?q= search)
    GET  /api/chat/conversations/<id>      → detail
    PATCH/DELETE /api/chat/conversations/<id>
    POST /api/chat/conversations/<id>/stream  → SSE streaming
    POST /api/chat/messages/<id>/feedback  → like / dislike
    GET  /api/chat/suggestions
    POST /api/chat/tools/<tool>            → career tools
    POST /api/chat/context                 → file upload
    GET  /api/chat/conversations/<id>/export

The LLM layer is monkeypatched so tests never touch real API endpoints —
only the HTTP layer + rule-based services are exercised.

Run with::

    pytest tests/test_chat_blueprint.py -v
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Neutralise email + LLM providers before importing the app so no test ever
# reaches out to a real service (load_dotenv never overrides existing vars).
os.environ.setdefault("MAIL_USERNAME", "")
os.environ.setdefault("MAIL_PASSWORD", "")
os.environ.setdefault("SMTP_USERNAME", "")
os.environ.setdefault("SMTP_PASSWORD", "")
os.environ.setdefault("LLM_PROVIDER", "")
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:1")  # unreachable

_TEST_DB_DIR = Path(tempfile.mkdtemp())
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(_TEST_DB_DIR / 'chat_test.db').as_posix()}")


# The session-scoped ``app`` and ``client`` fixtures come from conftest.py.


@pytest.fixture
def auth_client(app, monkeypatch):
    """A logged-in test client with the LLM layer mocked to be deterministic."""
    import services.ai_service as ai_service

    def fake_stream_reply(question, history=None, context="", cancel_token="", max_tokens=None):
        yield ("meta", {"mode": "rule-based"})
        yield ("token", "Hello from ")
        yield ("token", "the test assistant.")
        yield ("done", "Hello from the test assistant.")

    def fake_generate_reply(question, history=None, context=""):
        return "Hello from the test assistant.", "rule-based"

    monkeypatch.setattr(ai_service, "stream_reply", fake_stream_reply)
    monkeypatch.setattr(ai_service, "generate_reply", fake_generate_reply)

    from storage import create_user, db

    with app.app_context():
        u = create_user("chatblue@example.com", "CorrectPass1!", full_name="Chat Blue", username="chatblue")
        u.email_verified = True
        db.session.commit()

    c = app.test_client()
    resp = c.post("/login", data={"email": "chatblue@example.com", "password": "CorrectPass1!"})
    assert resp.status_code == 302, "Login should redirect"
    return c


def _new_conversation(client) -> int:
    resp = client.post("/api/chat/conversations", json={})
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()["conversation"]["id"]


# ── Page ─────────────────────────────────────────────────────────


def test_chatbot_page_requires_login(client):
    resp = client.get("/chatbot")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_chatbot_page_renders(auth_client):
    resp = auth_client.get("/chatbot")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "chatbot-app" in body
    assert "data-chat-input" in body


# ── Conversation CRUD ─────────────────────────────────────────────


def test_create_and_list_conversations(auth_client):
    cid = _new_conversation(auth_client)
    resp = auth_client.get("/api/chat/conversations")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    ids = [c["id"] for c in data["conversations"]]
    assert cid in ids


def test_conversation_ownership_isolation(app, auth_client):
    """Another user must not be able to read this user's conversation."""
    cid = _new_conversation(auth_client)

    from storage import create_user, db

    with app.app_context():
        other = create_user("other@example.com", "CorrectPass1!", full_name="Other", username="otheruser")
        other.email_verified = True
        db.session.commit()

    other_client = app.test_client()
    other_client.post("/login", data={"email": "other@example.com", "password": "CorrectPass1!"})

    resp = other_client.get(f"/api/chat/conversations/{cid}")
    assert resp.status_code == 404
    resp = other_client.patch(f"/api/chat/conversations/{cid}", json={"title": "hacked"})
    assert resp.status_code == 404
    resp = other_client.delete(f"/api/chat/conversations/{cid}")
    assert resp.status_code == 404


def test_rename_and_delete_conversation(auth_client):
    cid = _new_conversation(auth_client)
    resp = auth_client.patch(f"/api/chat/conversations/{cid}", json={"title": "My career plan"})
    assert resp.status_code == 200
    resp = auth_client.get(f"/api/chat/conversations/{cid}")
    assert resp.get_json()["conversation"]["title"] == "My career plan"

    resp = auth_client.delete(f"/api/chat/conversations/{cid}")
    assert resp.status_code == 200
    resp = auth_client.get(f"/api/chat/conversations/{cid}")
    assert resp.status_code == 404


def test_clear_history(auth_client):
    _new_conversation(auth_client)
    _new_conversation(auth_client)
    resp = auth_client.post("/api/chat/clear", json={})
    assert resp.status_code == 200
    assert resp.get_json()["deleted"] >= 2
    resp = auth_client.get("/api/chat/conversations")
    assert resp.get_json()["conversations"] == []


# ── Messaging (streaming) ─────────────────────────────────────────


def test_stream_message_events(auth_client):
    cid = _new_conversation(auth_client)
    resp = auth_client.post(
        f"/api/chat/conversations/{cid}/stream",
        json={"message": "Hello assistant"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    body = resp.get_data(as_text=True)  # consumes the stream (runs the generator)

    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body

    events = {}
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        event = "message"
        data = ""
        for line in frame.split("\n"):
            if line.startswith("event: "):
                event = line[7:].strip()
            elif line.startswith("data: "):
                data += line[6:]
        if data:
            events.setdefault(event, []).append(json.loads(data))

    # done event should carry the full reply
    done = events.get("done", [])
    assert done
    assert "Hello from the test assistant." in done[0]["content"]
    assert done[0]["message_id"] is not None

    # The assistant message must now be persisted
    detail = auth_client.get(f"/api/chat/conversations/{cid}").get_json()["conversation"]
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]


def test_stream_empty_message_rejected(auth_client):
    cid = _new_conversation(auth_client)
    resp = auth_client.post(f"/api/chat/conversations/{cid}/stream", json={"message": ""})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ── Suggestions & tools ───────────────────────────────────────────


def test_suggestions(auth_client):
    resp = auth_client.get("/api/chat/suggestions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["suggestions"]) > 0


def test_tool_requires_resume(auth_client):
    resp = auth_client.post("/api/chat/tools/ats", json={"resume_text": "short"})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_tool_ats_returns_markdown(auth_client):
    resume = "Python developer with 3 years of experience in machine learning and data science."
    resp = auth_client.post("/api/chat/tools/ats", json={"resume_text": resume})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["tool"] == "ats"
    assert data["markdown"] and len(data["markdown"]) > 20


def test_unknown_tool(auth_client):
    resp = auth_client.post("/api/chat/tools/nope", json={"resume_text": "x" * 40})
    assert resp.status_code == 404


# ── Uploads ───────────────────────────────────────────────────────


def test_upload_context_requires_login(client):
    resp = client.post(
        "/api/chat/context",
        data={"file": (io.BytesIO(b"Python, Django, teamwork."), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401


def test_upload_context_txt(auth_client):
    resp = auth_client.post(
        "/api/chat/context",
        data={"file": (io.BytesIO(b"Python, Django, teamwork, leadership skills."), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["file"]["id"] > 0
    assert data["file"]["filename"] == "notes.txt"
    assert data["char_count"] >= 20
    assert data["skill_count"] >= 1


def test_upload_context_rejects_bad_extension(auth_client):
    resp = auth_client.post(
        "/api/chat/context",
        data={"file": (io.BytesIO(b"MZ..."), "evil.exe")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


# ── Feedback & export ─────────────────────────────────────────────


def test_message_feedback(auth_client):
    cid = _new_conversation(auth_client)
    stream_resp = auth_client.post(f"/api/chat/conversations/{cid}/stream", json={"message": "Hello"})
    assert stream_resp.status_code == 200, stream_resp.get_data(as_text=True)[:500]
    stream_resp.get_data(as_text=True)  # consume so the message is persisted
    detail = auth_client.get(f"/api/chat/conversations/{cid}").get_json()["conversation"]
    assistant_msg = next(m for m in detail["messages"] if m["role"] == "assistant")

    resp = auth_client.post(f"/api/chat/messages/{assistant_msg['id']}/feedback", json={"value": "like"})
    assert resp.status_code == 200

    detail = auth_client.get(f"/api/chat/conversations/{cid}").get_json()["conversation"]
    updated = next(m for m in detail["messages"] if m["role"] == "assistant")
    assert updated["feedback"] == "like"


def test_export_txt(auth_client):
    cid = _new_conversation(auth_client)
    stream_resp = auth_client.post(f"/api/chat/conversations/{cid}/stream", json={"message": "Hello"})
    assert stream_resp.status_code == 200
    stream_resp.get_data(as_text=True)  # consume so the message is persisted
    resp = auth_client.get(f"/api/chat/conversations/{cid}/export?format=txt")
    assert resp.status_code == 200
    assert "text/plain" in resp.mimetype
    assert "Hello from the test assistant." in resp.get_data(as_text=True)


def test_export_requires_login(client):
    """API endpoints return a JSON 401 (not a redirect) when unauthenticated."""
    resp = client.get("/api/chat/conversations/1/export?format=txt")
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False
