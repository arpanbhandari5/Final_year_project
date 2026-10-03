"""
Prayash — AI Service
=====================
LLM orchestration for the career AI assistant.

Supports three tiers, in priority order:
    1. OpenAI-compatible API (OpenRouter / DeepSeek / OpenAI) with token
       streaming — configured via ``LLM_PROVIDER`` + the matching API key.
    2. Local Ollama (``OLLAMA_HOST``/``OLLAMA_MODEL``) with streaming.
    3. Deterministic rule-based fallback (``services.resume_service``) when
       neither LLM tier is reachable — the assistant always answers.

Cancellation is supported via an in-memory registry keyed by a token
(``user_id:conversation_id``) so the frontend can stop generation.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator

import requests

from llm_cooldown import is_ollama_on_cooldown, mark_ollama_unavailable
from services.resume_service import rule_based_career_answer

log = logging.getLogger("prayash.ai")

# Whether the `openai` SDK is installed (required for the API tier).
# Imported lazily — the SDK pulls ~1.9s of imports at startup, so defer
# until an LLM API call actually needs it.
_HAS_OPENAI: bool | None = None  # None = not yet checked


def _openai_available() -> bool:
    """True if the openai SDK is importable (checked once, lazily)."""
    global _HAS_OPENAI
    if _HAS_OPENAI is None:
        try:
            import openai  # noqa: F401

            _HAS_OPENAI = True
        except Exception:  # pragma: no cover - graceful degradation
            _HAS_OPENAI = False
    return _HAS_OPENAI


# ── Cancellation registry ─────────────────────────────────────────────

_CANCELLED: dict[str, bool] = {}


def request_cancel(token: str) -> None:
    """Ask the generator with *token* to stop as soon as possible."""
    _CANCELLED[token] = True


def is_cancelled(token: str) -> bool:
    """True when a stop request has been issued for *token*."""
    return _CANCELLED.get(token, False)


def clear_cancel(token: str) -> None:
    """Reset the cancel flag (called when a new generation starts)."""
    _CANCELLED.pop(token, None)


# ── Provider resolution ───────────────────────────────────────────────


def _env() -> dict[str, str]:
    """Read the LLM-related environment configuration."""

    def get(key: str) -> str:
        return (os.environ.get(key) or "").strip()

    return {
        "provider": get("LLM_PROVIDER").lower(),
        "model": get("LLM_MODEL"),
        "openrouter_key": get("OPENROUTER_API_KEY"),
        "deepseek_key": get("DEEPSEEK_API_KEY"),
        "openai_key": get("OPENAI_API_KEY"),
        "openrouter_site_url": get("OPENROUTER_SITE_URL"),
        "openrouter_site_name": get("OPENROUTER_SITE_NAME"),
        "ollama_host": get("OLLAMA_HOST") or "http://localhost:11434",
        "ollama_model": get("OLLAMA_MODEL") or "llama3",
    }


def resolve_provider() -> dict[str, str]:
    """Pick the best available LLM provider from the environment.

    Returns a dict with keys: provider, base_url, model, api_key.
    Falls back to ``ollama`` when no API key is configured.
    """
    cfg = _env()
    provider = cfg["provider"]
    api_key = None
    base_url = None
    model = cfg["model"]

    # Explicit provider selection (LLM_PROVIDER set)
    if provider == "openrouter" and cfg["openrouter_key"]:
        api_key, base_url = cfg["openrouter_key"], "https://openrouter.ai/api/v1"
        model = model or "openai/gpt-4o"
    elif provider == "deepseek" and cfg["deepseek_key"]:
        api_key, base_url = cfg["deepseek_key"], "https://api.deepseek.com/v1"
        model = model or "deepseek-chat"
    elif provider == "openai" and cfg["openai_key"]:
        api_key, base_url = cfg["openai_key"], "https://api.openai.com/v1"
        model = model or "gpt-4o-mini"

    # Auto-detection when no explicit provider is chosen
    if not api_key:
        if cfg["openrouter_key"]:
            api_key, base_url, provider = cfg["openrouter_key"], "https://openrouter.ai/api/v1", "openrouter"
            model = model or "openai/gpt-4o"
        elif cfg["deepseek_key"]:
            api_key, base_url, provider = cfg["deepseek_key"], "https://api.deepseek.com/v1", "deepseek"
            model = model or "deepseek-chat"
        elif cfg["openai_key"]:
            api_key, base_url, provider = cfg["openai_key"], "https://api.openai.com/v1", "openai"
            model = model or "gpt-4o-mini"
        else:
            provider = "ollama"

    return {
        "provider": provider,
        "api_key": api_key or "",
        "base_url": base_url or "",
        "model": model or "llama3",
        "site_url": cfg["openrouter_site_url"],
        "site_name": cfg["openrouter_site_name"],
        "ollama_host": cfg["ollama_host"],
        "ollama_model": cfg["ollama_model"],
    }


def build_system_prompt() -> str:
    """The system prompt that shapes the assistant's career-expert persona."""
    return (
        "You are Prayash, a professional, friendly AI career assistant. "
        "You help users with resume analysis, ATS optimisation, skill gaps, "
        "job matching, career recommendations, learning roadmaps, interview "
        "preparation, cover letters and salary guidance. "
        "Answer concisely and practically, using markdown for structure. "
        "When a resume or job description is included in the context, base "
        "your advice on its actual content first (skills, experience, "
        "education, projects) before giving general career advice. "
        "Never invent facts that are not in the provided context; if the "
        "document has no answer, say so and ask a clarifying question."
    )


def _build_openai_client(provider_cfg: dict[str, str]):
    """Create an OpenAI-compatible client, or None if unavailable."""
    if not _openai_available() or not provider_cfg.get("api_key"):
        return None
    import openai

    headers: dict[str, str] = {}
    if provider_cfg.get("site_url"):
        headers["HTTP-Referer"] = provider_cfg["site_url"]
    if provider_cfg.get("site_name"):
        headers["X-Title"] = provider_cfg["site_name"]
    return openai.OpenAI(
        api_key=provider_cfg["api_key"],
        base_url=provider_cfg["base_url"] or None,
        default_headers=headers or None,
    )


def _build_messages(
    system_prompt: str, history: list[dict[str, str]], question: str, context: str
) -> list[dict[str, str]]:
    """Assemble the OpenAI-style message list from history + context."""
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if context:
        messages.append(
            {
                "role": "system",
                "content": f"Context from attached documents:\n{context[:15000]}",
            }
        )
    for msg in history[-12:]:
        messages.append(
            {
                "role": msg.get("role") if msg.get("role") in ("user", "assistant") else "user",
                "content": (msg.get("content") or "")[:2000],
            }
        )
    messages.append({"role": "user", "content": question[:4000]})
    return messages


def _stream_openai(
    provider_cfg: dict[str, str], messages: list[dict[str, str]], cancel_token: str, max_tokens: int
) -> Iterator[str]:
    """Yield tokens from an OpenAI-compatible streaming completion."""
    client = _build_openai_client(provider_cfg)
    if client is None:
        raise RuntimeError("OpenAI client unavailable")

    stream = client.chat.completions.create(
        model=provider_cfg["model"],
        messages=messages,
        temperature=0.3,
        max_tokens=max_tokens,
        stream=True,
        timeout=15,
    )
    for chunk in stream:
        if cancel_token and is_cancelled(cancel_token):
            break
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def _stream_ollama(provider_cfg: dict[str, str], messages: list[dict[str, str]], cancel_token: str) -> Iterator[str]:
    """Yield tokens from a local Ollama generate call.

    The conversation history is flattened into a single prompt because
    Ollama's ``/api/generate`` is prompt-based (not chat-based)."""
    if is_ollama_on_cooldown():
        raise RuntimeError("Ollama skipped (recent failure)")

    system = messages[0]["content"] if messages and messages[0]["role"] == "system" else build_system_prompt()
    transcript = "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in messages[1:])
    prompt = f"{system}\n\n{transcript}\nAssistant:"

    resp = requests.post(
        f"{provider_cfg['ollama_host']}/api/generate",
        json={
            "model": provider_cfg["ollama_model"],
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.3, "num_predict": 400},
        },
        stream=True,
        timeout=(2, 15),
    )
    resp.raise_for_status()
    for line in resp.iter_lines(decode_unicode=True):
        if cancel_token and is_cancelled(cancel_token):
            break
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        token = payload.get("response", "")
        if token:
            yield token
        if payload.get("done"):
            break


# ── Public API ────────────────────────────────────────────────────────


def stream_reply(
    question: str,
    history: list[dict[str, str]] | None = None,
    context: str = "",
    cancel_token: str = "",
    max_tokens: int | None = None,
) -> Iterator[tuple[str, str]]:
    """Stream an assistant reply.

    Yields ``("meta" | "token" | "done" | "error", payload)`` tuples.
    ``done`` carries the full text; ``error`` carries the error message and
    ends the stream. The caller is responsible for persisting the reply.
    """
    history = history or []
    yield "meta", {"mode": resolve_provider()["provider"]}

    provider_cfg = resolve_provider()
    messages = _build_messages(build_system_prompt(), history, question, context)
    full = ""

    # Tier 1: OpenAI-compatible API
    if provider_cfg["provider"] != "ollama":
        try:
            if cancel_token:
                clear_cancel(cancel_token)
            for token in _stream_openai(provider_cfg, messages, cancel_token, max_tokens or 600):
                full += token
                yield "token", token
            if full.strip():
                yield "done", full
                return
        except Exception as exc:  # fall through to next tier
            log.warning("API LLM stream failed (%s): %s", provider_cfg["provider"], exc)
            full = ""

    # Tier 2: local Ollama
    if provider_cfg["provider"] == "ollama" or not full.strip():
        try:
            if provider_cfg["provider"] != "ollama":
                provider_cfg["provider"] = "ollama"
            for token in _stream_ollama(provider_cfg, messages, cancel_token):
                full += token
                yield "token", token
            if full.strip():
                yield "done", full
                return
        except Exception as exc:
            mark_ollama_unavailable()
            log.warning("Ollama stream failed: %s", exc)
            full = ""

    # Tier 3: deterministic rule-based fallback
    if not full.strip():
        try:
            resume_text = context
            answer = rule_based_career_answer(question, resume_text=resume_text, history=history)
        except Exception as exc:  # pragma: no cover - last-resort guard
            log.error("Rule-based fallback failed: %s", exc)
            answer = (
                "I hit a snag while thinking. Please try again in a moment — "
                "and consider attaching your resume so I can give personalised advice."
            )
        yield "token", answer
        yield "done", answer


def generate_reply(
    question: str,
    history: list[dict[str, str]] | None = None,
    context: str = "",
) -> tuple[str, str]:
    """Non-streaming variant of ``stream_reply``. Returns ``(reply, mode)``."""
    full = ""
    mode = "rule-based"
    for kind, payload in stream_reply(question, history=history, context=context):
        if kind == "token":
            full += payload
        elif kind == "meta":
            mode = payload.get("mode", mode)
        elif kind == "error":
            full = full or payload
    return full, mode
