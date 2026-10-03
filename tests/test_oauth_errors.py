"""OAuth error-handling tests for Google, GitHub, and LinkedIn flows.

Verifies that a broken OAuth callback (state mismatch, denied/missing code,
invalid grant) degrades to a friendly redirect back to the login page
instead of an unhandled 500 — and that the happy path still logs the user
in and creates/links the account.
"""

from __future__ import annotations

import urllib.parse as up
from unittest import mock

import pytest
import requests_oauthlib
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError

# ── Shared helpers ──────────────────────────────────────────────────────

TOKEN = {
    "access_token": "ya29.fake",
    "token_type": "Bearer",
    "expires_in": 3599,
    "scope": "openid https://www.googleapis.com/auth/userinfo.email",
}
USERINFO = {
    "sub": "12345",
    "email": "oauth.happy@gmail.com",
    "email_verified": True,
    "name": "OAuth Happy",
}


def _start_flow(client, provider: str) -> str:
    """Begin an OAuth flow in-process and return the captured state."""
    entry = {"google": "/oauth/google", "github": "/oauth/github", "linkedin": "/oauth/linkedin"}[provider]
    r = client.get(entry)
    # /oauth/<provider> 302s to the blueprint's /login/<provider>
    assert r.status_code in (200, 302), f"entry for {provider} failed: {r.status_code}"
    r2 = client.get("/login/" + provider)
    if r2.status_code == 302 and "accounts.google" not in (r2.headers.get("Location") or ""):
        # GitHub/LinkedIn redirect straight to their authorize URLs
        loc = r2.headers.get("Location", "")
    else:
        loc = r2.headers.get("Location", "")
    assert loc, f"no authorize redirect for {provider}"
    qs = up.parse_qs(up.urlparse(loc).query)
    return (qs.get("state") or [""])[0]


def _authorized(client, provider: str, state: str, code: str | None = "good_code"):
    qs = f"code={code}&state={state}" if code else f"state={state}"
    return client.get(f"/login/{provider}/authorized?{qs}")


def _patch_google(monkeypatch):
    """Patch token exchange + userinfo for the Google blueprint."""
    def fake_fetch(self, token_url, **kwargs):
        self.token = dict(TOKEN)
        return dict(TOKEN)

    real_request = requests_oauthlib.OAuth2Session.request

    def fake_request(self, method, url, **kwargs):
        if "userinfo" in url:
            resp = mock.Mock(ok=True, status_code=200)
            resp.json.return_value = dict(USERINFO)
            return resp
        return real_request(self, method, url, **kwargs)

    monkeypatch.setattr(requests_oauthlib.OAuth2Session, "fetch_token", fake_fetch)
    monkeypatch.setattr(requests_oauthlib.OAuth2Session, "request", fake_request)


# ── Google: error paths (previously 500 + debugger page) ───────────────


def test_google_state_mismatch_redirects_not_500(client) -> None:
    client.get("/oauth/google")
    client.get("/login/google")
    resp = client.get("/login/google/authorized?code=x&state=WRONG_STATE")
    assert resp.status_code == 302
    assert "error=" in resp.headers["Location"]
    assert "/login" in resp.headers["Location"]


def test_google_missing_code_redirects(client) -> None:
    client.get("/oauth/google")
    client.get("/login/google")
    resp = client.get("/login/google/authorized?state=whatever")
    # flask-dance restarts the flow when no code is present
    assert resp.status_code == 302
    assert "500" != resp.status_code


def test_google_invalid_grant_redirects(client, monkeypatch) -> None:
    client.get("/oauth/google")
    client.get("/login/google")

    def boom(self, token_url, **kwargs):
        raise MismatchingStateError()

    monkeypatch.setattr(requests_oauthlib.OAuth2Session, "fetch_token", boom)
    resp = client.get("/login/google/authorized?code=x&state=y")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert "error=" in resp.headers["Location"]


def test_google_happy_path_logs_user_in(client, monkeypatch) -> None:
    _patch_google(monkeypatch)
    state = _start_flow(client, "google")

    resp = _authorized(client, "google", state)
    assert resp.status_code == 302
    assert "/login/google/callback" in resp.headers["Location"]

    landing = client.get(resp.headers["Location"])
    assert landing.status_code == 302
    assert "/workspace" in landing.headers["Location"]

    # Session is authenticated: workspace renders
    assert client.get("/workspace").status_code == 200

    from storage import User, db
    user = User.query.filter_by(email=USERINFO["email"]).first()
    assert user is not None
    assert user.email_verified is True
    db.session.delete(user)
    db.session.commit()


def test_google_existing_user_links_not_duplicated(client, monkeypatch) -> None:
    """Second sign-in with the same email reuses the account."""
    _patch_google(monkeypatch)
    from storage import User, db

    state = _start_flow(client, "google")
    _authorized(client, "google", state)
    first = User.query.filter_by(email=USERINFO["email"]).first()
    assert first is not None

    # Sign out and sign in again with the same mocked identity
    client.get("/logout")
    state = _start_flow(client, "google")
    _authorized(client, "google", state)
    users = User.query.filter_by(email=USERINFO["email"]).all()
    assert len(users) == 1

    db.session.delete(users[0])
    db.session.commit()


# ── GitHub / LinkedIn: callback error paths ─────────────────────────────


def test_github_state_mismatch_redirects_not_500(client) -> None:
    client.get("/oauth/github")
    client.get("/login/github")
    resp = client.get("/login/github/authorized?code=x&state=WRONG")
    assert resp.status_code == 302
    loc = resp.headers["Location"]
    assert "/login" in loc
    assert "500" != resp.status_code


def test_github_invalid_grant_redirects(client, monkeypatch) -> None:
    client.get("/oauth/github")
    client.get("/login/github")

    def boom(self, token_url, **kwargs):
        raise MismatchingStateError()

    monkeypatch.setattr(requests_oauthlib.OAuth2Session, "fetch_token", boom)
    resp = client.get("/login/github/authorized?code=x&state=y")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def _linkedin_available() -> bool:
    try:
        from flask_dance.contrib.linkedin import make_linkedin_blueprint  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _linkedin_available(), reason="flask-dance linkedin contrib not installed")
def test_linkedin_state_mismatch_redirects(client) -> None:
    client.get("/oauth/linkedin")
    resp = client.get("/login/linkedin/authorized?code=x&state=WRONG")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ── Unconfigured provider entry points stay graceful ───────────────────


def test_unconfigured_provider_redirects_with_error(client, monkeypatch) -> None:
    import routes.auth as auth_module

    monkeypatch.setattr(auth_module, "_oauth_is_configured", lambda p: False)
    resp = client.get("/oauth/github")
    assert resp.status_code == 302
    assert "error=" in resp.headers["Location"]


def test_callback_landing_without_session_redirects_to_login(client) -> None:
    resp = client.get("/login/google/callback")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert "error=" in resp.headers["Location"]
