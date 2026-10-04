#!/usr/bin/env python3
"""Shared helpers for raw-to-normalized tables. Does not train or invent labels."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

csv.field_size_limit(sys.maxsize)

BASE_DIR = Path(__file__).resolve().parents[2]
TRANSFORMATION_VERSION = "norm-v1.0-esco-careercorpus"
NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
ESCO_URI_PREFIX = "http://data.europa.eu/esco/"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n+", " | ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_esco_uri(value: str) -> bool:
    return value.startswith(ESCO_URI_PREFIX) and len(value) > len(ESCO_URI_PREFIX)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def missing_counts(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, int]:
    counts = {field: 0 for field in fields}
    for row in rows:
        for field in fields:
            if not str(row.get(field, "")).strip():
                counts[field] += 1
    return counts


def duplicate_counts(values: list[str]) -> dict[str, int]:
    counter = Counter(value for value in values if value)
    duplicated = {key: count for key, count in counter.items() if count > 1}
    return {
        "duplicate_identifier_values": len(duplicated),
        "duplicate_identifier_row_extra": sum(count - 1 for count in duplicated.values()),
    }


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = []
        for row in reader:
            rows.append({key: (value if value is not None else "") for key, value in row.items()})
    return fieldnames, rows


def _column_index(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + (ord(character.upper()) - 64)
    return index - 1


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.get("t")
    value_el = cell.find(f"{NS_MAIN}v")
    inline = cell.find(f"{NS_MAIN}is")
    if cell_type == "s" and value_el is not None and value_el.text is not None:
        return shared[int(value_el.text)]
    if cell_type == "inlineStr" and inline is not None:
        return "".join(node.text or "" for node in inline.iter(f"{NS_MAIN}t"))
    if value_el is None or value_el.text is None:
        return ""
    text = value_el.text
    if re.fullmatch(r"-?\d+\.0", text):
        return text[:-2]
    if re.fullmatch(r"-?\d+\.\d+E[+-]?\d+", text, flags=re.I):
        number = float(text)
        if number.is_integer():
            return str(int(number))
        return format(number, "f").rstrip("0").rstrip(".")
    return text


def inspect_xlsx(path: Path) -> list[dict[str, Any]]:
    sheets: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.get("Id"): rel.get("Target") for rel in rels}
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{NS_MAIN}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{NS_MAIN}t")))
        for sheet_el in workbook.findall(f"{NS_MAIN}sheets/{NS_MAIN}sheet"):
            name = sheet_el.get("name") or ""
            target = rid_to_target[sheet_el.get(NS_REL + "id")]
            xml_path = target.lstrip("/")
            if not xml_path.startswith("xl/"):
                xml_path = "xl/" + xml_path
            xml = ET.fromstring(archive.read(xml_path))
            xml_rows = xml.findall(f"{NS_MAIN}sheetData/{NS_MAIN}row")
            table: list[list[str]] = []
            for xml_row in xml_rows:
                cells = xml_row.findall(f"{NS_MAIN}c")
                values: dict[int, str] = {}
                for cell in cells:
                    ref = cell.get("r") or "A1"
                    values[_column_index(ref)] = _cell_value(cell, shared)
                if not values:
                    table.append([])
                    continue
                width = max(values) + 1
                table.append([values.get(index, "") for index in range(width)])
            header = table[0] if table else []
            data = table[1:] if len(table) > 1 else []
            sheets.append(
                {
                    "name": name,
                    "path": xml_path,
                    "header": header,
                    "data_rows": data,
                    "xml_row_count": len(xml_rows),
                }
            )
    return sheets


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)
