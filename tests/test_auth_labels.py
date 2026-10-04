"""Visible labels on authentication forms. Does not change login semantics."""

from app import app


def test_login_and_signup_have_visible_labels():
    client = app.test_client()
    login = client.get("/login")
    assert login.status_code == 200
    html = login.get_data(as_text=True)
    assert 'for="login-email"' in html
    assert ">Email or username<" in html
    assert 'for="login-password"' in html
    assert ">Password<" in html
    assert 'id="login-email"' in html
    assert 'id="login-password"' in html

    signup = client.get("/signup")
    assert signup.status_code == 200
    signup_html = signup.get_data(as_text=True)
    for field_id, label in (
        ("signup-name", "Full name"),
        ("signup-username", "Username"),
        ("signup-email", "Email address"),
        ("signup-phone", "Phone number (optional)"),
        ("signup-password", "Password"),
        ("confirm-password", "Confirm password"),
    ):
        assert f'for="{field_id}"' in signup_html
        assert label in signup_html


def test_forgot_and_reset_templates_keep_visible_labels():
    client = app.test_client()
    forgot = client.get("/forgot-password")
    assert forgot.status_code == 200
    assert 'for="forgot-email"' in forgot.get_data(as_text=True)
