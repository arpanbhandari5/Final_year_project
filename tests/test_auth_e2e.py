from app import app

app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False


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
    assert b"Your next step" in response.data
    assert b"Current goal" in response.data
    assert client.post("/api/upload", json={"resume_text": "Python analyst"}).status_code != 302


def test_upload_api_is_available_without_a_login_redirect():
    """README documents POST /api/upload as a public analysis route.

    The workspace page stays login-protected. Anonymous analysis must not
    be redirected to the login form.
    """
    client = app.test_client()
    response = client.post("/api/upload", json={"resume_text": "Python analyst"})
    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()["success"] is True
