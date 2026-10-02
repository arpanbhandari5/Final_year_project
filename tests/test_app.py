from app import app
from storage import Upload, User, db, record_upload
from utils import redact_sensitive


def _login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def test_feedback_cannot_attach_to_another_users_upload():
    with app.app_context():
        admin = User.query.filter_by(username=app.config["ADMIN_EMAIL"]).first()
        upload = record_upload(
            filename="owned.txt",
            file_type="text",
            mode="standard",
            risk_score=0.2,
            risk_label="Low",
            reasoning={"summary": "test"},
            user_id=admin.id,
        )
        upload_id = upload.id

    client = app.test_client()
    _login(client, "student", "student")
    response = client.post("/api/feedback", json={"message": "Not mine", "upload_id": upload_id})
    assert response.status_code == 404


def test_log_redaction_removes_sensitive_values():
    payload = {
        "resume_text": "Private resume content",
        "password": "super-secret",
        "otp": "123456",
        "message": "token=abc123",
    }
    redacted = redact_sensitive(payload)
    assert redacted["resume_text"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["otp"] == "[REDACTED]"
    assert "abc123" not in redacted["message"]


def test_production_transport_flags_are_not_enabled():
    assert app.config["DEBUG"] is False
    assert app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] is False
