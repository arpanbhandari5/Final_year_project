from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app import app
from storage import (
    OnetInterest,
    OnetOccupation,
    OnetSkill,
    OnetTask,
    OnetTechnology,
    db,
)

DATA_DIR = BASE_DIR / "data"
DEFAULT_RELEASE = os.environ.get("ONET_RELEASE_VERSION", "28.0")
DEFAULT_RELEASE_DATE = os.environ.get("ONET_RELEASE_DATE", "2026")


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",\t").delimiter
        except csv.Error:
            delimiter = "\t" if "\t" in sample.splitlines()[0] else ","
        return list(csv.DictReader(handle, delimiter=delimiter))


def value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if row.get(key):
            return row[key].strip()
    return ""


def number(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def insert_batches(model: Any, rows: list[dict[str, Any]], batch_size: int = 1000) -> None:
    for start in range(0, len(rows), batch_size):
        db.session.bulk_insert_mappings(model, rows[start:start + batch_size])
        db.session.commit()


def import_onet(release_version: str = DEFAULT_RELEASE, release_date: str = DEFAULT_RELEASE_DATE) -> dict[str, int | str]:
    skill_rows = read_rows(DATA_DIR / "onet_skils.csv")
    interest_rows = read_rows(DATA_DIR / "onet_interests.csv")
    task_rows = [row for path in sorted(DATA_DIR.glob("onet_tasks*.csv")) for row in read_rows(path)]
    technology_rows = [row for path in sorted(DATA_DIR.glob("onet_technology*.csv")) for row in read_rows(path)]
    codes = sorted({value(row, "O*NET-SOC Code", "SOC Code", "onet_soc_code") for row in skill_rows + interest_rows if value(row, "O*NET-SOC Code", "SOC Code", "onet_soc_code")})

    imported_at = datetime.now(timezone.utc)
    with app.app_context():
        for model in (OnetTask, OnetSkill, OnetTechnology, OnetInterest, OnetOccupation):
            db.session.query(model).delete()
        db.session.commit()

        occupations: dict[str, OnetOccupation] = {}
        for code in codes:
            occupation = OnetOccupation(
                onet_soc_code=code,
                title=f"O*NET occupation {code}",
                release_version=release_version,
                release_date=release_date,
                imported_at=imported_at,
            )
            db.session.add(occupation)
            occupations[code] = occupation
        db.session.flush()

        skill_values: list[dict[str, Any]] = []
        for row in skill_rows:
            code = value(row, "O*NET-SOC Code", "SOC Code", "onet_soc_code")
            occupation = occupations.get(code)
            if occupation is None:
                continue
            skill_values.append({"occupation_id": occupation.id, "element_id": value(row, "Element ID", "element_id"), "name": value(row, "Element Name", "name"), "scale_id": value(row, "Scale ID", "scale_id"), "value": number(value(row, "Data Value", "value")), "release_version": release_version, "imported_at": imported_at})
        insert_batches(OnetSkill, skill_values)

        interest_values: list[dict[str, Any]] = []
        for row in interest_rows:
            code = value(row, "O*NET-SOC Code", "SOC Code", "onet_soc_code")
            occupation = occupations.get(code)
            if occupation is None or value(row, "Scale ID", "scale_id") != "OI":
                continue
            interest_values.append({"occupation_id": occupation.id, "name": value(row, "Element Name", "name"), "score": number(value(row, "Data Value", "score")), "release_version": release_version, "imported_at": imported_at})
        insert_batches(OnetInterest, interest_values)

        task_values: list[dict[str, Any]] = []
        for row in task_rows:
            code = value(row, "O*NET-SOC Code", "SOC Code", "onet_soc_code")
            occupation = occupations.get(code)
            if occupation is not None:
                task_values.append({"occupation_id": occupation.id, "task_id": value(row, "Task ID", "Element ID", "task_id"), "statement": value(row, "Task", "Task Statement", "statement", "Description"), "release_version": release_version, "imported_at": imported_at})
        insert_batches(OnetTask, task_values)

        technology_values: list[dict[str, Any]] = []
        for row in technology_rows:
            code = value(row, "O*NET-SOC Code", "SOC Code", "onet_soc_code")
            occupation = occupations.get(code)
            if occupation is not None:
                technology_values.append({"occupation_id": occupation.id, "name": value(row, "Technology", "Technology Name", "Name", "name"), "category": value(row, "Category", "Technology Category", "category"), "release_version": release_version, "imported_at": imported_at})
        insert_batches(OnetTechnology, technology_values)

        db.session.commit()

    return {
        "release_version": release_version,
        "release_date": release_date,
        "occupations": len(codes),
        "skills": len(skill_rows),
        "interests": sum(1 for row in interest_rows if value(row, "Scale ID", "scale_id") == "OI"),
        "tasks": len(task_rows),
        "technologies": len(technology_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotently import available O*NET CSV datasets.")
    parser.add_argument("--release-version", default=DEFAULT_RELEASE)
    parser.add_argument("--release-date", default=DEFAULT_RELEASE_DATE)
    args = parser.parse_args()
    print(import_onet(args.release_version, args.release_date))


if __name__ == "__main__":
    main()
