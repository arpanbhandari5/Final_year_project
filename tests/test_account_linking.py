"""Account-linking tests: attach an OAuth identity to an existing
email/password account, sign in via provider identity or email link,
and refuse to unlink when the account has no password."""

from __future__ import annotations

import urllib.parse as up
from unittest import mock

import pytest
import requests_oauthlib
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError


def _link_user(client, user):
    """Log *user* in by planting the Flask-Login session fields."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = False


def _patch_google(monkeypatch, email: str, sub: str = "google-sub-42"):
    def fake_fetch(self, token_url, **kwargs):
        token = {"access_token": "ya29.fake", "token_type": "Bearer", "expires_in": 3599}
        self.token = token
        return token

    real_request = requests_oauthlib.OAuth2Session.request

    def fake_request(self, method, url, **kwargs):
        if "userinfo" in url:
            resp = mock.Mock(ok=True, status_code=200)
            resp.json.return_value = {
                "sub": sub,
                "email": email,
                "email_verified": True,
                "name": "Linked User",
            }
            return resp
        return real_request(self, method, url, **kwargs)

    monkeypatch.setattr(requests_oauthlib.OAuth2Session, "fetch_token", fake_fetch)
    monkeypatch.setattr(requests_oauthlib.OAuth2Session, "request", fake_request)


def _run_google(client, monkeypatch, email: str, sub: str = "google-sub-42") -> None:
    _patch_google(monkeypatch, email, sub)
    client.get("/oauth/google")
    r = client.get("/login/google")
    state = up.parse_qs(up.urlparse(r.headers["Location"]).query)["state"][0]
    client.get(f"/login/google/authorized?code=good&state={state}")


# ── Attach flow (signed-in user links a provider) ───────────────────────


def test_attach_start_marks_session_and_redirects(client) -> None:
    from storage import User, db

    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = False

    with client.application.app_context():
        user = db.session.get(User, 1)

    resp = client.post("/settings/linked-accounts/google/start")
    assert resp.status_code == 302
    # First hop lands on the flask-dance login view (which then 302s to Google)
    assert resp.headers["Location"].endswith("/login/google")
    hop = client.get(resp.headers["Location"])
    assert "accounts.google" in hop.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("oauth_attach_google") == str(user.id)


def test_attach_flow_links_provider_to_signed_in_user(client, monkeypatch) -> None:
    from storage import OAuthAccount, User, db

    # Create a local user with a DIFFERENT email than the OAuth identity
    with client.application.app_context():
        u = User(email="local.user@test.local", username="localuser", full_name="Local User",
                 role="student", email_verified=True)
        u.set_password("Local-Passw0rd!")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    _link_user(client, db.session.get(User, uid))
    # Google identity has a different email — the ATTACH flow must still
    # link it to the signed-in local user (not create a new account).
    _patch_google(monkeypatch, email="someone.else@gmail.com", sub="attach-sub-7")
    resp = client.post("/settings/linked-accounts/google/start")
    assert resp.status_code == 302
    client.get(resp.headers["Location"])  # /login/google → captures state
    # Re-fetch the authorize URL to read the state (flask-dance stores it server-side)
    r = client.get("/login/google")
    state = up.parse_qs(up.urlparse(r.headers["Location"]).query)["state"][0]
    client.get(f"/login/google/authorized?code=good&state={state}")

    with client.application.app_context():
        account = OAuthAccount.query.filter_by(provider="google", provider_user_id="attach-sub-7").first()
        assert account is not None
        assert account.user_id == uid
        # Session now authenticated as the local user again
        assert client.get("/workspace").status_code == 200

        db.session.delete(account)
        db.session.delete(db.session.get(User, uid))
        db.session.commit()


# ── Sign-in resolution order ─────────────────────────────────────────────


def test_identity_match_takes_precedence_over_email(client, monkeypatch) -> None:
    """A linked identity signs in even if the provider email changed."""
    from storage import OAuthAccount, User, db, link_oauth_account

    with client.application.app_context():
        u = User(email="identity.match@test.local", username="idmatch", role="student", email_verified=True)
        u.set_password("Local-Passw0rd!")
        db.session.add(u)
        db.session.commit()
        link_oauth_account(u, "google", "durable-sub-9")
        uid = u.id

    # Google reports a NEW email for the same sub
    _run_google(client, monkeypatch, email="renamed@gmail.com", sub="durable-sub-9")

    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(uid)

    with client.application.app_context():
        db.session.delete(OAuthAccount.query.filter_by(provider="google", provider_user_id="durable-sub-9").first())
        db.session.delete(db.session.get(User, uid))
        db.session.commit()


def test_email_match_links_identity(client, monkeypatch) -> None:
    """Signing in with the same email attaches the identity (keeps password)."""
    from storage import OAuthAccount, User, db

    with client.application.app_context():
        u = User(email="shared.email@test.local", username="sharedemail", role="student", email_verified=True)
        u.set_password("Local-Passw0rd!")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    _run_google(client, monkeypatch, email="shared.email@test.local", sub="email-link-sub")

    with client.application.app_context():
        account = OAuthAccount.query.filter_by(provider="google", provider_user_id="email-link-sub").first()
        assert account is not None and account.user_id == uid
        with client.session_transaction() as sess:
            assert sess.get("_user_id") == str(uid)

        db.session.delete(account)
        db.session.delete(db.session.get(User, uid))
        db.session.commit()


# ── Unlink safety ────────────────────────────────────────────────────────


def test_unlink_removes_identity(client, monkeypatch) -> None:
    from storage import OAuthAccount, User, db, link_oauth_account

    with client.application.app_context():
        u = User(email="unlink.me@test.local", username="unlinkme", role="student", email_verified=True)
        u.set_password("Local-Passw0rd!")
        db.session.add(u)
        db.session.commit()
        link_oauth_account(u, "google", "unlink-sub")
        uid = u.id

    _link_user(client, db.session.get(User, uid))
    resp = client.post("/settings/linked-accounts/google/remove")
    assert resp.status_code == 302

    with client.application.app_context():
        assert OAuthAccount.query.filter_by(user_id=uid, provider="google").first() is None
        db.session.delete(db.session.get(User, uid))
        db.session.commit()


def test_unlink_refused_without_password(client, monkeypatch) -> None:
    """OAuth-only account (no password) cannot unlink its last provider."""
    from storage import OAuthAccount, User, db, link_oauth_account

    with client.application.app_context():
        u = User(email="pwless@test.local", username="pwless", role="student", email_verified=True)
        u.password_hash = ""  # OAuth-only: no local password
        db.session.add(u)
        db.session.commit()
        link_oauth_account(u, "google", "pwless-sub")
        uid = u.id

    _link_user(client, db.session.get(User, uid))
    client.post("/settings/linked-accounts/google/remove")

    with client.application.app_context():
        assert OAuthAccount.query.filter_by(user_id=uid, provider="google").first() is not None
        db.session.delete(OAuthAccount.query.filter_by(user_id=uid, provider="google").first())
        db.session.delete(db.session.get(User, uid))
        db.session.commit()


def test_state_mismatch_still_graceful_with_linking(client) -> None:
    """Linking changes must not regress the 500-on-state-mismatch fix."""
    client.get("/oauth/google")
    client.get("/login/google")
    resp = client.get("/login/google/authorized?code=x&state=WRONG")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
