"""Tests for the POST /score_resume endpoint (Resume Strength Score API)."""

from __future__ import annotations

from io import BytesIO

RESUME_TEXT = (
    "John Doe\njohn.doe@example.com\n+91 98765 43210\n\n"
    "Summary: Computer science graduate with hands-on experience in Python, "
    "SQL, and machine learning through academic projects and internships.\n\n"
    "Experience: Data Science Intern at Acme Corp (6 months). Built ETL "
    "pipelines that reduced report generation time by 35% and improved "
    "forecast accuracy by 12%.\n\n"
    "Education: B.Tech in Computer Science, 2024.\n\n"
    "Skills: Python, SQL, Pandas, Machine Learning, Flask, Git\n\n"
    "Projects: Built a sentiment analysis dashboard and a resume screening "
    "tool. Led a 4-member team; automated data collection, saving 10 hours "
    "per week.\n\n"
    "Certifications: Google Data Analytics Certificate."
)


def test_score_resume_with_text(client) -> None:
    """JSON resume_text returns the full score payload."""
    resp = client.post("/score_resume", json={"resume_text": RESUME_TEXT})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

    result = data["result"]
    for key in ("final_score", "skill_score", "experience_score", "quality_score", "feedback"):
        assert key in result, f"missing key: {key}"
        assert result[key] is not None

    for key in ("final_score", "skill_score", "experience_score", "quality_score"):
        assert isinstance(result[key], int)
        assert 0 <= result[key] <= 100, f"{key} out of range: {result[key]}"

    assert isinstance(result["feedback"], str) and len(result["feedback"]) > 10
    assert isinstance(result.get("skills"), list)


def test_score_resume_final_is_weighted_average(client) -> None:
    """final_score matches the documented 40/30/30 weighting."""
    resp = client.post("/score_resume", json={"resume_text": RESUME_TEXT})
    result = resp.get_json()["result"]
    expected = round(
        result["skill_score"] * 0.4
        + result["experience_score"] * 0.3
        + result["quality_score"] * 0.3
    )
    assert result["final_score"] == expected


def test_score_resume_with_file(client) -> None:
    """Multipart upload with a TXT file (field name "resume") works."""
    resp = client.post(
        "/score_resume",
        data={"resume": (BytesIO(RESUME_TEXT.encode("utf-8")), "resume.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["result"]["final_score"] >= 0
    assert "final_score" in data["result"]


def test_score_resume_accepts_resume_file_field(client) -> None:
    """The 'resume_file' field name (used by the main analyzer) also works."""
    resp = client.post(
        "/score_resume",
        data={"resume_file": (BytesIO(RESUME_TEXT.encode("utf-8")), "resume.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_score_resume_rejects_empty(client) -> None:
    """No file and no text → 400."""
    resp = client.post("/score_resume", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "error" in data


def test_score_resume_rejects_short_text(client) -> None:
    """Text under 20 chars → 400."""
    resp = client.post("/score_resume", json={"resume_text": "too short"})
    assert resp.status_code == 400


def test_score_resume_weak_resume_scores_low(client) -> None:
    """A sparse resume should not score in the top band."""
    weak = (
        "Somebody\nsomebody@example.com\nI know computers and did some "
        "stuff at a company once for a while."
    )
    resp = client.post("/score_resume", json={"resume_text": weak})
    assert resp.status_code == 200
    result = resp.get_json()["result"]
    assert result["final_score"] < 80


def test_score_resume_shape_matches_frontend_contract(client) -> None:
    """The frontend meter reads data.result.{final_score,...} — verify shape."""
    resp = client.post("/score_resume", json={"resume_text": RESUME_TEXT})
    data = resp.get_json()
    assert "result" in data, "frontend expects scores nested under 'result'"
    assert isinstance(data["result"]["feedback"], str)
