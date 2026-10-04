"""Optional narrative services must fail closed without calling a live model."""

from __future__ import annotations

from unittest.mock import patch

import requests

from app import app
from risk_assessor import _ollama_narrative

_ANALYSIS = {"risk_score": 0.2, "top_roles": [], "riasec": {}, "roadmap": []}


def test_narrative_timeout_returns_none() -> None:
    with patch("risk_assessor.requests.post", side_effect=requests.Timeout("slow")):
        assert _ollama_narrative("Python analyst", _ANALYSIS) is None


def test_narrative_connection_error_returns_none() -> None:
    with patch("risk_assessor.requests.post", side_effect=requests.ConnectionError("offline")):
        assert _ollama_narrative("Python analyst", _ANALYSIS) is None


def test_narrative_http_error_returns_none() -> None:
    response = requests.Response()
    response.status_code = 503
    with patch("risk_assessor.requests.post", return_value=response):
        assert _ollama_narrative("Python analyst", _ANALYSIS) is None


def test_narrative_invalid_payload_returns_none() -> None:
    class FakeResponse:
        ok = True
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return ["not", "an", "object"]

    with patch("risk_assessor.requests.post", return_value=FakeResponse()):
        assert _ollama_narrative("Python analyst", _ANALYSIS) is None


def test_narrative_success_uses_a_timeout() -> None:
    class FakeResponse:
        ok = True
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"response": "A concise narrative."}

    with patch("risk_assessor.requests.post", return_value=FakeResponse()) as posted:
        assert _ollama_narrative("Python analyst", _ANALYSIS) == "A concise narrative."
    assert posted.call_args.kwargs["timeout"] == 45


def test_career_chat_works_when_optional_ai_is_unavailable() -> None:
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()
    with patch("app.requests.post", side_effect=requests.ConnectionError("offline")):
        response = client.post("/api/career-chat", json={"message": "How should I prepare for an interview?"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["llm_powered"] is False
    assert "interview" in payload["answer"].lower()
    assert "api_key" not in response.get_data(as_text=True).lower()
