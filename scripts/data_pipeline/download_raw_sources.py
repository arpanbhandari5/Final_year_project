#!/usr/bin/env python3
"""Download the approved raw replacement sources. Does not train or invent labels."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "external_data" / "raw"

SOURCES = {
    "onet_31_0": {
        "url": "https://www.onetcenter.org/dl_files/database/db_31_0_text.zip",
        "path": RAW_DIR / "onet_31_0" / "onet_31_0_text.zip",
    },
    "historical_benchmark": {
        "url": "https://raw.githubusercontent.com/plotly/datasets/master/job-automation-probability.csv",
        "path": RAW_DIR / "historical_benchmark" / "frey_osborne_historical_702_occupations.csv",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"exists {destination}")
        return
    request = urllib.request.Request(url, headers={"User-Agent": "FinalYearProject/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())
    print(f"downloaded {destination}")


def main() -> None:
    for name, spec in SOURCES.items():
        download(spec["url"], spec["path"])
        print(f"{name}\t{spec['path'].stat().st_size}\t{sha256(spec['path'])}")


if __name__ == "__main__":
    main()
