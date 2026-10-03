"""
Prayash — Upload Models
========================
Tracks files attached to the career AI assistant.

Every uploaded file is stored on disk under a UUID-prefixed, sanitised name
(see ``services/upload_service.py``) while this model records its metadata,
owner and the extracted text that is fed to the AI as context.

Model:
    - UploadedFile  metadata for a securely stored chat attachment
"""

from __future__ import annotations

from extensions import db
from models import utc_now


class UploadedFile(db.Model):
    """A securely stored file attached to a chat conversation."""

    __tablename__ = "chat_uploaded_files"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("chat_conversations.id"), nullable=True, index=True
    )
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)  # pdf | docx | ... | image
    mime_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    extracted_text = db.Column(db.Text, nullable=True)
    is_image = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<UploadedFile {self.id} {self.original_name}>"
