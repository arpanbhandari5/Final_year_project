from unittest.mock import patch

from app import app
from risk_assessor import _generate_roadmap, build_jd_match
from storage import CareerProfile, Feedback, PartnershipRequest, db


def test_admin_credentials_can_access_dashboard():
    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": app.config["ADMIN_EMAIL"], "password": app.config["ADMIN_PASSWORD"]},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Workspace" in response.data
    assert client.get("/admin").status_code == 200


def test_skill_overlap_has_evidence_and_missing_skills():
    result = build_jd_match(
        "Built Python dashboards with Tableau for stakeholders.",
        "Need Python, SQL, Tableau and stakeholder management.",
    )
    assert "python" in result["matched_skills"]
    assert "sql" in result["missing_skills"]
    assert result["evidence"]


def test_course_recommendations_always_have_a_direct_link():
    roadmap = _generate_roadmap(
        {"courses": {"sql": [{"title": "SQL Basics", "url": "", "short_intro": "Learn SQL."}]}},
        "Analyst", [], ["sql"],
    )
    assert roadmap[0]["url"].startswith("https://www.coursera.org/")


def test_advanced_mode_falls_back_when_ollama_is_unreachable():
    with patch("risk_assessor.requests.post", side_effect=OSError("offline")):
        from risk_assessor import _ollama_narrative
        assert _ollama_narrative("Python analyst", {"risk_score": .2, "top_roles": [], "riasec": {}, "roadmap": []}) is None


def test_feedback_and_partnership_response_persist():
    client = app.test_client()
    feedback_response = client.post("/api/feedback", json={"message": "Useful guidance", "rating": 1})
    assert feedback_response.status_code == 200
    with app.app_context():
        assert Feedback.query.filter_by(message="Useful guidance").first() is not None

    client.post("/partnerships", data={"organization": "Test College", "contact_email": "team@example.com", "use_case": "Career advising"})
    with app.app_context():
        request = PartnershipRequest.query.filter_by(organization="Test College").first()
        request_id = request.id
    client.post("/login", data={"email": app.config["ADMIN_EMAIL"], "password": app.config["ADMIN_PASSWORD"]})
    reply = client.post(f"/admin/partnerships/{request_id}/reply", data={"message": "We would be glad to talk."})
    assert reply.status_code == 200
    with app.app_context():
        assert db.session.get(PartnershipRequest, request_id).response_message


def test_authenticated_user_can_save_and_read_own_career_profile():
    client = app.test_client()
    client.post("/login", data={"email": "student", "password": "student"})
    response = client.put("/api/career-profile", json={"intent": "Find a role", "target_role": "Data Analyst"})
    assert response.status_code == 200
    assert response.json["profile"]["confidence"] == "self-reported"
    assert client.get("/api/career-profile").json["profile"]["target_role"] == "Data Analyst"
    with app.app_context():
        assert CareerProfile.query.filter_by(user_id=2, target_role="Data Analyst").first() is not None


def test_career_profile_requires_authentication_and_complete_fields():
    client = app.test_client()
    assert client.get("/api/career-profile").status_code == 401
    client.post("/login", data={"email": "student", "password": "student"})
    assert client.put("/api/career-profile", json={"intent": "Find a role"}).status_code == 400
