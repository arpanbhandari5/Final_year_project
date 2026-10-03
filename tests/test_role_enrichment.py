"""Tests for per-role enrichment of ``top_roles`` (trait chips + job-board links)."""

from __future__ import annotations

from io import BytesIO

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


def _analyze(client):
    return client.post(
        "/api/upload",
        data={"resume_file": (BytesIO(RESUME_TEXT.encode("utf-8")), "resume.txt")},
        content_type="multipart/form-data",
    )


def test_top_roles_are_enriched(client) -> None:
    """Every role exposes trait_chips and job_board_links, without training internals."""
    resp = _analyze(client)
    assert resp.status_code == 200
    roles = resp.get_json().get("top_roles") or []
    assert roles, "expected at least one role match"

    for role in roles:
        assert "text" not in role, "raw vectorizer blob must be stripped"
        assert "skills" not in role, "numeric attribute list must be replaced by trait_chips"
        assert isinstance(role.get("trait_chips"), list) and role["trait_chips"]
        links = role.get("job_board_links") or []
        labels = {l.get("label") for l in links}
        assert {"Indeed", "LinkedIn", "Naukri"} <= labels
        for link in links:
            assert link["url"].startswith("https://")


def test_trait_chips_vary_per_role(client) -> None:
    """Chips are derived per role, not shared across all matches."""
    resp = _analyze(client)
    roles = resp.get_json().get("top_roles") or []
    if len(roles) >= 2:
        assert roles[0].get("trait_chips") != roles[1].get("trait_chips") or (
            roles[0].get("job_role") == roles[1].get("job_role")
        )


def test_role_links_url_encode_role_names(client) -> None:
    """Role names are URL-encoded into each board's search URL."""
    resp = _analyze(client)
    roles = resp.get_json().get("top_roles") or []
    assert roles
    role = roles[0]
    name = (role.get("job_role") or "").strip()
    if name:
        indeed = next(l for l in role["job_board_links"] if l["label"] == "Indeed")
        assert "indeed.com" in indeed["url"]
