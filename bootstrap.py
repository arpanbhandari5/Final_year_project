from __future__ import annotations

import subprocess
import sys
import os
import secrets
import warnings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "ml_models" / "automation_model.pkl"
LOCAL_ENVIRONMENTS = {"local", "development", "test"}


def runtime_security_settings() -> dict[str, str | bool]:
    app_env = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "local")).strip().lower()
    is_local = app_env in LOCAL_ENVIRONMENTS

    def required_secret(name: str, local_factory) -> str:
        value = os.environ.get(name, "").strip()
        if value:
            return value
        if not is_local:
            raise RuntimeError(f"{name} must be set outside local development.")
        warnings.warn(f"{name} is unset; using an ephemeral local-development value.", RuntimeWarning, stacklevel=2)
        return local_factory()

    if not is_local and os.environ.get("FLASK_DEBUG", "0") == "1":
        raise RuntimeError("FLASK_DEBUG must be disabled outside local development.")
    if not is_local:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "0"

    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if not admin_email:
        if not is_local:
            raise RuntimeError("ADMIN_EMAIL must be set outside local development.")
        warnings.warn("ADMIN_EMAIL is unset; using a local-development account.", RuntimeWarning, stacklevel=2)
        admin_email = "admin123@prayash"

    admin_password = required_secret("ADMIN_PASSWORD", lambda: secrets.token_urlsafe(24))
    os.environ.setdefault("ADMIN_EMAIL", admin_email)
    os.environ.setdefault("ADMIN_PASSWORD", admin_password)

    return {
        "app_env": app_env,
        "is_local": is_local,
        "flask_secret_key": required_secret("FLASK_SECRET_KEY", lambda: secrets.token_urlsafe(32)),
        "admin_password": admin_password,
        "admin_email": admin_email,
        "debug": is_local and os.environ.get("FLASK_DEBUG", "0") == "1",
    }


def ensure_model_artifacts() -> bool:
    if MODEL_PATH.exists():
        return False

    subprocess.run([sys.executable, str(BASE_DIR / "train_model.py")], check=True)
    return True


if __name__ == "__main__":
    ensure_model_artifacts()