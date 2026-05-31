from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def email(self) -> str:
        return self.username

    @property
    def is_admin_email(self) -> bool:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@prayash.local").strip().lower()
        return self.email.strip().lower() == admin_email or self.role == "admin"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Upload(db.Model):
    __tablename__ = "uploads"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False, default="text")
    mode = db.Column(db.String(20), nullable=False, default="standard")
    risk_score = db.Column(db.Float, nullable=False, default=0.0)
    risk_label = db.Column(db.String(20), nullable=False, default="Low")
    reasoning_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("uploads.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


def _default_admin_credentials() -> tuple[str, str]:
    username = os.environ.get("ADMIN_EMAIL", "admin@prayash.local")
    password = os.environ.get("ADMIN_PASSWORD", "prayash-admin")
    return username, password


def init_database(app) -> None:
    db.init_app(app)
    with app.app_context():
        db.create_all()
        seed_default_users()


def seed_default_users() -> None:
    admin_username, admin_password = _default_admin_credentials()
    admin_user = User.query.filter_by(username=admin_username).first()
    if admin_user is None:
        admin_user = User(username=admin_username, role="admin")
        admin_user.set_password(admin_password)
        db.session.add(admin_user)

    student_user = User.query.filter_by(username="student").first()
    if student_user is None:
        student_user = User(username="student", role="student")
        student_user.set_password("student")
        db.session.add(student_user)

    db.session.commit()


def authenticate_admin(username: str, password: str) -> User | None:
    user = User.query.filter_by(username=username, role="admin", is_active=True).first()
    if user and user.check_password(password):
        return user
    return None


def authenticate_user(email: str, password: str) -> User | None:
    user = User.query.filter_by(username=email.strip().lower(), is_active=True).first()
    if user and user.check_password(password):
        return user
    return None


def get_user_by_email(email: str) -> User | None:
    return User.query.filter_by(username=email.strip().lower()).first()


def create_user(email: str, password: str, role: str = "student") -> User:
    user = User(username=email.strip().lower(), role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def record_upload(*, filename: str, file_type: str, mode: str, risk_score: float, risk_label: str, reasoning: dict[str, Any], user_id: int | None = None) -> Upload | None:
    try:
        upload = Upload(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            mode=mode,
            risk_score=float(risk_score),
            risk_label=risk_label,
            reasoning_json=__import__("json").dumps(reasoning, ensure_ascii=False),
        )
        db.session.add(upload)
        db.session.commit()
        return upload
    except Exception:
        db.session.rollback()
        return None


def record_feedback(*, message: str, rating: int | None = None, upload_id: int | None = None, user_id: int | None = None) -> Feedback | None:
    try:
        feedback = Feedback(user_id=user_id, upload_id=upload_id, rating=rating, message=message)
        db.session.add(feedback)
        db.session.commit()
        return feedback
    except Exception:
        db.session.rollback()
        return None


def dashboard_metrics() -> dict[str, Any]:
    uploads = Upload.query.order_by(Upload.created_at.desc()).all()
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).limit(5).all()
    total_uploads = len(uploads)
    mode_counts = {"standard": 0, "advanced": 0}
    risk_buckets = {"low": 0, "moderate": 0, "elevated": 0}
    average_risk = 0.0

    for upload in uploads:
        mode_counts[upload.mode if upload.mode in mode_counts else "standard"] += 1
        if upload.risk_score < 0.35:
            risk_buckets["low"] += 1
        elif upload.risk_score < 0.7:
            risk_buckets["moderate"] += 1
        else:
            risk_buckets["elevated"] += 1
        average_risk += upload.risk_score

    if total_uploads:
        average_risk /= total_uploads

    return {
        "total_uploads": total_uploads,
        "average_risk": round(average_risk, 3),
        "mode_counts": mode_counts,
        "risk_buckets": risk_buckets,
        "recent_uploads": uploads[:8],
        "recent_feedback": feedback_items,
    }
