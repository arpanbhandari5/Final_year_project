"""
Prayash — Chat Blueprint
=========================
HTTP layer for the ChatGPT-style career assistant page.

Routes:
    GET  /chatbot                             → the chatbot UI (login required)
    GET  /api/chat/conversations              → list (+ ?q= search)
    POST /api/chat/conversations              → create a conversation
    GET  /api/chat/conversations/<cid>        → detail (messages + files)
    PATCH /api/chat/conversations/<cid>       → rename
    DELETE /api/chat/conversations/<cid>      → delete
    POST /api/chat/conversations/<cid>/stop   → stop generation
    POST /api/chat/conversations/<cid>/messages → non-streaming reply
    POST /api/chat/conversations/<cid>/stream → SSE streaming reply
    PATCH /api/chat/messages/<mid>            → edit a user message
    POST /api/chat/messages/<mid>/feedback    → like / dislike
    POST /api/chat/messages/<mid>/regenerate  → regenerate reply
    POST /api/chat/clear                      → clear all history
    GET  /api/chat/suggestions                → suggested prompts
    GET  /api/chat/conversations/<cid>/export → TXT / DOCX / PDF export
    POST /api/chat/tools/<tool>               → career intelligence tools

All endpoints are scoped to the authenticated user.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

from flask import Blueprint, Response, jsonify, render_template, request, send_file, stream_with_context
from flask_login import current_user, login_required

from extensions import db
from security import rate_limit
from services import ai_service, chat_service, resume_service, upload_service
from services.upload_service import file_to_dict

log = logging.getLogger("prayash.routes.chat")

chat_bp = Blueprint("chat_bp", __name__)

# Conversation title used until the first user message sets a real one.
DEFAULT_TITLE = "New conversation"


# ── Rate limiting ────────────────────────────────────────────────────
# Uses the shared sliding-window limiter from security.py (per-IP,
# bypassed under TESTING) instead of a second private implementation.


def _json_payload() -> dict[str, Any]:
    """Return the JSON body (or form fallback) as a dict."""
    data = request.get_json(silent=True)
    if data is not None and isinstance(data, dict):
        return data
    return {k: v for k, v in request.form.items()}


# ════════════════════════════════════════════════════════════════════
# Page
# ════════════════════════════════════════════════════════════════════


@chat_bp.get("/chatbot")
@login_required
def chatbot_page():
    """Render the ChatGPT-style career assistant page."""
    return render_template(
        "chatbot.html",
        active_page="chatbot",
        title="AI Career Assistant | Prayash",
    )


# ════════════════════════════════════════════════════════════════════
# Conversation management
# ════════════════════════════════════════════════════════════════════


@chat_bp.get("/api/chat/conversations")
@login_required
@rate_limit
def list_conversations():
    """List the user's conversations (optionally filtered by ?q=)."""
    search = request.args.get("q", "").strip()
    conversations = chat_service.list_conversations(current_user.id, search=search)
    return jsonify({"success": True, "conversations": conversations, "total": len(conversations)})


@chat_bp.post("/api/chat/conversations")
@login_required
@rate_limit
def create_conversation():
    """Create a new conversation."""
    payload = _json_payload()
    title = (payload.get("title") or "").strip() or DEFAULT_TITLE
    conversation = chat_service.create_conversation(current_user.id, title=title)
    return jsonify({"success": True, "conversation": chat_service.conversation_to_dict(conversation)}), 201


@chat_bp.get("/api/chat/conversations/<int:conversation_id>")
@login_required
def get_conversation(conversation_id: int):
    """Return a conversation with all its messages and files."""
    data = chat_service.get_conversation_detail(current_user.id, conversation_id)
    if data is None:
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    return jsonify({"success": True, "conversation": data})


@chat_bp.patch("/api/chat/conversations/<int:conversation_id>")
@login_required
@rate_limit
def rename_conversation(conversation_id: int):
    """Rename a conversation."""
    payload = _json_payload()
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "Title cannot be empty."}), 400
    if not chat_service.rename_conversation(current_user.id, conversation_id, title):
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    return jsonify({"success": True})


@chat_bp.delete("/api/chat/conversations/<int:conversation_id>")
@login_required
def delete_conversation(conversation_id: int):
    """Delete a conversation and its files."""
    if not chat_service.delete_conversation(current_user.id, conversation_id):
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    return jsonify({"success": True})


@chat_bp.post("/api/chat/clear")
@login_required
@rate_limit
def clear_history():
    """Delete every conversation belonging to the user."""
    count = chat_service.clear_history(current_user.id)
    return jsonify({"success": True, "deleted": count})


# ════════════════════════════════════════════════════════════════════
# Generation helpers
# ════════════════════════════════════════════════════════════════════


def _history_until(conversation, messages: list, exclude_last_user: bool = False) -> list[dict[str, str]]:
    """Convert a list of messages to LLM history, optionally dropping the
    trailing user message (which becomes the prompt)."""
    items = [{"role": m.role, "content": m.content} for m in messages]
    if exclude_last_user and items and items[-1]["role"] == "user":
        items = items[:-1]
    return items[-20:]


def _prepare_generation(
    user_id: int, conversation, payload: dict[str, Any]
) -> tuple[str | None, list[dict[str, str]] | None, str | None]:
    """Handle the send / regenerate / edit-from flows.

    Returns ``(prompt, history, error)``. ``history`` is the message list
    to feed the LLM (the prompt itself is passed separately so it is not
    duplicated in the transcript).
    """
    regenerate = bool(payload.get("regenerate"))
    regenerate_from = payload.get("regenerate_from")
    message = (payload.get("message") or "").strip()

    if regenerate:
        chat_service.pop_last_assistant(conversation)
        messages = list(conversation.messages.order_by("created_at").all())
        if not messages:
            return None, None, "Nothing to regenerate."
        prompt = messages[-1].content
        history = _history_until(conversation, messages, exclude_last_user=True)
        return prompt, history, None

    if regenerate_from:
        anchor = chat_service.get_message(conversation, int(regenerate_from))
        if anchor is None or anchor.role != "user":
            return None, None, "Cannot regenerate from that message."
        chat_service.delete_messages_after(conversation, anchor.id)
        messages = list(conversation.messages.order_by("created_at").all())
        prompt = anchor.content
        history = _history_until(conversation, messages, exclude_last_user=True)
        return prompt, history, None

    # Normal send
    if not message:
        return None, None, "Please enter a message."
    messages = list(conversation.messages.order_by("created_at").all())
    history = _history_until(conversation, messages)
    chat_service.add_message(conversation, "user", message)
    if conversation.title == DEFAULT_TITLE:
        conversation.title = chat_service.suggest_title(message)
        db.session.commit()
    return message, history, None


def _resolve_context(conversation, payload: dict[str, Any]) -> str:
    """Build LLM context for a message send.

    Two sources, combined:
    1. Attached files (existing + freshly referenced via ``file_ids``).
    2. An optional inline ``context`` string from the client (used by the
       workspace AI Assistant page to pass a privacy-safe summary of the
       user's latest resume analysis: risk, skills, top matches). This is
       already-derived display data — no resume text or secrets — so the
       assistant can answer "What skills am I missing?" from real results
       instead of replying generically.
    """
    chat_service.link_files(conversation, payload.get("file_ids") or [], current_user.id)
    file_context = chat_service.context_for_conversation(conversation, payload.get("file_ids"), current_user.id)
    inline_context = str(payload.get("context") or "").strip()
    if file_context and inline_context:
        return f"{file_context}\n\n{inline_context}"
    return file_context or inline_context


def _cancel_token(conversation_id: int) -> str:
    return f"{current_user.id}:{conversation_id}"


def _sse(event: str, data: dict[str, Any]) -> Iterator[str]:
    """Serialize one SSE frame."""
    yield f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ════════════════════════════════════════════════════════════════════
# Send message (non-streaming JSON reply)
# ════════════════════════════════════════════════════════════════════


@chat_bp.post("/api/chat/conversations/<int:conversation_id>/messages")
@login_required
@rate_limit
def send_message(conversation_id: int):
    """Send a message and return the assistant's reply as JSON."""
    conversation = chat_service.get_conversation(current_user.id, conversation_id)
    if conversation is None:
        return jsonify({"success": False, "error": "Conversation not found."}), 404

    payload = _json_payload()
    prompt, history, error = _prepare_generation(current_user.id, conversation, payload)
    if error:
        return jsonify({"success": False, "error": error}), 400

    context = _resolve_context(conversation, payload)
    reply, mode = ai_service.generate_reply(prompt, history=history, context=context)

    message = chat_service.add_message(conversation, "assistant", reply)
    return jsonify(
        {
            "success": True,
            "reply": reply,
            "mode": mode,
            "message_id": message.id,
            "conversation": chat_service.conversation_to_dict(conversation),
        }
    )


# ════════════════════════════════════════════════════════════════════
# Send message (streaming SSE)
# ════════════════════════════════════════════════════════════════════


@chat_bp.post("/api/chat/conversations/<int:conversation_id>/stream")
@login_required
@rate_limit
def stream_message(conversation_id: int):
    """Send a message and stream the assistant's reply token-by-token.

    The response is a Server-Sent Events stream. Events:
        meta   → {conversation_id, title}
        token  → {content}
        done   → {content, message_id, cancelled}
        error  → {error}
    """
    conversation = chat_service.get_conversation(current_user.id, conversation_id)
    if conversation is None:
        return jsonify({"success": False, "error": "Conversation not found."}), 404

    payload = _json_payload()
    prompt, history, error = _prepare_generation(current_user.id, conversation, payload)
    if error:
        return jsonify({"success": False, "error": error}), 400

    context = _resolve_context(conversation, payload)
    cancel_token = _cancel_token(conversation_id)
    ai_service.clear_cancel(cancel_token)

    def generate() -> Iterator[str]:
        full = ""
        yield from _sse("meta", {"conversation_id": conversation_id, "title": conversation.title})
        try:
            for kind, item in ai_service.stream_reply(
                prompt, history=history, context=context, cancel_token=cancel_token
            ):
                if kind == "token":
                    full += item
                    yield from _sse("token", {"content": item})
                elif kind == "error":
                    yield from _sse("error", {"error": item})
                    break

            stopped = ai_service.is_cancelled(cancel_token)
            if full.strip():
                message = chat_service.add_message(conversation, "assistant", full.strip())
                yield from _sse(
                    "done",
                    {
                        "content": full.strip(),
                        "message_id": message.id,
                        "cancelled": stopped,
                    },
                )
            elif not stopped:
                yield from _sse(
                    "error",
                    {
                        "error": "The assistant returned an empty response. Please try again.",
                    },
                )
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Stream generation failed for conversation %s", conversation_id)
            yield from _sse("error", {"error": f"Something went wrong: {exc}"})
        finally:
            ai_service.clear_cancel(cancel_token)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@chat_bp.post("/api/chat/conversations/<int:conversation_id>/stop")
@login_required
@rate_limit
def stop_generation(conversation_id: int):
    """Ask an in-flight generation to stop (the stream persists partial text)."""
    if chat_service.get_conversation(current_user.id, conversation_id) is None:
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    ai_service.request_cancel(_cancel_token(conversation_id))
    return jsonify({"success": True})


# ════════════════════════════════════════════════════════════════════
# Message actions
# ════════════════════════════════════════════════════════════════════


@chat_bp.patch("/api/chat/messages/<int:message_id>")
@login_required
@rate_limit
def edit_message(message_id: int):
    """Edit a user message's content. The frontend then triggers a
    regenerate from that point to keep the thread coherent."""
    conversation_id = request.args.get("conversation_id", type=int)
    if not conversation_id:
        return jsonify({"success": False, "error": "conversation_id is required."}), 400
    conversation = chat_service.get_conversation(current_user.id, conversation_id)
    if conversation is None:
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    message = chat_service.get_message(conversation, message_id)
    if message is None:
        return jsonify({"success": False, "error": "Message not found."}), 404
    if message.role != "user":
        return jsonify({"success": False, "error": "Only user messages can be edited."}), 400

    payload = _json_payload()
    content = (payload.get("content") or "").strip()
    if not content:
        return jsonify({"success": False, "error": "Message cannot be empty."}), 400

    chat_service.update_message(message, content)
    if conversation.title == DEFAULT_TITLE:
        conversation.title = chat_service.suggest_title(content)
        db.session.commit()

    # If requested, prune everything after the edited message so the thread
    # can be regenerated from here without stale context.
    if payload.get("prune"):
        chat_service.delete_messages_after(conversation, message.id)

    return jsonify({"success": True, "message": chat_service.message_to_dict(message)})


@chat_bp.post("/api/chat/messages/<int:message_id>/feedback")
@login_required
@rate_limit
def message_feedback(message_id: int):
    """Record like/dislike feedback for an assistant message."""
    payload = _json_payload()
    value = (payload.get("value") or "").strip().lower()
    if value not in ("like", "dislike"):
        return jsonify({"success": False, "error": "Feedback value must be 'like' or 'dislike'."}), 400
    if not chat_service.set_feedback(current_user.id, message_id, value):
        return jsonify({"success": False, "error": "Message not found."}), 404
    return jsonify({"success": True})


# ════════════════════════════════════════════════════════════════════
# Suggestions
# ════════════════════════════════════════════════════════════════════


@chat_bp.get("/api/chat/suggestions")
def suggestions():
    """Curated suggested prompts shown when a chat is empty."""
    items = [
        {"label": "Analyse my resume", "prompt": "Please analyse my resume and give me a full career overview."},
        {"label": "ATS score", "prompt": "Run an ATS score for my resume and tell me how to improve it."},
        {"label": "Skill gaps", "prompt": "What skill gaps do I have for a software engineer role?"},
        {"label": "Interview prep", "prompt": "Generate interview questions based on my profile."},
        {"label": "Cover letter", "prompt": "Draft a cover letter for me."},
        {"label": "Learning roadmap", "prompt": "Create a learning roadmap for my career goals."},
    ]
    return jsonify({"success": True, "suggestions": items})


# ════════════════════════════════════════════════════════════════════
# Career intelligence tools
# ════════════════════════════════════════════════════════════════════

_TOOLS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "ats": lambda p: resume_service.compute_ats_score(p.get("resume_text", "")),
    "gap": lambda p: resume_service.skill_gap_analysis(p.get("resume_text", ""), (p.get("target_role") or "").strip()),
    "compare": lambda p: resume_service.compare_with_job_description(p.get("resume_text", ""), p.get("jd_text", "")),
    "interview": lambda p: resume_service.interview_questions(p.get("resume_text", "")),
    "cover-letter": lambda p: resume_service.cover_letter(
        p.get("resume_text", ""),
        job_title=p.get("job_title", ""),
        company=p.get("company", ""),
    ),
    "roadmap": lambda p: resume_service.learning_roadmap(p.get("resume_text", "")),
    "recommendations": lambda p: resume_service.career_recommendations(p.get("resume_text", "")),
    "rewrite": lambda p: resume_service.resume_rewrite_suggestions(p.get("resume_text", "")),
    "salary": lambda p: resume_service.salary_estimation(p.get("resume_text", "")),
    "analysis": lambda p: resume_service.analyze_resume_profile(
        p.get("resume_text", ""), mode=p.get("mode", "standard")
    ),
}

_REQUIRE_RESUME = {
    "ats",
    "gap",
    "compare",
    "interview",
    "cover-letter",
    "roadmap",
    "recommendations",
    "rewrite",
    "salary",
    "analysis",
}


@chat_bp.post("/api/chat/tools/<tool>")
@login_required
@rate_limit
def run_tool(tool: str):
    """Run a deterministic career-intelligence tool and return its result
    plus a markdown rendering ready to display in the chat."""
    handler = _TOOLS.get(tool)
    if handler is None:
        return jsonify({"success": False, "error": f"Unknown tool: {tool}"}), 404

    payload = _json_payload()
    if tool in _REQUIRE_RESUME and len((payload.get("resume_text") or "").strip()) < resume_service.RESUME_MIN_CHARS:
        return jsonify(
            {
                "success": False,
                "error": "Attach a resume (PDF/DOCX/TXT) first, then try this again — the tool needs your document content.",
            }
        ), 400

    try:
        result = handler(payload)
    except Exception as exc:
        log.exception("Career tool %s failed", tool)
        return jsonify({"success": False, "error": f"Could not run that tool: {exc}"}), 500

    return jsonify(
        {
            "success": True,
            "tool": tool,
            "data": result,
            "markdown": resume_service.format_tool_result(tool, result),
        }
    )


# ════════════════════════════════════════════════════════════════════
# File upload (context)
# ════════════════════════════════════════════════════════════════════


@chat_bp.post("/api/chat/context")
@login_required
@rate_limit
def upload_context():
    """Upload a file (PDF/DOCX/TXT/CSV/XLSX/image) to use as chat context.

    Persists an ``UploadedFile`` record owned by the current user (with the
    extracted text) so it can be attached to a conversation via ``file_ids``
    in a later message. Returns the record plus a short skills summary so
    the frontend can show what was loaded.

    Returns:
        200 JSON: {success, file, text, skills, skill_count}
        400: rejected upload (bad extension / size / MIME / unreadable)
    """
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "Please attach a file."}), 400

    record, error = upload_service.save_upload(current_user.id, uploaded_file)
    if record is None:
        return jsonify({"success": False, "error": error or "Could not read the file."}), 400

    text = (record.extracted_text or "").strip()
    skills: list[str] = []
    if not record.is_image:
        try:
            from resume_parser import extract_skills_from_text

            extracted = extract_skills_from_text(text)
            skills = (extracted.get("all_skills") or [])[:12]
        except Exception:
            skills = []

    return jsonify(
        {
            "success": True,
            "file": file_to_dict(record),
            "text": text,
            "char_count": len(text),
            "skills": skills,
            "skill_count": len(skills),
        }
    ), 200


# ════════════════════════════════════════════════════════════════════
# Export
# ════════════════════════════════════════════════════════════════════


def _build_export_content(conversation) -> str:
    """Render a conversation as plain text for export."""
    lines = [f"{conversation.title}", "=" * len(conversation.title), ""]
    for message in conversation.messages.order_by("created_at").all():
        role = "You" if message.role == "user" else "Prayash Assistant"
        lines.append(f"[{role}]")
        lines.append(message.content)
        lines.append("")
    return "\n".join(lines)


def _build_docx(conversation) -> bytes:
    """Build a .docx export using python-docx."""
    from docx import Document

    doc = Document()
    doc.add_heading(conversation.title, level=0)
    for message in conversation.messages.order_by("created_at").all():
        role = "You" if message.role == "user" else "Prayash Assistant"
        doc.add_heading(role, level=2)
        doc.add_paragraph(message.content)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _build_pdf(conversation) -> bytes:
    """Build a .pdf export using PyMuPDF (fitz) with automatic text wrap."""
    import fitz  # PyMuPDF

    text = _build_export_content(conversation)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    margin = 54
    width = 595 - 2 * margin
    rect = fitz.Rect(margin, margin, margin + width, 842 - margin)
    inserted = page.insert_textbox(rect, text, fontsize=10, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)
    while inserted < 0:
        page = doc.new_page(width=595, height=842)
        inserted = page.insert_textbox(
            fitz.Rect(margin, margin, margin + width, 842 - margin), text, fontsize=10, fontname="helv"
        )
    buffer = io.BytesIO()
    doc.save(buffer)
    doc.close()
    buffer.seek(0)
    return buffer.getvalue()


@chat_bp.get("/api/chat/conversations/<int:conversation_id>/export")
@login_required
def export_conversation(conversation_id: int):
    """Export a conversation as TXT, DOCX or PDF (?format=txt|docx|pdf)."""
    conversation = chat_service.get_conversation(current_user.id, conversation_id)
    if conversation is None:
        return jsonify({"success": False, "error": "Conversation not found."}), 404

    fmt = (request.args.get("format") or "txt").lower()
    safe_title = "".join(c for c in conversation.title if c.isalnum() or c in " -_")[:40].strip() or "chat"
    filename = f"{safe_title}.{fmt}"

    if fmt == "txt":
        content = _build_export_content(conversation)
        return Response(
            content,
            mimetype="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if fmt == "docx":
        data = _build_docx(conversation)
        return send_file(
            io.BytesIO(data),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename,
        )
    if fmt == "pdf":
        data = _build_pdf(conversation)
        return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True, download_name=filename)
    return jsonify({"success": False, "error": "Format must be txt, docx or pdf."}), 400
