"""Tests for POST /match_jobs and POST /predict_risk (granular pipeline APIs)."""

from __future__ import annotations

RESUME_TEXT = (
    "John Doe\njohn.doe@example.com\n+91 98765 43210\n\n"
    "Summary: Computer science graduate with experience in Python, SQL, "
    "and machine learning through projects and internships.\n\n"
    "Experience: Data Science Intern at Acme Corp. Built ETL pipelines "
    "reducing report time by 35%.\n\n"
    "Education: B.Tech in Computer Science, 2024.\n\n"
    "Skills: Python, SQL, Pandas, Machine Learning, Flask, Git\n\n"
    "Projects: Sentiment analysis dashboard; resume screening tool.\n"
)


# ── /match_jobs ────────────────────────────────────────────────────────


def test_match_jobs_with_skills(client) -> None:
    """A skill list returns ranked job cards in the frontend shape."""
    resp = client.post("/match_jobs", json={"skills": ["python", "sql", "data analysis"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    jobs = data["jobs"]
    assert isinstance(jobs, list) and jobs

    for job in jobs:
        for key in ("title", "score", "risk_level", "industry", "job_board_links"):
            assert key in job, f"missing key: {key}"
        assert 0 <= job["score"] <= 100
        assert job["risk_level"] in ("Low", "Moderate", "Elevated")
        labels = {l["label"] for l in job["job_board_links"]}
        assert {"Indeed", "LinkedIn", "Naukri"} <= labels

    # Ranked by descending match score
    scores = [j["score"] for j in jobs]
    assert scores == sorted(scores, reverse=True)


def test_match_jobs_with_resume_text(client) -> None:
    """Resume text uses the full ML similarity pipeline."""
    resp = client.post("/match_jobs", json={"resume_text": RESUME_TEXT})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["jobs"], "ML path should return matches for a real resume"
    top = data["jobs"][0]
    assert top["score"] > 0, "top ML match should have positive similarity"
    assert isinstance(top["skills"], list)


def test_match_jobs_requires_input(client) -> None:
    """Neither skills nor resume_text → 400."""
    resp = client.post("/match_jobs", json={})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_match_jobs_accepts_comma_separated_skills(client) -> None:
    """A single comma-separated skills string also works."""
    resp = client.post("/match_jobs", json={"skills": "python, sql, flask"})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


# ── /predict_risk ──────────────────────────────────────────────────────


def test_predict_risk_returns_band_and_explanation(client) -> None:
    """Resume text returns risk_level + explanation in the frontend shape."""
    resp = client.post("/predict_risk", json={"resume_text": RESUME_TEXT})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    for key in ("risk_level", "risk_score", "explanation"):
        assert key in data, f"missing key: {key}"
    assert data["risk_level"] in ("Low", "Moderate", "Elevated")
    assert 0.0 <= data["risk_score"] <= 1.0
    assert len(data["explanation"]) > 20
    # Frontend meter contract
    assert data["explanation"]  # displayRiskLevel reads data.explanation


def test_predict_risk_requires_text(client) -> None:
    """Empty body → 400."""
    resp = client.post("/predict_risk", json={})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_predict_risk_short_text_rejected(client) -> None:
    """Text under 20 chars → 400."""
    resp = client.post("/predict_risk", json={"resume_text": "too short"})
    assert resp.status_code == 400


def test_predict_risk_deterministic(client) -> None:
    """Same input → same risk score (deterministic local ML)."""
    r1 = client.post("/predict_risk", json={"resume_text": RESUME_TEXT}).get_json()
    r2 = client.post("/predict_risk", json={"resume_text": RESUME_TEXT}).get_json()
    assert r1["risk_score"] == r2["risk_score"]
    assert r1["risk_level"] == r2["risk_level"]
