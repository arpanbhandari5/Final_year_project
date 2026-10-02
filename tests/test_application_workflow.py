from app import app


def login(client, email, password):
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302


def test_manual_job_capture_resume_analysis_and_snapshot_lock():
    client = app.test_client()
    login(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    job_response = client.post(
        "/api/jobs",
        json={
            "title": "Data Analyst",
            "company": "Example Co",
            "source_url": "https://example.com/jobs/data-analyst",
            "description_raw": "Required: Python and SQL. Preferred: Tableau. Build dashboards.",
        },
    )
    assert job_response.status_code == 201
    job_id = job_response.json["job"]["id"]
    application_id = job_response.json["application"]["id"]

    resume_response = client.post(
        "/api/resume-versions",
        json={"name": "Analytics resume", "content_text": "Built Python dashboards and wrote SQL queries."},
    )
    assert resume_response.status_code == 201
    resume_id = resume_response.json["resume_version"]["id"]

    analysis_response = client.post("/api/jobs/analyze", json={"job_posting_id": job_id, "resume_version_id": resume_id})
    assert analysis_response.status_code == 200
    analysis = analysis_response.json["analysis"]
    assert "python" in analysis["required"]["matched"]
    assert "sql" in analysis["required"]["matched"]
    assert "tableau" in analysis["preferred"]["missing"]
    assert analysis["resume_evidence_quotes"]
    assert len(analysis_response.json["snapshot"]["snapshot_hash"]) == 64

    application = client.get("/api/applications").json["applications"][0]
    assert application["analysis_snapshot_id"] == analysis_response.json["snapshot"]["id"]
    moved = client.patch(f"/api/applications/{application_id}", json={"status": "Interviewing"})
    assert moved.status_code == 200
    assert moved.json["application"]["status"] == "Interviewing"

    exported = client.post(f"/api/applications/{application_id}/export-apply")
    assert exported.status_code == 200
    assert exported.json["snapshot_locked"] is True
    assert exported.json["export_format"] == "pdf"
    assert exported.json["application"]["status"] == "Applied"


def test_job_application_data_isolation_between_users():
    owner = app.test_client()
    login(owner, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    job_response = owner.post("/api/jobs", json={"title": "Private Role", "company": "Private Co", "description_raw": "Required: Python."})
    job_id = job_response.json["job"]["id"]
    application_id = job_response.json["application"]["id"]

    other = app.test_client()
    login(other, "student", "student")
    assert all(item["id"] != job_id for item in other.get("/api/jobs").json["jobs"])
    assert all(item["id"] != application_id for item in other.get("/api/applications").json["applications"])
    assert other.post("/api/jobs/analyze", json={"job_posting_id": job_id, "resume_version_id": 1}).status_code == 404
    assert other.patch(f"/api/applications/{application_id}", json={"status": "Rejected"}).status_code == 404


def test_tracker_endpoints_require_authentication():
    client = app.test_client()
    assert client.post("/api/jobs", json={"title": "Role", "description_raw": "JD"}).status_code == 401
    assert client.get("/api/applications").status_code == 401
    assert client.post("/api/jobs/analyze", json={"job_posting_id": 1, "resume_version_id": 1}).status_code == 401
