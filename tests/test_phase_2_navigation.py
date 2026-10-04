"""Phase 2: start intents and primary navigation. No API or matcher changes."""

from __future__ import annotations

from app import app
from tests.test_target_job_match import login_csrf


def _primary_nav(html: bytes) -> bytes:
    marker = b'aria-label="Primary"'
    start = html.find(marker)
    assert start != -1
    end = html.find(b"</nav>", start)
    assert end != -1
    return html[start:end]


def test_guest_start_intents_and_primary_nav():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    home = client.get("/")
    assert home.status_code == 200
    assert b'id="analysis"' in home.data
    assert b"I know my target role" in home.data
    assert b"I have a job description" in home.data
    assert b"I want to explore careers" in home.data
    assert b"I want to understand my resume" in home.data
    assert b"I'm a student" in home.data
    nav = _primary_nav(home.data)
    assert b">Home<" in nav
    assert b"Start Here" in nav
    assert b">Privacy<" in nav
    assert b">Login<" in nav
    assert b"Methodology" not in nav
    assert b"Insights" not in nav
    assert b"Partnerships" not in nav
    assert b"Resources" not in nav
    assert b"ATS score" in home.data
    assert b"hiring probability" not in home.data.lower()
    assert b"job-loss probability" not in home.data.lower()

    job_match = client.get("/workspace/job-match", follow_redirects=False)
    assert job_match.status_code in {302, 303}
    location = job_match.headers.get("Location", "")
    assert "/login" in location
    assert "next=" in location
    assert "/workspace/job-match" in location

    applications = client.get("/workspace/applications", follow_redirects=False)
    assert applications.status_code in {302, 303}
    apps_location = applications.headers.get("Location", "")
    assert "/login" in apps_location
    assert "/workspace/applications" in apps_location

    insights = client.get("/insights")
    assert insights.status_code == 200
    app.config["WTF_CSRF_ENABLED"] = previous


def test_authenticated_start_intents_and_workspace_hashes():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    login_csrf(client, "student", "Student@123")
    home = client.get("/")
    assert home.status_code == 200
    assert b'href="/workspace#career-goal"' in home.data or b"workspace#career-goal" in home.data
    assert b"/workspace/job-match" in home.data
    assert b"/workspace/skills-gap" in home.data
    nav = _primary_nav(home.data)
    assert b"Workspace" in nav
    assert b"Career goal" in nav
    assert b"Resume &amp; evidence" in nav or b"Resume & evidence" in nav
    assert b"Target jobs" in nav
    assert b"Learning &amp; actions" in nav or b"Learning & actions" in nav
    assert b">Applications<" in nav
    assert b"Methodology" not in nav
    assert b"Saved jobs" not in nav

    workspace = client.get("/workspace")
    assert workspace.status_code == 200
    assert b'id="career-goal"' in workspace.data
    assert b'id="resume-evidence"' in workspace.data
    assert b'id="learning-actions"' in workspace.data

    job_match = client.get("/workspace/job-match")
    assert job_match.status_code == 200
    applications = client.get("/workspace/applications")
    assert applications.status_code == 200
    assert b"Saved jobs and applications" in applications.data
    assert b"Track jobs you saved, applied to, and followed up on." in applications.data
    app.config["WTF_CSRF_ENABLED"] = previous
