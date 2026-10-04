"""Authentication scripts must reuse the interpreter running the tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_standalone_auth_scripts_use_sys_executable() -> None:
    for name in ("test_auth_e2e.py", "test_forgot_password.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "sys.executable" in text
        assert '["python"' not in text
        assert "['python'" not in text
