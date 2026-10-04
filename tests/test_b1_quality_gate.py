"""B1 quality-closure: CSRF on workspace mutations and GET must not persist actions."""

from __future__ import annotations

from app import app


def _login_with_csrf(client):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    client.get("/login")
    token = client.get("/api/csrf-token").get_json()["csrf_token"]
    response = client.post(
        "/login",
        data={
            "email": app.config["ADMIN_EMAIL"],
            "password": app.config["ADMIN_PASSWORD"],
            "csrf_token": token,
        },
        headers={"X-CSRFToken": token},
    )
    assert response.status_code in {200, 302}, response.status_code
    return client.get("/api/csrf-token").get_json()["csrf_token"]


def test_workspace_mutations_require_csrf() -> None:
    previous = app.config.get("WTF_CSRF_ENABLED")
    client = app.test_client()
    try:
        token = _login_with_csrf(client)
        missing = client.post(
            "/api/career-goal",
            json={"target_occupation_code": "15-1252.00", "immediate_goal": "Learn missing skills"},
        )
        assert missing.status_code == 400
        assert "csrf" in (missing.get_data(as_text=True) + str(missing.get_json() or {})).lower()

        invalid = client.post(
            "/api/career-goal",
            json={"target_occupation_code": "15-1252.00", "immediate_goal": "Learn missing skills"},
            headers={"X-CSRFToken": "not-a-valid-csrf-token"},
        )
        assert invalid.status_code == 400

        ok = client.post(
            "/api/career-goal",
            json={"target_occupation_code": "15-1252.00", "immediate_goal": "Learn missing skills"},
            headers={"X-CSRFToken": token},
        )
        assert ok.status_code == 200, ok.get_json()

        get_loop = client.get("/api/workspace-loop")
        assert get_loop.status_code == 200
        with app.app_context():
            from storage import ActionItem, User

            user = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
            before = ActionItem.query.filter_by(user_id=user.id).count()
        client.get("/api/workspace-loop")
        with app.app_context():
            after = ActionItem.query.filter_by(user_id=user.id).count()
        assert after == before

        refresh = client.post("/api/actions/refresh", json={}, headers={"X-CSRFToken": token})
        assert refresh.status_code == 200
        action = refresh.get_json()["action"]
        assert action and action["id"]

        evidence_missing = client.patch(
            "/api/evidence-profile/correct",
            json={"action": "add", "skill": "SQL", "evidence_span": "Used SQL"},
        )
        assert evidence_missing.status_code == 400

        evidence_ok = client.patch(
            "/api/evidence-profile/correct",
            json={"action": "add", "skill": "SQL", "evidence_span": "Used SQL"},
            headers={"X-CSRFToken": token},
        )
        assert evidence_ok.status_code == 200, evidence_ok.get_json()
        profile = client.get("/api/evidence-profile").get_json()["profile"]
        for skill in profile.get("extracted_skills") or []:
            client.patch(
                "/api/evidence-profile/correct",
                json={"action": "delete", "skill_id": skill["id"]},
                headers={"X-CSRFToken": token},
            )
        client.delete("/api/career-goal", headers={"X-CSRFToken": token})
    finally:
        app.config["WTF_CSRF_ENABLED"] = previous if previous is not None else False
