"""Session-bound occupation confirmation must not trust client occupation codes."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("MAIL_USERNAME", "")
os.environ.setdefault("MAIL_PASSWORD", "")
os.environ.setdefault("SMTP_USERNAME", "")
os.environ.setdefault("SMTP_PASSWORD", "")

_TEST_DB_DIR = Path(tempfile.mkdtemp())
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{(_TEST_DB_DIR / 'test_occupation_auth.db').as_posix()}",
)

RESUME = (
    "Chief Executives officer with 15 years of corporate leadership experience. "
    "Managed large teams, strategy, and operations across software and finance. "
    "Python and SQL are secondary skills. Board reporting and policy decisions."
)


@pytest.fixture
def app():
    from app import app as flask_app
    from tests.conftest import assert_not_project_database, rebind_database

    previous_uri = flask_app.config["SQLALCHEMY_DATABASE_URI"]
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    db_path = _TEST_DB_DIR / f"test_{uuid4().hex[:8]}.db"
    test_uri = f"sqlite:///{db_path.as_posix()}"
    rebind_database(flask_app, test_uri)

    with flask_app.app_context():
        from storage import db, seed_default_users

        assert_not_project_database(flask_app)
        db.create_all()
        seed_default_users()
        yield flask_app
        db.session.remove()
        db.drop_all()
    rebind_database(flask_app, previous_uri)
    with flask_app.app_context():
        from storage import db, seed_default_users

        db.create_all()
        seed_default_users()
    try:
        if db_path.exists():
            db_path.unlink()
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def _inventory():
    from occupation_authorization import allowlist_inventory

    return allowlist_inventory()


def _upload(client, resume=RESUME):
    response = client.post("/api/upload", json={"resume_text": resume, "mode": "standard"})
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["success"] is True
    assert payload.get("analysis_id")
    assert payload.get("candidate_id")
    return payload


def _confirm(client, analysis_id, candidate_id, extra=None):
    body = {"analysis_id": analysis_id, "candidate_id": candidate_id, "action": "confirm_candidate"}
    if extra:
        body.update(extra)
    return client.post("/api/confirm-occupation", json=body)


def _select(client, analysis_id, selected_code, extra=None):
    body = {"analysis_id": analysis_id, "selected_code": selected_code, "action": "select_occupation"}
    if extra:
        body.update(extra)
    return client.post("/api/select-occupation", json=body)


def test_allowlist_is_unique_800_benchmark_intersection() -> None:
    inv = _inventory()
    selectable = inv["selectable"]
    assert inv["selectable_codes"] == len(selectable)
    assert len(selectable) == len(set(selectable))
    assert inv["duplicates"] >= 0
    for code, row in selectable.items():
        assert code in inv["product_set"]
        assert code in inv["benchmark_set"]
        assert row["occupation_title"]
        assert row["selectable"] is True
        assert row["in_product_800"] is True
        assert row["benchmark_coverage"] is True


def test_selectable_endpoint_omits_client_flags(client) -> None:
    response = client.get("/api/occupations/selectable")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == len(data["occupations"])
    assert data["count"] == _inventory()["selectable_codes"]
    first = data["occupations"][0]
    assert set(first) == {"occupation_code", "occupation_title"}


def test_valid_candidate_confirm_uses_stored_code(client) -> None:
    payload = _upload(client)
    occ = payload.get("occupation_match") or payload.get("occupation_candidate") or {}
    stored = occ.get("candidate_code")
    assert stored
    response = _confirm(
        client,
        payload["analysis_id"],
        payload["candidate_id"],
        extra={
            "verified_occupation_code": "15-1252.00",
            "candidate_code": "15-1252.00",
            "candidate_title": "Forged Title",
            "confirmation_method": "resume_verified_occupation",
            "in_product_800": True,
            "benchmark_coverage": True,
        },
    )
    if stored not in _inventory()["selectable"]:
        assert response.status_code == 400
        assert response.get_json()["error_code"] in {
            "occupation_outside_product_scope",
            "benchmark_coverage_unavailable",
            "candidate_invalid",
        }
        return
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    match = data["occupation_match"]
    assert match["status"] == "confirmed"
    assert match["verified_occupation_code"] == stored
    assert match["verified_occupation_title"] != "Forged Title"
    assert match["confirmation_method"] == "candidate_confirmation"
    assert match["source"] == "server_issued_candidate"
    assert data["task_exposure"]["status"] == "verified"
    assert data["task_exposure"]["occupation_code"] == stored


def test_wrong_candidate_id_rejected(client) -> None:
    payload = _upload(client)
    response = _confirm(client, payload["analysis_id"], "not-the-candidate")
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "candidate_not_owned"


def test_other_analysis_id_rejected(client) -> None:
    first = _upload(client)
    second = _upload(client)
    response = _confirm(client, first["analysis_id"], second["candidate_id"])
    assert response.status_code in {400, 403}
    assert response.get_json()["error_code"] in {"analysis_not_found", "candidate_not_owned"}


def test_cross_session_cannot_confirm(client, app) -> None:
    payload = _upload(client)
    other = app.test_client()
    response = _confirm(other, payload["analysis_id"], payload["candidate_id"])
    assert response.status_code in {400, 403}
    assert response.get_json()["error_code"] in {"analysis_not_found", "analysis_not_owned"}


def test_bound_user_id_mismatch_rejected(client) -> None:
    payload = _upload(client)
    with client.session_transaction() as sess:
        pending = dict(sess.get("pending_occupation_analyses") or {})
        record = dict(pending[payload["analysis_id"]])
        record["user_id"] = 999999
        pending[payload["analysis_id"]] = record
        sess["pending_occupation_analyses"] = pending
    response = _confirm(client, payload["analysis_id"], payload["candidate_id"])
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "analysis_not_owned"


def test_expired_analysis_rejected(client) -> None:
    payload = _upload(client)
    with client.session_transaction() as sess:
        pending = dict(sess.get("pending_occupation_analyses") or {})
        record = dict(pending[payload["analysis_id"]])
        record["expires_at"] = time.time() - 10
        pending[payload["analysis_id"]] = record
        sess["pending_occupation_analyses"] = pending
    response = _confirm(client, payload["analysis_id"], payload["candidate_id"])
    assert response.status_code in {400, 403}
    assert response.get_json()["error_code"] in {"analysis_expired", "analysis_not_found"}


def test_replay_after_confirm_rejected(client) -> None:
    payload = _upload(client)
    stored = (payload.get("occupation_match") or {}).get("candidate_code")
    if stored not in _inventory()["selectable"]:
        pytest.skip("matcher did not issue a selectable candidate for replay test")
    first = _confirm(client, payload["analysis_id"], payload["candidate_id"])
    assert first.status_code == 200, first.get_json()
    second = _confirm(client, payload["analysis_id"], payload["candidate_id"])
    assert second.status_code == 403
    assert second.get_json()["error_code"] == "candidate_consumed"


def test_valid_select_uses_server_title(client) -> None:
    payload = _upload(client)
    response = _select(
        client,
        payload["analysis_id"],
        "15-1252.00",
        extra={
            "verified_occupation_code": "11-1011.00",
            "confirmation_method": "resume_verified_occupation",
            "in_product_800": True,
            "occupation_title": "Forged Developers",
        },
    )
    assert response.status_code == 200, response.get_json()
    match = response.get_json()["occupation_match"]
    assert match["verified_occupation_code"] == "15-1252.00"
    assert match["verified_occupation_title"] == "Software Developers"
    assert match["confirmation_method"] == "user_selected_occupation"
    assert match["source"] == "user_selection"
    assert response.get_json()["task_exposure"]["occupation_code"] == "15-1252.00"


def test_garbage_and_missing_soc_rejected(client) -> None:
    payload = _upload(client)
    garbage = _select(client, payload["analysis_id"], "not-a-soc")
    assert garbage.status_code == 400
    assert garbage.get_json()["error_code"] == "occupation_selection_invalid"
    missing = _select(client, payload["analysis_id"], "99-9999.99")
    assert missing.status_code == 400
    assert missing.get_json()["error_code"] in {
        "occupation_not_canonical",
        "occupation_outside_product_scope",
    }


def test_benchmark_only_code_rejected(client) -> None:
    payload = _upload(client)
    inv = _inventory()
    only_bench = sorted(code for code in inv["benchmark_set"] if code not in inv["product_set"])
    assert only_bench, "expected at least one 923-only occupation"
    response = _select(
        client,
        payload["analysis_id"],
        only_bench[0],
        extra={"in_product_800": True, "benchmark_coverage": True},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["error_code"] == "occupation_outside_product_scope"
    assert data.get("product_coverage_available") is False
    assert data.get("research_benchmark_available") is True
    assert data.get("status") == "unavailable"


def test_800_without_benchmark_rejected(client) -> None:
    payload = _upload(client)
    inv = _inventory()
    only_800 = sorted(code for code in inv["product_set"] if code not in inv["benchmark_set"])
    if not only_800:
        pytest.skip("every 800 code is benchmark-covered")
    response = _select(client, payload["analysis_id"], only_800[0])
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "benchmark_coverage_unavailable"


def test_csrf_missing_rejected_valid_accepted(app) -> None:
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    token = client.get("/api/csrf-token").get_json()["csrf_token"]
    upload = client.post(
        "/api/upload",
        json={"resume_text": RESUME, "mode": "standard"},
        headers={"X-CSRFToken": token},
    )
    assert upload.status_code == 200, upload.get_json()
    payload = upload.get_json()
    missing = client.post(
        "/api/confirm-occupation",
        json={
            "analysis_id": payload["analysis_id"],
            "candidate_id": payload["candidate_id"],
            "action": "confirm_candidate",
        },
    )
    assert missing.status_code == 400
    body = (missing.get_json() or {})
    text = str(body) + missing.get_data(as_text=True)
    assert "csrf" in text.lower()
    token = client.get("/api/csrf-token").get_json()["csrf_token"]
    stored = (payload.get("occupation_match") or {}).get("candidate_code")
    accepted = client.post(
        "/api/confirm-occupation",
        json={
            "analysis_id": payload["analysis_id"],
            "candidate_id": payload["candidate_id"],
            "action": "confirm_candidate",
        },
        headers={"X-CSRFToken": token},
    )
    if stored in _inventory()["selectable"]:
        assert accepted.status_code == 200, accepted.get_json()
        assert accepted.get_json()["occupation_match"]["confirmation_method"] == "candidate_confirmation"
    else:
        assert accepted.status_code == 400
    invalid = client.post(
        "/api/confirm-occupation",
        json={
            "analysis_id": payload["analysis_id"],
            "candidate_id": payload["candidate_id"],
            "action": "confirm_candidate",
        },
        headers={"X-CSRFToken": "not-a-valid-csrf-token"},
    )
    assert invalid.status_code == 400
    invalid_text = str(invalid.get_json() or {}) + invalid.get_data(as_text=True)
    assert "csrf" in invalid_text.lower()
    app.config["WTF_CSRF_ENABLED"] = False


def test_session_does_not_store_resume_or_skills(client) -> None:
    payload = _upload(client)
    with client.session_transaction() as sess:
        blob = str(dict(sess))
        assert RESUME not in blob
        assert "Chief Executives officer" not in blob
        pending = sess.get("pending_occupation_analyses") or {}
        assert payload["analysis_id"] in pending
        record = pending[payload["analysis_id"]]
        allowed = {
            "analysis_id",
            "candidate_id",
            "candidate_code",
            "candidate_title",
            "candidate_matcher_score",
            "created_at",
            "expires_at",
            "consumed",
            "session_nonce",
            "user_id",
        }
        assert set(record) <= allowed
        for key in ("resume_text", "skills", "filename", "prompt"):
            assert key not in record


def test_invalid_inputs_never_call_benchmark_lookup(client, monkeypatch) -> None:
    calls: list[object] = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("lookup_verified_task_exposure must not run")

    monkeypatch.setattr("occupation_authorization.lookup_verified_task_exposure", forbidden)
    payload = _upload(client)
    analysis_id = payload["analysis_id"]
    inv = _inventory()
    only_bench = sorted(code for code in inv["benchmark_set"] if code not in inv["product_set"])
    garbage = _select(client, analysis_id, "not-a-soc")
    assert garbage.status_code == 400
    wrong = _confirm(client, analysis_id, "wrong-candidate")
    assert wrong.status_code == 403
    if only_bench:
        research = _select(client, analysis_id, only_bench[0])
        assert research.status_code == 400
    expired_payload = _upload(client)
    with client.session_transaction() as sess:
        pending = dict(sess.get("pending_occupation_analyses") or {})
        record = dict(pending[expired_payload["analysis_id"]])
        record["expires_at"] = time.time() - 10
        pending[expired_payload["analysis_id"]] = record
        sess["pending_occupation_analyses"] = pending
    expired = _confirm(client, expired_payload["analysis_id"], expired_payload["candidate_id"])
    assert expired.status_code in {400, 403}
    assert calls == []


def test_client_cannot_confirm_other_occupation_but_can_select_supported(client) -> None:
    payload = _upload(client)
    stored = (payload.get("occupation_match") or {}).get("candidate_code")
    assert stored
    forged_code = "15-1252.00" if stored != "15-1252.00" else "11-1011.00"
    forged = _confirm(
        client,
        payload["analysis_id"],
        payload["candidate_id"],
        extra={
            "verified_occupation_code": forged_code,
            "confirmation_method": "user_selected_occupation",
            "in_product_800": True,
        },
    )
    if forged.status_code == 200:
        match = forged.get_json()["occupation_match"]
        assert match["verified_occupation_code"] == stored
        assert match["verified_occupation_code"] != forged_code
        assert match["confirmation_method"] == "candidate_confirmation"
    else:
        assert forged.status_code in {400, 403}
        body = forged.get_json() or {}
        assert (body.get("occupation_match") or {}).get("verified_occupation_code") != forged_code

    payload_b = _upload(client)
    selected = _select(client, payload_b["analysis_id"], forged_code)
    assert selected.status_code == 200, selected.get_json()
    selected_match = selected.get_json()["occupation_match"]
    assert selected_match["verified_occupation_code"] == forged_code
    assert selected_match["confirmation_method"] == "user_selected_occupation"
    assert selected.get_json()["task_exposure"]["occupation_code"] == forged_code


def test_malformed_allowlist_fails_closed(tmp_path, monkeypatch) -> None:
    import occupation_authorization as auth

    missing = tmp_path / "missing.csv"
    monkeypatch.setattr(auth, "PRODUCT_800_PATH", missing)
    auth.allowlist_inventory.cache_clear()
    with pytest.raises(auth.AuthorizationError) as missing_exc:
        auth.allowlist_inventory()
    assert missing_exc.value.code == "allowlist_unavailable"

    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(auth, "PRODUCT_800_PATH", bad)
    auth.allowlist_inventory.cache_clear()
    with pytest.raises(auth.AuthorizationError) as bad_exc:
        auth.allowlist_inventory()
    assert bad_exc.value.code == "allowlist_unavailable"
    auth.allowlist_inventory.cache_clear()

