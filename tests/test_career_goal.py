from app import app


def login(client, email, password):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302


def test_career_goal_crud_and_user_isolation():
    client = app.test_client()
    login(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    response = client.post(
        "/api/career-goal",
        json={
            "target_role": "Data Analyst",
            "alternative_roles": ["BI Analyst", "Product Analyst"],
            "geography": "Remote",
            "seniority": "Entry level",
            "time_per_week": 8,
            "learning_budget": 250,
        },
    )
    assert response.status_code == 200
    assert response.json["goal"]["target_role"] == "Data Analyst"
    assert client.get("/api/career-goal").json["goal"]["geography"] == "Remote"

    other_client = app.test_client()
    login(other_client, "student", "Student@123")
    existing_other_goal = other_client.get("/api/career-goal").json["goal"]
    assert existing_other_goal is None or existing_other_goal["target_role"] != "Data Analyst"
    assert other_client.post("/api/career-goal", json={"target_role": "QA Engineer"}).status_code == 200
    assert other_client.get("/api/career-goal").json["goal"]["target_role"] == "QA Engineer"
    assert client.get("/api/career-goal").json["goal"]["target_role"] == "Data Analyst"


def test_evidence_skill_correction_persists_and_isolation_is_enforced():
    client = app.test_client()
    login(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    added = client.patch(
        "/api/evidence-profile/correct",
        json={"action": "add", "skill": "Python", "evidence_span": "Built Python dashboards", "confidence": 0.8},
    )
    assert added.status_code == 200
    skill = added.json["profile"]["extracted_skills"][0]
    skill_id = skill["id"]

    edited = client.patch(
        "/api/evidence-profile/correct",
        json={"action": "edit", "skill_id": skill_id, "skill": "Python analytics", "confidence": 0.9},
    )
    assert edited.status_code == 200
    assert edited.json["profile"]["extracted_skills"][0]["skill"] == "Python analytics"

    other_client = app.test_client()
    login(other_client, "student", "Student@123")
    assert other_client.get("/api/evidence-profile").json["profile"]["extracted_skills"] == []
    assert other_client.patch(
        "/api/evidence-profile/correct",
        json={"action": "delete", "skill_id": skill_id},
    ).status_code == 404

    deleted = client.patch(
        "/api/evidence-profile/correct",
        json={"action": "delete", "skill_id": skill_id},
    )
    assert deleted.status_code == 200
    assert deleted.json["profile"]["extracted_skills"] == []


def test_career_goal_delete_and_invalid_occupation():
    client = app.test_client()
    login(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    created = client.post(
        "/api/career-goal",
        json={
            "target_occupation_code": "15-1252.00",
            "immediate_goal": "Learn missing skills",
            "seniority": "Mid level",
            "time_per_week": 6,
        },
    )
    assert created.status_code == 200, created.json
    assert created.json["goal"]["target_role"] == "Software Developers"
    assert created.json["goal"]["target_occupation_code"] == "15-1252.00"
    denied = client.post("/api/career-goal", json={"target_occupation_code": "99-9999.99", "immediate_goal": "Learn missing skills"})
    assert denied.status_code == 400
    deleted = client.delete("/api/career-goal")
    assert deleted.status_code == 200
    assert client.get("/api/career-goal").json["goal"] is None


def test_action_create_complete_and_isolation():
    client = app.test_client()
    login(client, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])
    client.post(
        "/api/career-goal",
        json={"target_occupation_code": "15-1252.00", "immediate_goal": "Learn missing skills", "time_per_week": 4},
    )
    client.patch(
        "/api/evidence-profile/correct",
        json={"action": "add", "skill": "Python", "evidence_span": "Wrote Python scripts", "status": "confirmed"},
    )
    refreshed = client.post("/api/actions/refresh", json={})
    assert refreshed.status_code == 200, refreshed.json
    action = refreshed.json["action"]
    assert action["title"]
    completed = client.patch(f"/api/actions/{action['id']}", json={"status": "completed"})
    assert completed.status_code == 200
    assert completed.json["action"]["status"] == "completed"

    other = app.test_client()
    login(other, "student", "Student@123")
    stolen = other.patch(f"/api/actions/{action['id']}", json={"status": "in_progress"})
    assert stolen.status_code == 404

    loop = client.get("/api/workspace-loop")
    assert loop.status_code == 200
    # GET must not mint a new action after completion
    assert loop.json["action"] is None or loop.json["action"]["id"] == action["id"]


def test_career_goal_and_evidence_require_authentication():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()
    assert client.get("/api/career-goal").status_code == 401
    assert client.get("/api/evidence-profile").status_code == 401
    assert client.patch("/api/evidence-profile/correct", json={"action": "add", "skill": "SQL"}).status_code == 401
    assert client.get("/api/workspace-loop").status_code == 401
    assert client.post("/api/actions/refresh", json={}).status_code == 401
    assert client.patch("/api/actions/1", json={"status": "completed"}).status_code == 401
    assert client.delete("/api/career-goal").status_code == 401
    assert client.post("/api/evidence-profile/import", json={"skills": []}).status_code == 401
