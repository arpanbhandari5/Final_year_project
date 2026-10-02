from app import app


def login(client, email, password):
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
    login(other_client, "student", "student")
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
    login(other_client, "student", "student")
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


def test_career_goal_and_evidence_require_authentication():
    client = app.test_client()
    assert client.get("/api/career-goal").status_code == 401
    assert client.get("/api/evidence-profile").status_code == 401
    assert client.patch("/api/evidence-profile/correct", json={"action": "add", "skill": "SQL"}).status_code == 401
