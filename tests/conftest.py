"""Keep pytest off the project SQLite file.

The application binds its engine while it is imported. This file runs first
and points that import at a temporary database when the environment would
otherwise use ``instance/prayash.db``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_SUITE_DIR = Path(tempfile.mkdtemp(prefix="prayash-pytest-"))
_SUITE_DB = _SUITE_DIR / "suite.db"


def _is_project_database(database_url: str) -> bool:
    normalized = database_url.replace("\\", "/").lower()
    return normalized.endswith("/instance/prayash.db")


_current = os.environ.get("DATABASE_URL", "")
if not _current or _is_project_database(_current):
    os.environ["DATABASE_URL"] = f"sqlite:///{_SUITE_DB.as_posix()}"

os.environ.setdefault("MAIL_USERNAME", "")
os.environ.setdefault("MAIL_PASSWORD", "")
os.environ.setdefault("SMTP_USERNAME", "")
os.environ.setdefault("SMTP_PASSWORD", "")


def rebind_database(flask_app, database_uri: str):
    """Point the existing SQLAlchemy engine at ``database_uri``.

    ``init_app`` cannot be called twice, so the default engine is replaced
    in place. The URI string itself is not rewritten for the caller.
    """
    if _is_project_database(database_uri):
        raise RuntimeError("Refusing to bind tests to instance/prayash.db")
    from sqlalchemy import create_engine
    from storage import db

    flask_app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    with flask_app.app_context():
        db.session.remove()
        engines = db._app_engines.setdefault(flask_app, {})
        previous = engines.get(None)
        if previous is not None:
            previous.dispose()
        engines[None] = create_engine(database_uri)


def pytest_addoption(parser):
    parser.addoption(
        "--run-browser",
        action="store_true",
        default=False,
        help="Execute live Flask Playwright verification (server must be running).",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "browser_live: live Flask + Playwright")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-browser"):
        return
    skip_browser = pytest.mark.skip(reason="Needs live Flask; run with pytest --run-browser")
    for item in items:
        if "browser_live" in item.keywords:
            item.add_marker(skip_browser)


def assert_not_project_database(flask_app) -> None:
    uri = str(flask_app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    if _is_project_database(uri):
        raise RuntimeError("Refusing to reset instance/prayash.db during tests")
