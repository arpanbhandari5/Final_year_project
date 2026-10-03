"""Pandas-backed career-role skill requirements service.

Loads ``data/career_skills.csv`` once and exposes cached, normalized
queries. No LLM involved — deterministic data only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "career_skills.csv"

_NORMALIZE = lambda s: s.strip().lower().replace("_", " ").replace("-", " ")


class CareerDataService:
    _instance: "CareerDataService | None" = None

    def __new__(cls) -> "CareerDataService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_loaded", False):
            return
        if not DATA_FILE.exists():
            raise FileNotFoundError(f"Career dataset missing: {DATA_FILE}")
        self.df = pd.read_csv(DATA_FILE)
        self.df["role_norm"] = self.df["role"].astype(str).str.strip().str.lower()
        self.df["skill_norm"] = self.df["skill"].astype(str).str.strip().str.lower()
        self._loaded = True

    def get_roles(self) -> list[str]:
        return sorted(self.df["role"].dropna().unique().tolist())

    def get_role_requirements(self, target_role: str) -> pd.DataFrame:
        norm = _NORMALIZE(str(target_role or ""))
        if not norm:
            return pd.DataFrame(columns=self.df.columns)
        return self.df[self.df["role_norm"] == norm].copy()

    def get_skill_importance(self, target_role: str, skill: str) -> int | None:
        reqs = self.get_role_requirements(target_role)
        if reqs.empty:
            return None
        skill_norm = str(skill or "").strip().lower()
        row = reqs[reqs["skill_norm"] == skill_norm]
        if row.empty:
            return None
        try:
            return int(row.iloc[0]["importance"])
        except Exception:
            return None

    def get_learning_sequence(self, target_role: str) -> list[dict[str, Any]]:
        reqs = self.get_role_requirements(target_role)
        if reqs.empty:
            return []
        reqs = reqs.sort_values(["learning_order", "importance"], ascending=[True, False])
        return reqs.to_dict(orient="records")
