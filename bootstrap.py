from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "ml_models" / "model.pkl"


def ensure_model_artifacts() -> bool:
    if MODEL_PATH.exists():
        return False

    subprocess.run([sys.executable, str(BASE_DIR / "train_model.py")], check=True)
    return True


if __name__ == "__main__":
    ensure_model_artifacts()