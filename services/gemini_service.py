"""Gemini (Google AI) explanation layer.

Deterministic results must always come first; this service only explains
them. If the key is missing, the API is down, or the response is invalid,
``None`` is returned and the caller falls back to deterministic output.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("prayash.gemini")

try:
    from google import genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None


class GeminiService:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY") or ""
        self.model = os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
        self.client = None
        if self.api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                log.warning("Gemini client init failed", exc_info=True)
                self.client = None

    def available(self) -> bool:
        return self.client is not None

    def _generate(self, prompt: str) -> str | None:
        if not self.available():
            return None
        try:
            resp = self.client.models.generate_content(model=self.model, contents=prompt)
            text = getattr(resp, "text", None)
            return text.strip() if text else None
        except Exception:
            log.warning("Gemini request failed", exc_info=True)
            return None

    def analyze_resume(self, resume_text: str, skills: list[str], ats_score: int | None = None) -> dict[str, Any] | None:
        prompt = (
            "You are a resume coach. Based ONLY on the data below, respond with JSON:\n"
            '{"strengths":[],"weaknesses":[],"improvements":[],"suggested_careers":[],"recommended_skills":[]}\n\n'
            f"Skills: {skills}\nATS score: {ats_score}\nResume text:\n{resume_text[:4000]}"
        )
        import json
        raw = self._generate(prompt)
        if not raw:
            return None
        try:
            # tolerate markdown fences
            cleaned = raw.strip().strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            data = json.loads(cleaned)
            return data if isinstance(data, dict) else None
        except Exception:
            return {"explanation": raw}

    def personalize_roadmap(self, roadmap: dict[str, Any], user_profile: str = "") -> str | None:
        prompt = (
            "You are a career reskilling advisor. Do NOT change the calculated skill order.\n"
            f"User profile: {user_profile}\n"
            f"Roadmap: {roadmap}\n\n"
            "For each step provide: why it matters, learning objectives, one beginner project, one intermediate project, practical advice."
        )
        return self._generate(prompt)
