from app import app


def _login(client):
    return client.post(
        "/login",
        data={
            "email": app.config["ADMIN_EMAIL"],
            "password": app.config["ADMIN_PASSWORD"],
        },
        follow_redirects=True,
    )


def test_workspace_requires_authentication():
    client = app.test_client()
    response = client.get("/workspace")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_authenticated_user_can_access_workspace_and_upload_api():
    client = app.test_client()
    response = _login(client)
    assert response.status_code == 200
    assert b"Career direction" in response.data
    assert client.post("/api/upload", json={"resume_text": "Python analyst"}).status_code != 302


def test_upload_api_rejects_anonymous_requests():
    client = app.test_client()
    response = client.post("/api/upload", json={"resume_text": "Python analyst"})
    assert response.status_code == 401
