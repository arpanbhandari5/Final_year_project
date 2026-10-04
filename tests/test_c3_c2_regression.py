"""C.3 re-audit of C.2 Target Job Match contracts. Does not change matching semantics."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from pathlib import Path

from app import app
from storage import (
    AnalysisSnapshot,
    JobPosting,
    ResumeVersion,
    TargetJobMatch,
    db,
    get_resume_profile,
)
from tests.test_target_job_match import POSTGRES_JD, login_csrf

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "C3_RAW_JOB_SENTINEL_9f42a7b1"
FREEZE = {
    "data/automation_risk.csv": "d28ca4cbc2ca746c9a033d1953d49d565c3e64a2d8ae54b6ce52bed1826a18f1",
    "ml_models/model.pkl": "cca7933cc2fca7b37d405c5d5d0f111a88ec071a69cea536315064d60944398c",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _csrf(client):
    return client.get("/api/csrf-token").get_json()["csrf_token"]


def _headers(client):
    return {"X-CSRFToken": _csrf(client)}


def test_deleted_resume_version_cannot_be_used_for_new_match():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    created = client.post(
        "/api/resume-versions",
        json={"name": "C3 delete-me", "content_text": "Python warehouse reporting with measurable outcomes."},
        headers=_headers(client),
    )
    assert created.status_code == 201
    version_id = created.get_json()["resume_version"]["id"]
    listed = client.get("/api/resume-versions")
    assert listed.status_code == 200
    assert any(item["id"] == version_id for item in listed.get_json()["resume_versions"])
    with app.app_context():
        row = db.session.get(ResumeVersion, version_id)
        db.session.delete(row)
        db.session.commit()
    listed_after = client.get("/api/resume-versions")
    assert all(item["id"] != version_id for item in listed_after.get_json()["resume_versions"])
    attempt = client.post(
        "/api/target-job-match",
        json={
            "description": POSTGRES_JD,
            "evidence_source": "resume_version",
            "resume_version_id": version_id,
        },
        headers=_headers(client),
    )
    assert attempt.status_code == 404
    body = attempt.get_json()
    assert body.get("success") is False
    app.config["WTF_CSRF_ENABLED"] = previous


def test_deleted_match_raw_job_text_is_not_application_accessible():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    description = (
        "Required: Python for internal tools. "
        f"{SENTINEL} "
        "Documented stakeholder reporting and delivery work on this team."
    )
    created = client.post(
        "/api/target-job-match",
        json={"description": description, "evidence_source": "profile", "title": "C3 sentinel job"},
        headers=_headers(client),
    )
    assert created.status_code in {200, 201}
    match_id = created.get_json()["id"]
    assert SENTINEL in created.get_json()["description_raw"]
    listed = client.get("/api/target-job-match")
    assert listed.status_code == 200
    for item in listed.get_json()["matches"]:
        assert "description_raw" not in item
        blob = json.dumps(item)
        assert SENTINEL not in blob
    deleted = client.delete(f"/api/target-job-match/{match_id}", headers=_headers(client))
    assert deleted.status_code == 200
    assert client.get(f"/api/target-job-match/{match_id}").status_code == 404
    listed_after = client.get("/api/target-job-match")
    ids = [item["id"] for item in listed_after.get_json()["matches"]]
    assert match_id not in ids
    with app.app_context():
        assert db.session.get(TargetJobMatch, match_id) is None
        leftover_matches = TargetJobMatch.query.filter(TargetJobMatch.description_raw.contains(SENTINEL)).all()
        assert leftover_matches == []
        leftover_jobs = JobPosting.query.filter(JobPosting.description_raw.contains(SENTINEL)).all()
        assert leftover_jobs == []
        for snap in AnalysisSnapshot.query.all():
            assert SENTINEL not in (snap.result_json or "")
    app.config["WTF_CSRF_ENABLED"] = previous


def test_c3_sentinel_absent_from_application_logs(caplog):
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    description = (
        "Required: Python for internal tools. "
        f"{SENTINEL} "
        "Documented stakeholder reporting and delivery work on this team."
    )
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="prayash")
    response = client.post(
        "/api/target-job-match",
        json={"description": description, "evidence_source": "profile"},
        headers=_headers(client),
    )
    assert response.status_code in {200, 201}
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert SENTINEL not in messages
    match_id = response.get_json()["id"]
    client.delete(f"/api/target-job-match/{match_id}", headers=_headers(client))
    app.config["WTF_CSRF_ENABLED"] = previous


def test_identical_submissions_reuse_owned_row():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    payload = {
        "description": POSTGRES_JD,
        "evidence_source": "profile",
        "title": "Reuse check",
        "company": "Example",
    }
    first = client.post("/api/target-job-match", json=payload, headers=_headers(client))
    second = client.post("/api/target-job-match", json=payload, headers=_headers(client))
    assert first.status_code in {200, 201}
    assert second.status_code == 200
    assert first.get_json()["id"] == second.get_json()["id"]
    assert second.get_json()["created"] is False
    match_id = first.get_json()["id"]
    with app.app_context():
        from storage import User

        admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
        rows = TargetJobMatch.query.filter_by(
            user_id=admin.id,
            content_hash=first.get_json()["content_hash"],
            evidence_source_key="profile",
        ).all()
        assert len(rows) == 1
        assert rows[0].id == match_id
    app.config["WTF_CSRF_ENABLED"] = previous


def test_target_job_match_get_routes_are_read_only():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    created = client.post(
        "/api/target-job-match",
        json={"description": POSTGRES_JD, "evidence_source": "profile", "title": "GET check"},
        headers=_headers(client),
    )
    assert created.status_code in {200, 201}
    match_id = created.get_json()["id"]
    updated_before = created.get_json()["updated_at"]
    with app.app_context():
        from storage import User

        admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
        count_before = TargetJobMatch.query.filter_by(user_id=admin.id).count()
        profile_before = get_resume_profile(admin.id)
        skills_before = profile_before.extracted_skills_json if profile_before else None
    listed = client.get("/api/target-job-match")
    detail = client.get(f"/api/target-job-match/{match_id}")
    page = client.get("/workspace/job-match")
    versions = client.get("/api/resume-versions")
    assert listed.status_code == 200
    assert detail.status_code == 200
    assert page.status_code == 200
    assert versions.status_code == 200
    assert detail.get_json()["updated_at"] == updated_before
    with app.app_context():
        from storage import User

        admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
        assert TargetJobMatch.query.filter_by(user_id=admin.id).count() == count_before
        row = db.session.get(TargetJobMatch, match_id)
        assert row.updated_at.isoformat() == updated_before
        profile_after = get_resume_profile(admin.id)
        skills_after = profile_after.extracted_skills_json if profile_after else None
        assert skills_after == skills_before
    app.config["WTF_CSRF_ENABLED"] = previous


def test_match_ownership_is_session_user_not_client_fields():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    owner = app.test_client()
    other = app.test_client()
    login_csrf(owner, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    login_csrf(other, "student", "Student@123")
    created = owner.post(
        "/api/target-job-match",
        json={
            "description": POSTGRES_JD,
            "evidence_source": "profile",
            "user_id": 0,
            "owner_id": 0,
            "account_id": 0,
        },
        headers=_headers(owner),
    )
    assert created.status_code in {200, 201}
    match_id = created.get_json()["id"]
    with app.app_context():
        from storage import User

        admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
        row = db.session.get(TargetJobMatch, match_id)
        assert row.user_id == admin.id
    assert other.get(f"/api/target-job-match/{match_id}").status_code == 404
    assert other.patch(
        f"/api/target-job-match/{match_id}",
        json={"title": "nope"},
        headers=_headers(other),
    ).status_code == 404
    assert other.delete(f"/api/target-job-match/{match_id}", headers=_headers(other)).status_code == 404
    listed = other.get("/api/target-job-match")
    assert all(item["id"] != match_id for item in listed.get_json()["matches"])
    app.config["WTF_CSRF_ENABLED"] = previous


def test_protected_benchmark_and_model_hashes_match_freeze():
    for relative, expected in FREEZE.items():
        path = ROOT / relative
        assert path.is_file()
        assert _sha256(path) == expected
    train = ROOT / "train_model.py"
    pickle = ROOT / "ml_models" / "model.pkl"
    status = subprocess.check_output(
        ["git", "status", "--short", "--", str(train), str(pickle)],
        cwd=ROOT,
        text=True,
    ).strip()
    assert status == ""
    diff = subprocess.check_output(
        ["git", "diff", "--", "train_model.py", "ml_models/model.pkl"],
        cwd=ROOT,
        text=True,
    )
    assert diff == ""
