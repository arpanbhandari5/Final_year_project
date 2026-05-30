from __future__ import annotations

from io import BytesIO
from typing import Any

try:
    from docx import Document
except Exception:  # pragma: no cover - optional dependency during bootstrap
    Document = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency during bootstrap
    PdfReader = None

import numpy as np
import re


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.lower() == "nan" else text


def extract_resume_text(uploaded_file) -> str:
    filename = (uploaded_file.filename or "").lower()
    payload = uploaded_file.read()
    uploaded_file.stream.seek(0)

    if filename.endswith(".pdf") and PdfReader is not None:
        reader = PdfReader(BytesIO(payload))
        return _clean_text(" ".join(page.extract_text() or "" for page in reader.pages))

    if filename.endswith(".docx") and Document is not None:
        document = Document(BytesIO(payload))
        return _clean_text(" ".join(paragraph.text for paragraph in document.paragraphs))

    return _clean_text(payload.decode("utf-8", errors="ignore"))