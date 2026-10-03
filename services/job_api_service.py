"""RapidAPI JSearch live-job search, isolated and failure-safe.

Local career recommendation remains the primary engine; this only fetches
current openings for a selected role. Never exposed to the frontend.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

log = logging.getLogger("prayash.jobs")


class JobAPIService:
    BASE_URL = "https://jsearch.p.rapidapi.com/search"

    def __init__(self) -> None:
        self.api_key = os.getenv("RAPIDAPI_KEY") or ""
        self.host = os.getenv("RAPIDAPI_HOST") or "jsearch.p.rapidapi.com"

    def available(self) -> bool:
        return bool(self.api_key) and os.getenv("LIVE_JOBS_ENABLED", "false").lower() in ("1", "true", "yes")

    def search_jobs(self, role: str, location: str | None = None, page: int = 1) -> list[dict[str, Any]]:
        if not self.available() or not role:
            return []
        query = role.strip()
        if location:
            query = f"{query} in {location.strip()}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.host,
        }
        params = {"query": query, "page": str(max(int(page or 1), 1)), "num_pages": "1"}
        try:
            resp = requests.get(self.BASE_URL, headers=headers, params=params, timeout=10)
            if resp.status_code in (401, 403):
                log.warning("RapidAPI auth failed: %s", resp.status_code)
                return []
            if resp.status_code == 429:
                log.warning("RapidAPI quota exceeded")
                return []
            if resp.status_code != 200:
                log.warning("RapidAPI HTTP %s", resp.status_code)
                return []
            data = resp.json()
            return self._normalize(data.get("data", []) or [])
        except requests.Timeout:
            log.warning("RapidAPI timeout")
            return []
        except Exception:
            log.warning("RapidAPI request failed", exc_info=True)
            return []

    def _normalize(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for j in jobs:
            out.append({
                "title": j.get("job_title") or j.get("title") or "",
                "company": j.get("employer_name") or j.get("company") or "",
                "location": j.get("job_city") or j.get("job_country") or j.get("location") or "",
                "city": j.get("job_city") or "",
                "country": j.get("job_country") or "",
                "description": (j.get("job_description") or j.get("description") or "")[:500],
                "apply_url": j.get("job_apply_link") or j.get("apply_url") or j.get("job_google_link") or "",
                "source": "JSearch",
            })
        return out
