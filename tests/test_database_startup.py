"""SQLite directory handling must not rewrite external database URLs."""

from __future__ import annotations

import logging
from pathlib import Path

from app import ensure_sqlite_parent_directory


def test_missing_sqlite_parent_is_created(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "app.db"
    uri = f"sqlite:///{database.as_posix()}"
    assert ensure_sqlite_parent_directory(uri) == uri
    assert database.parent.is_dir()
    assert not database.exists()


def test_existing_sqlite_directory_and_file_are_preserved(tmp_path: Path) -> None:
    database = tmp_path / "keep.db"
    database.write_text("sentinel", encoding="utf-8")
    uri = f"sqlite:///{database.as_posix()}"
    assert ensure_sqlite_parent_directory(uri) == uri
    assert database.read_text(encoding="utf-8") == "sentinel"


def test_external_and_memory_urls_are_not_rewritten(tmp_path: Path) -> None:
    external = "postgresql://db.example.invalid/prayash"
    assert ensure_sqlite_parent_directory(external) == external
    memory = "sqlite:///:memory:"
    assert ensure_sqlite_parent_directory(memory) == memory
    assert not (tmp_path / "should-not-exist").exists()


def test_directory_creation_errors_are_reported(tmp_path: Path, monkeypatch, caplog) -> None:
    database = tmp_path / "blocked" / "app.db"
    uri = f"sqlite:///{database.as_posix()}"

    def deny_mkdir(self, *args, **kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(Path, "mkdir", deny_mkdir)
    with caplog.at_level(logging.ERROR):
        try:
            ensure_sqlite_parent_directory(uri)
        except OSError as exc:
            assert exc.errno == 13
        else:
            raise AssertionError("directory creation failure must surface")
    assert "Failed to create SQLite directory" in caplog.text
