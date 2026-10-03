"""
Prayash — Upload Services
==========================
Secure, validated file handling for the career AI assistant.

Responsibilities:
    - Accept only whitelisted extensions (PDF/DOCX/TXT/CSV/XLSX/PNG/JPG/JPEG)
    - Enforce the 20 MB size ceiling
    - Validate MIME type on the backend (belt-and-braces with the frontend)
    - Store files under a UUID-prefixed, ``secure_filename``-sanitised name
    - Extract readable text from documents (PDF/DOCX/TXT/CSV/XLSX) and mark
      images for later OCR / vision handling
    - Persist metadata in the ``UploadedFile`` model and clean up disk files
      when an upload is removed

Uploads are restricted to authenticated users at the route layer
(``@login_required`` in ``routes/upload.py``).
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from flask import current_app
from werkzeug.utils import secure_filename

from extensions import db
from models.upload import UploadedFile

log = logging.getLogger("prayash.upload")

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}

# Expected MIME type prefixes per extension (used for backend validation).
_MIME_PREFIX: dict[str, tuple[str, ...]] = {
    "pdf": ("application/pdf",),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    ),
    "txt": ("text/",),
    "csv": ("text/", "application/csv", "application/vnd.ms-excel", "text/csv"),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
        "application/vnd.ms-excel",
    ),
    "png": ("image/png",),
    "jpg": ("image/jpeg",),
    "jpeg": ("image/jpeg",),
}


def allowed_extensions() -> set[str]:
    """Return the set of extensions the chatbot accepts (from config)."""
    allowed = current_app.config.get("CHAT_ALLOWED_EXTENSIONS") or {}
    return set(allowed.keys())


def upload_directory() -> Path:
    """Return the configured upload directory (created on demand)."""
    path = Path(current_app.config.get("CHAT_UPLOAD_DIR", "uploads"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _extension_of(filename: str) -> str:
    """Return the lowercased extension of a filename ('' if none)."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _validate_extension(filename: str, ext: str) -> tuple[bool, str]:
    if ext not in allowed_extensions():
        allowed = ", ".join(sorted(allowed_extensions())) or "PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, JPEG"
        return False, f"Unsupported file type. Please attach one of: {allowed}."
    return True, ""


def _validate_mime(ext: str, mimetype: str) -> bool:
    """Best-effort MIME validation. Tolerant: a missing/odd MIME only blocks
    when it clearly disagrees with the extension."""
    mimetype = (mimetype or "").lower()
    if not mimetype:
        return True
    prefixes = _MIME_PREFIX.get(ext)
    if not prefixes:
        return True
    return any(mimetype.startswith(prefix) for prefix in prefixes)


def _validate_size(size: int) -> tuple[bool, str]:
    limit = int(current_app.config.get("MAX_UPLOAD_SIZE", MAX_UPLOAD_SIZE))
    if size <= 0:
        return False, "The uploaded file is empty."
    if size > limit:
        return False, "File is too large (max 20 MB). Please choose a smaller file."
    return True, ""


def validate_upload(filename: str, size: int, mimetype: str) -> tuple[bool, str]:
    """Validate an upload's extension, size and MIME type. Returns
    ``(ok, error_message)``."""
    filename = (filename or "").strip()
    if not filename:
        return False, "Please attach a file."
    ext = _extension_of(filename)
    ok, error = _validate_extension(filename, ext)
    if not ok:
        return False, error
    ok, error = _validate_size(size)
    if not ok:
        return False, error
    if not _validate_mime(ext, mimetype):
        return False, "File content does not match its extension. Upload rejected for security."
    return True, ""


def _store_file(data: bytes, filename: str, ext: str) -> str:
    """Persist the bytes to the uploads dir with a UUID-prefixed safe name.
    Returns the stored filename."""
    safe_base = secure_filename(filename) or "upload"
    stored_name = f"{uuid.uuid4().hex}_{safe_base}"
    if "." in safe_base and not safe_base.lower().endswith(f".{ext}"):
        # Ensure the stored file keeps its true extension for later parsing
        stored_name = f"{uuid.uuid4().hex}_{Path(safe_base).stem}.{ext}"
    (upload_directory() / stored_name).write_bytes(data)
    log.info("Saved chat attachment: %s", stored_name)
    return stored_name


class _FileLike:
    """Minimal wrapper so ``resume_parser.extract_resume_text`` can read bytes
    the way it reads a Flask ``FileStorage``."""

    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self.stream = io.BytesIO(data)

    def read(self) -> bytes:
        self.stream.seek(0)
        return self.stream.read()


# ── Document text extraction ─────────────────────────────────────────

def _extract_document_text(filename: str, data: bytes) -> str:
    """Extract plain text from PDF/DOCX/TXT using the existing robust parser."""
    from resume_parser import extract_resume_text

    return extract_resume_text(_FileLike(filename, data))


def _extract_csv_text(data: bytes) -> str:
    """Convert a CSV file into readable text."""
    text = data.decode("utf-8", errors="replace")
    if re.search(r"[,;\t|]", text):
        try:
            import pandas as pd

            frame = pd.read_csv(io.BytesIO(data), sep=None, engine="python")
            return frame.to_string(index=False)
        except Exception:
            log.debug("CSV table conversion failed; returning raw text")
    return text


def _extract_xlsx_text(data: bytes) -> str:
    """Convert an Excel workbook into readable text (one block per sheet)."""
    import pandas as pd

    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
    parts: list[str] = []
    for sheet_name, frame in sheets.items():
        parts.append(f"Sheet: {sheet_name}")
        parts.append(frame.to_string(index=False))
    return "\n\n".join(parts)


def _image_metadata(data: bytes, filename: str) -> tuple[int, int]:
    """Return (width, height) of an image, falling back to (0, 0)."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            return img.size
    except Exception:
        log.debug("Could not read image dimensions for %s", filename)
        return 0, 0


def extract_text(filename: str, data: bytes, ext: str) -> tuple[str, bool]:
    """Extract readable text from an upload.

    Returns ``(text, is_image)``. Images carry no extractable text — the
    return value describes the image and flags ``is_image=True`` so the
    caller can route it to an OCR / vision model later.
    """
    if ext in IMAGE_EXTENSIONS:
        width, height = _image_metadata(data, filename)
        text = (
            f"Attached image: {filename} ({width}x{height} pixels). "
            "The user shared an image, so no text could be extracted locally. "
            "If asked, acknowledge the image and offer career/resume guidance."
        )
        return text, True

    if ext == "xlsx":
        text = _extract_xlsx_text(data)
    elif ext == "csv":
        text = _extract_csv_text(data)
    else:
        text = _extract_document_text(filename, data)

    text = (text or "").strip()
    return text, False


def save_upload(user_id: int, upload_file, conversation_id: int | None = None) -> tuple[UploadedFile | None, str]:
    """Validate and persist an uploaded file.

    Returns ``(record, error_message)`` where ``record`` is ``None`` when the
    upload was rejected.
    """
    filename = (upload_file.filename or "").strip()
    # ``content_length`` is unreliable (0/None from some clients and proxies),
    # so read the bytes first and validate against the REAL size.
    data = upload_file.read()
    size = len(data)
    ok, error = validate_upload(filename, size, upload_file.mimetype)
    if not ok:
        return None, error

    ext = _extension_of(filename)
    stored_name = _store_file(data, filename, ext)
    text, is_image = extract_text(filename, data, ext)

    record = UploadedFile(
        user_id=user_id,
        conversation_id=conversation_id,
        original_name=filename,
        stored_name=stored_name,
        file_type="image" if is_image else ext,
        mime_type=(upload_file.mimetype or "").lower(),
        size_bytes=size,
        extracted_text=text,
        is_image=is_image,
    )
    db.session.add(record)
    db.session.commit()
    log.info("Recorded chat attachment #%s (%s)", record.id, filename)
    return record, ""


def get_upload(upload_id: int, user_id: int) -> UploadedFile | None:
    """Fetch an upload owned by *user_id* (ownership enforced)."""
    return UploadedFile.query.filter_by(id=upload_id, user_id=user_id).first()


def delete_upload(upload_id: int, user_id: int) -> bool:
    """Remove an upload record and its file from disk. Returns True on success."""
    record = get_upload(upload_id, user_id)
    if record is None:
        return False
    try:
        path = upload_directory() / record.stored_name
        if path.exists():
            path.unlink()
    except OSError:
        log.warning("Could not delete file for upload #%s", upload_id)
    db.session.delete(record)
    db.session.commit()
    return True


def file_to_dict(record: UploadedFile) -> dict[str, Any]:
    """Serialise an UploadedFile for the JSON API."""
    return {
        "id": record.id,
        "conversation_id": record.conversation_id,
        "filename": record.original_name,
        "file_type": record.file_type,
        "is_image": record.is_image,
        "size_bytes": record.size_bytes,
        "char_count": len(record.extracted_text or ""),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def context_from_files(files: list[UploadedFile], max_chars: int = 15000) -> str:
    """Concatenate extracted text of a set of files for LLM context."""
    parts: list[str] = []
    used = 0
    for f in files:
        text = (f.extracted_text or "").strip()
        if not text:
            continue
        if f.is_image:
            continue  # images carry no useful text; skip in context
        remaining = max_chars - used
        if remaining <= 0:
            break
        parts.append(f"[Document: {f.original_name}]\n{text[:remaining]}")
        used += len(text)
    return "\n\n".join(parts)
