"""Phase D: save Target Job Match as an application action. Not ATS scoring."""

from __future__ import annotations

import json
import logging

import pytest

from app import app
from storage import Application, JobPosting, TargetJobMatch, db
from tests.test_target_job_match import POSTGRES_JD, login_csrf, _seed_python_profile


def _headers(client):
    return {"X-CSRFToken": client.get("/api/csrf-token").get_json()["csrf_token"]}


def test_save_from_match_csrf_ownership_reuse_and_deleted_match(caplog):
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    _seed_python_profile(app.config["ADMIN_EMAIL"])
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    created = client.post(
        "/api/target-job-match",
        json={"description": POSTGRES_JD, "title": "Analyst", "company": "Example Co", "evidence_source": "profile"},
        headers=_headers(client),
    )
    assert created.status_code in {200, 201}
    match_id = created.get_json()["id"]
    missing_csrf = client.post(f"/api/target-job-match/{match_id}/save-application", json={})
    assert missing_csrf.status_code == 400
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="prayash")
    saved = client.post(
        f"/api/target-job-match/{match_id}/save-application",
        json={"description": "client dump must be ignored " + ("x" * 40), "user_id": 0, "owner_id": 0},
        headers=_headers(client),
    )
    assert saved.status_code == 201
    body = saved.get_json()
    assert body["created"] is True
    assert body["status"] == "Bookmarked"
    assert body["target_job_match_id"] == match_id
    assert body["comparison_available"] is True
    assert body["export_supported"] is False
    assert "description_raw" not in body
    assert "description_raw" not in (body.get("job") or {})
    application_id = body["id"]
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert POSTGRES_JD.strip() not in messages
    reused = client.post(
        f"/api/target-job-match/{match_id}/save-application",
        json={},
        headers=_headers(client),
    )
    assert reused.status_code == 200
    assert reused.get_json()["id"] == application_id
    assert reused.get_json()["created"] is False

    listed = client.get("/api/applications")
    assert listed.status_code == 200
    blob = json.dumps(listed.get_json())
    assert "description_raw" not in blob
    assert "Required: PostgreSQL" not in blob
    count = len(listed.get_json()["applications"])
    listed_again = client.get("/api/applications")
    assert len(listed_again.get_json()["applications"]) == count

    other = app.test_client()
    login_csrf(other, "student", "Student@123")
    assert other.post(
        f"/api/target-job-match/{match_id}/save-application",
        json={},
        headers=_headers(other),
    ).status_code == 404
    assert other.patch(
        f"/api/applications/{application_id}",
        json={"status": "Applied"},
        headers=_headers(other),
    ).status_code == 404
    assert all(item["id"] != application_id for item in other.get("/api/applications").get_json()["applications"])

    patched = client.patch(
        f"/api/applications/{application_id}",
        json={"status": "Applied", "notes": "Followed up by email.", "follow_up_date": "2026-10-20"},
        headers=_headers(client),
    )
    assert patched.status_code == 200
    assert patched.get_json()["application"]["status"] == "Applied"
    assert patched.get_json()["application"]["follow_up_date"] == "2026-10-20"

    foreign_resume = other.post(
        "/api/resume-versions",
        json={"name": "Other resume", "content_text": "Python reporting work with measurable outcomes."},
        headers=_headers(other),
    )
    assert foreign_resume.status_code == 201
    stolen_version = foreign_resume.get_json()["resume_version"]["id"]
    assert client.patch(
        f"/api/applications/{application_id}",
        json={"resume_version_id": stolen_version},
        headers=_headers(client),
    ).status_code == 404

    client.delete(f"/api/target-job-match/{match_id}", headers=_headers(client))
    after_delete = client.get("/api/applications").get_json()["applications"]
    row = next(item for item in after_delete if item["id"] == application_id)
    assert row["comparison_available"] is False
    assert row["target_job_match_id"] is None
    with app.app_context():
        stored = db.session.get(Application, application_id)
        assert stored is not None
        assert stored.target_job_match_id is None
        assert db.session.get(TargetJobMatch, match_id) is None
    assert client.post(
        f"/api/target-job-match/{match_id}/save-application",
        json={},
        headers=_headers(client),
    ).status_code == 404
    app.config["WTF_CSRF_ENABLED"] = previous


def test_applications_get_is_read_only_and_page_requires_login():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    anon = app.test_client()
    assert anon.get("/api/applications").status_code == 401
    page = anon.get("/workspace/applications")
    assert page.status_code in {302, 401}
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    with app.app_context():
        from storage import User

        admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
        count = Application.query.filter_by(user_id=admin.id).count()
        jobs = JobPosting.query.filter_by(user_id=admin.id).count()
    listed = client.get("/api/applications")
    html = client.get("/workspace/applications")
    assert listed.status_code == 200
    assert html.status_code == 200
    assert b"not an ATS score or a prediction that you will be hired" in html.data
    with app.app_context():
        from storage import User

        admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
        assert Application.query.filter_by(user_id=admin.id).count() == count
        assert JobPosting.query.filter_by(user_id=admin.id).count() == jobs
    app.config["WTF_CSRF_ENABLED"] = previous


def test_applications_schema_has_target_job_match_id():
    with app.app_context():
        from sqlalchemy import text

        columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(applications)"))}
        assert "target_job_match_id" in columns
        names = {row[1] for row in db.session.execute(text("PRAGMA index_list(applications)"))}
        assert "uq_applications_user_job" in names
        job_indexes = {row[1] for row in db.session.execute(text("PRAGMA index_list(job_postings)"))}
        assert "uq_job_postings_user_hash" in job_indexes


def test_database_rejects_duplicate_active_applications():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    _seed_python_profile(app.config["ADMIN_EMAIL"])
    client = app.test_client()
    login_csrf(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    created = client.post(
        "/api/target-job-match",
        json={"description": POSTGRES_JD, "title": "Analyst", "company": "Example Co", "evidence_source": "profile"},
        headers=_headers(client),
    )
    match_id = created.get_json()["id"]
    first = client.post(f"/api/target-job-match/{match_id}/save-application", json={}, headers=_headers(client))
    second = client.post(f"/api/target-job-match/{match_id}/save-application", json={}, headers=_headers(client))
    assert first.status_code in {200, 201}
    assert second.status_code == 200
    assert first.get_json()["id"] == second.get_json()["id"]
    application_id = first.get_json()["id"]
    with app.app_context():
        from sqlalchemy.exc import IntegrityError

        from storage import User

        admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
        row = db.session.get(Application, application_id)
        duplicate = Application(
            user_id=admin.id,
            job_posting_id=row.job_posting_id,
            status="Applying",
        )
        db.session.add(duplicate)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert Application.query.filter_by(user_id=admin.id, job_posting_id=row.job_posting_id).count() == 1
        job = db.session.get(JobPosting, row.job_posting_id)
        twin = JobPosting(
            user_id=admin.id,
            title="Clone",
            company="Clone Co",
            description_raw="unused because hash is forced",
            content_hash=job.content_hash,
        )
        db.session.add(twin)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
    app.config["WTF_CSRF_ENABLED"] = previous


def test_application_ownership_csrf_and_edge_inputs():
    previous = app.config.get("WTF_CSRF_ENABLED")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    _seed_python_profile(app.config["ADMIN_EMAIL"])
    owner = app.test_client()
    other = app.test_client()
    login_csrf(owner, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    login_csrf(other, "student", "Student@123")
    created = owner.post(
        "/api/target-job-match",
        json={"description": POSTGRES_JD + " extra uniqueness salt.", "title": "Analyst", "company": "Example Co"},
        headers=_headers(owner),
    )
    match_id = created.get_json()["id"]
    saved = owner.post(f"/api/target-job-match/{match_id}/save-application", json={}, headers=_headers(owner))
    application_id = saved.get_json()["id"]

    assert owner.get(f"/api/applications/{application_id}").status_code == 200
    assert "description_raw" not in json.dumps(owner.get(f"/api/applications/{application_id}").get_json())
    assert other.get(f"/api/applications/{application_id}").status_code == 404
    assert other.delete(f"/api/applications/{application_id}", headers=_headers(other)).status_code == 404
    assert other.patch(
        f"/api/applications/{application_id}",
        json={"status": "Applied"},
        headers=_headers(other),
    ).status_code == 404

    own_match = other.post(
        "/api/target-job-match",
        json={"description": POSTGRES_JD + " student-owned comparison text for isolation."},
        headers=_headers(other),
    )
    assert own_match.status_code in {200, 201}
    other_match_id = own_match.get_json()["id"]
    assert owner.post(
        f"/api/target-job-match/{other_match_id}/save-application",
        json={},
        headers=_headers(owner),
    ).status_code == 404
    before = owner.get(f"/api/applications/{application_id}").get_json()["target_job_match_id"]
    ignored = owner.patch(
        f"/api/applications/{application_id}",
        json={"target_job_match_id": other_match_id, "user_id": 0, "owner_id": 0, "status": "Applying"},
        headers=_headers(owner),
    )
    assert ignored.status_code == 200
    assert ignored.get_json()["application"]["target_job_match_id"] == before
    assert ignored.get_json()["application"]["status"] == "Applying"

    assert owner.patch(
        f"/api/applications/{application_id}",
        json={"status": "NotARealStatus"},
        headers=_headers(owner),
    ).status_code == 400
    assert owner.patch(
        f"/api/applications/{application_id}",
        json={"notes": "n" * 4001},
        headers=_headers(owner),
    ).status_code == 400
    past = owner.patch(
        f"/api/applications/{application_id}",
        json={"follow_up_date": "2020-01-02"},
        headers=_headers(owner),
    )
    assert past.status_code == 200
    assert past.get_json()["application"]["follow_up_date"] == "2020-01-02"

    version = owner.post(
        "/api/resume-versions",
        json={"name": "Owned", "content_text": "Python warehouse reporting with measurable outcomes."},
        headers=_headers(owner),
    )
    version_id = version.get_json()["resume_version"]["id"]
    attached = owner.patch(
        f"/api/applications/{application_id}",
        json={"resume_version_id": version_id},
        headers=_headers(owner),
    )
    assert attached.status_code == 200
    with app.app_context():
        from storage import ResumeVersion as VersionModel

        row = db.session.get(VersionModel, version_id)
        db.session.delete(row)
        db.session.commit()
    missing = owner.patch(
        f"/api/applications/{application_id}",
        json={"resume_version_id": version_id},
        headers=_headers(owner),
    )
    assert missing.status_code == 404

    bad_csrf = owner.patch(
        f"/api/applications/{application_id}",
        json={"status": "Applied"},
        headers={"X-CSRFToken": "not-a-token"},
    )
    assert bad_csrf.status_code == 400
    assert owner.patch(f"/api/applications/{application_id}", json={"status": "Applied"}).status_code == 400

    guest = app.test_client()
    assert guest.get(f"/api/applications/{application_id}").status_code == 401
    assert guest.post(f"/api/target-job-match/{match_id}/save-application", json={}).status_code == 401
    assert guest.patch(f"/api/applications/{application_id}", json={"status": "Applied"}).status_code == 401
    assert guest.delete(f"/api/applications/{application_id}").status_code == 401
    app.config["WTF_CSRF_ENABLED"] = previous


def test_existing_sqlite_receives_unique_indexes_after_dedupe():
    from sqlalchemy import create_engine, text

    from storage import _dedupe_and_index_sqlite_applications

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE job_postings (id INTEGER PRIMARY KEY, user_id INTEGER, content_hash TEXT)"))
        conn.execute(text("CREATE TABLE applications (id INTEGER PRIMARY KEY, user_id INTEGER, job_posting_id INTEGER, target_job_match_id INTEGER)"))
        conn.execute(text("INSERT INTO job_postings (id, user_id, content_hash) VALUES (1, 9, 'same'), (2, 9, 'same')"))
        conn.execute(text("INSERT INTO applications (id, user_id, job_posting_id) VALUES (1, 9, 1), (2, 9, 2)"))
        _dedupe_and_index_sqlite_applications(conn)
        job_ids = [row[0] for row in conn.execute(text("SELECT id FROM job_postings ORDER BY id"))]
        app_rows = list(conn.execute(text("SELECT id, job_posting_id FROM applications")))
        assert job_ids == [1]
        assert len(app_rows) == 1
        assert app_rows[0][1] == 1
        names = {row[1] for row in conn.execute(text("PRAGMA index_list(applications)"))}
        assert "uq_applications_user_job" in names
        job_names = {row[1] for row in conn.execute(text("PRAGMA index_list(job_postings)"))}
        assert "uq_job_postings_user_hash" in job_names
        _dedupe_and_index_sqlite_applications(conn)
        assert {row[1] for row in conn.execute(text("PRAGMA index_list(applications)"))} & {"uq_applications_user_job"}

