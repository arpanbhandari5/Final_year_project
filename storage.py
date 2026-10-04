from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from flask_login import UserMixin

log = logging.getLogger("prayash.storage")
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from utils import RISK_LOW, RISK_MODERATE


db = SQLAlchemy()
mail = Mail()

# ── OTP Policy (single source of truth) ──────────────────────────────
OTP_LENGTH = 6
OTP_MAX_ATTEMPTS = 5
OTP_EXPIRY_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60


def _utc_now() -> datetime:
    """Naive UTC datetime, consistent with what SQLite stores/returns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_naive_utc(value: datetime | None) -> datetime | None:
    """Normalise a possibly timezone-aware datetime to naive UTC."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)

    @property
    def is_admin_email(self) -> bool:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@prayash.local").strip().lower()
        return self.email.strip().lower() == admin_email or self.role == "admin"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def touch_last_login(self) -> None:
        self.last_login = datetime.now(timezone.utc)
        db.session.commit()


class CareerProfile(db.Model):
    __tablename__ = "career_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    intent = db.Column(db.String(80), nullable=False, default="")
    target_role = db.Column(db.String(160), nullable=False, default="")
    target_role_source = db.Column(db.String(24), nullable=False, default="user")
    confidence = db.Column(db.String(24), nullable=False, default="self-reported")
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class CareerGoal(db.Model):
    __tablename__ = "career_goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    target_role = db.Column(db.String(160), nullable=False, default="")
    alternative_roles_json = db.Column(db.Text, nullable=False, default="[]")
    geography = db.Column(db.String(120), nullable=False, default="")
    seniority = db.Column(db.String(60), nullable=False, default="")
    time_per_week = db.Column(db.Float, nullable=True)
    learning_budget = db.Column(db.Float, nullable=True)
    target_occupation_code = db.Column(db.String(16), nullable=False, default="")
    immediate_goal = db.Column(db.String(80), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class ResumeProfile(db.Model):
    __tablename__ = "resume_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    extracted_skills_json = db.Column(db.Text, nullable=False, default="[]")
    evidence_spans_json = db.Column(db.Text, nullable=False, default="[]")
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class ActionItem(db.Model):
    __tablename__ = "action_items"

    STATUSES = ("not_started", "in_progress", "completed", "needs_review")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    source_type = db.Column(db.String(40), nullable=False, default="skill_gap")
    source_id = db.Column(db.String(64), nullable=False, default="")
    action_type = db.Column(db.String(40), nullable=False, default="learn_skill")
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(24), nullable=False, default="not_started", index=True)
    priority = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)


class TargetJobMatch(db.Model):
    """User-owned pasted job description and last comparison payload. Not an application tracker."""

    __tablename__ = "target_job_matches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, default="")
    company = db.Column(db.String(160), nullable=False, default="")
    location = db.Column(db.String(160), nullable=False, default="")
    description_raw = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    evidence_source_type = db.Column(db.String(40), nullable=False, default="profile")
    evidence_source_key = db.Column(db.String(80), nullable=False, default="profile")
    evidence_source_label = db.Column(db.String(240), nullable=False, default="Current evidence profile")
    resume_version_id = db.Column(db.Integer, nullable=True)
    result_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now)


class JobPosting(db.Model):
    __tablename__ = "job_postings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(160), nullable=False, default="")
    description_raw = db.Column(db.Text, nullable=False)
    source_url = db.Column(db.String(1000), nullable=False, default="")
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_job_postings_user_hash"),
    )


class ResumeVersion(db.Model):
    __tablename__ = "resume_versions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    content_text = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now, index=True)


class AnalysisSnapshot(db.Model):
    __tablename__ = "analysis_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_postings.id"), nullable=False)
    resume_version_id = db.Column(db.Integer, db.ForeignKey("resume_versions.id"), nullable=False)
    snapshot_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    result_json = db.Column(db.Text, nullable=False, default="{}")
    comparison_timestamp = db.Column(db.DateTime, nullable=False, default=_utc_now, index=True)


class Application(db.Model):
    __tablename__ = "applications"

    STATUSES = ("Bookmarked", "Applying", "Applied", "Interviewing", "Accepted", "Rejected")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_postings.id"), nullable=False, index=True)
    resume_version_id = db.Column(db.Integer, db.ForeignKey("resume_versions.id"), nullable=True)
    analysis_snapshot_id = db.Column(db.Integer, db.ForeignKey("analysis_snapshots.id"), nullable=True)
    target_job_match_id = db.Column(db.Integer, nullable=True, index=True)
    status = db.Column(db.String(24), nullable=False, default="Bookmarked", index=True)
    follow_up_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "job_posting_id", name="uq_applications_user_job"),
    )


class OnetOccupation(db.Model):
    __tablename__ = "onet_occupations"

    id = db.Column(db.Integer, primary_key=True)
    onet_soc_code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    job_zone = db.Column(db.String(32), nullable=False, default="")
    release_version = db.Column(db.String(32), nullable=False, index=True)
    release_date = db.Column(db.String(16), nullable=False, default="2026")
    imported_at = db.Column(db.DateTime, nullable=False, default=_utc_now)


class OnetTask(db.Model):
    __tablename__ = "onet_tasks"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    task_id = db.Column(db.String(80), nullable=False, default="")
    statement = db.Column(db.Text, nullable=False)
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=_utc_now)


class OnetSkill(db.Model):
    __tablename__ = "onet_skills"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    element_id = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    scale_id = db.Column(db.String(16), nullable=False, default="")
    value = db.Column(db.Float, nullable=True)
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=_utc_now)


class OnetTechnology(db.Model):
    __tablename__ = "onet_technologies"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(120), nullable=False, default="")
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=_utc_now)


class OnetInterest(db.Model):
    __tablename__ = "onet_interests"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    score = db.Column(db.Float, nullable=True)
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=_utc_now)


class PartnershipRequest(db.Model):
    __tablename__ = "partnership_requests"

    id = db.Column(db.Integer, primary_key=True)
    organization = db.Column(db.String(160), nullable=False)
    contact_email = db.Column(db.String(255), nullable=False)
    use_case = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(24), nullable=False, default="new")
    notes = db.Column(db.Text, nullable=False, default="")
    response_message = db.Column(db.Text, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now, index=True)


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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("uploads.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class VerificationOTP(db.Model):
    """Stores OTP codes for email verification and password reset."""
    __tablename__ = "verification_otps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    otp = db.Column(db.String(10), nullable=False)
    purpose = db.Column(db.String(30), nullable=False, default="verify_email")  # verify_email | reset_password
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now)


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


def _default_admin_credentials() -> tuple[str, str]:
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@prayash.local")
    password = os.environ.get("ADMIN_PASSWORD", "prayash-admin")
    return admin_email, password


def init_database(app) -> None:
    _configure_mail(app)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _ensure_sqlite_workspace_columns()
        seed_default_users()


def seed_default_users() -> None:
    admin_email, admin_password = _default_admin_credentials()
    admin_user = User.query.filter_by(email=admin_email).first()
    if admin_user is None:
        admin_user = User(
            email=admin_email,
            username="admin",
            full_name="Prayash Admin",
            role="admin",
            email_verified=True,
        )
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
    else:
        # Ensure existing admin user has email verified
        admin_user.email_verified = True
        admin_user.role = "admin"

    student_user = User.query.filter_by(email="student@prayash.local").first()
    if student_user is None:
        student_user = User(
            email="student@prayash.local",
            username="student",
            full_name="Student User",
            role="student",
            email_verified=True,
        )
        student_user.set_password("Student@123")  # Stronger default password: meets all complexity rules
        db.session.add(student_user)

    db.session.commit()


def _ensure_sqlite_workspace_columns() -> None:
    if db.engine.dialect.name != "sqlite":
        return
    statements = {
        "career_goals": (
            ("target_occupation_code", "ALTER TABLE career_goals ADD COLUMN target_occupation_code VARCHAR(16) DEFAULT ''"),
            ("immediate_goal", "ALTER TABLE career_goals ADD COLUMN immediate_goal VARCHAR(80) DEFAULT ''"),
        ),
        "target_job_matches": (
            ("evidence_source_type", "ALTER TABLE target_job_matches ADD COLUMN evidence_source_type VARCHAR(40) DEFAULT 'profile'"),
            ("evidence_source_key", "ALTER TABLE target_job_matches ADD COLUMN evidence_source_key VARCHAR(80) DEFAULT 'profile'"),
            ("evidence_source_label", "ALTER TABLE target_job_matches ADD COLUMN evidence_source_label VARCHAR(240) DEFAULT 'Current evidence profile'"),
            ("resume_version_id", "ALTER TABLE target_job_matches ADD COLUMN resume_version_id INTEGER"),
        ),
        "applications": (
            ("target_job_match_id", "ALTER TABLE applications ADD COLUMN target_job_match_id INTEGER"),
        ),
    }
    with db.engine.begin() as conn:
        for table, columns in statements.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if not existing:
                continue
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(ddl))
        _dedupe_and_index_sqlite_applications(conn)


def _dedupe_and_index_sqlite_applications(conn) -> None:
    tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    if "job_postings" in tables:
        rows = conn.execute(text("SELECT id, user_id, content_hash FROM job_postings")).fetchall()
        keepers: dict[tuple[Any, Any], int] = {}
        extras: list[tuple[int, int]] = []
        for job_id, user_id, digest in rows:
            key = (user_id, digest)
            if key in keepers:
                extras.append((int(job_id), keepers[key]))
            else:
                keepers[key] = int(job_id)
        for extra_id, keeper_id in extras:
            if "applications" in tables:
                conn.execute(
                    text("UPDATE applications SET job_posting_id = :keeper WHERE job_posting_id = :extra"),
                    {"keeper": keeper_id, "extra": extra_id},
                )
            if "analysis_snapshots" in tables:
                conn.execute(
                    text("UPDATE analysis_snapshots SET job_posting_id = :keeper WHERE job_posting_id = :extra"),
                    {"keeper": keeper_id, "extra": extra_id},
                )
            conn.execute(text("DELETE FROM job_postings WHERE id = :extra"), {"extra": extra_id})
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_job_postings_user_hash ON job_postings (user_id, content_hash)"
        ))
    if "applications" in tables:
        conn.execute(text(
            """
            DELETE FROM applications
            WHERE id NOT IN (
                SELECT MIN(id) FROM applications GROUP BY user_id, job_posting_id
            )
            """
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_applications_user_job ON applications (user_id, job_posting_id)"
        ))


def authenticate_user(email_or_username: str, password: str) -> User | None:
    """Authenticate by email or username."""
    lookup = email_or_username.strip().lower()
    user = User.query.filter(
        (User.email == lookup) | (User.username == lookup),
        User.is_active.is_(True),
    ).first()
    if user and user.check_password(password):
        return user
    return None


def get_user_by_email(email: str) -> User | None:
    return User.query.filter_by(email=email.strip().lower()).first()


def get_user_by_username(username: str) -> User | None:
    return User.query.filter_by(username=username.strip().lower()).first()


def create_user(
    email: str,
    password: str,
    full_name: str | None = None,
    username: str | None = None,
    phone: str | None = None,
    role: str = "student",
) -> User:
    user = User(
        email=email.strip().lower(),
        username=username.strip().lower() if username else None,
        full_name=full_name.strip() if full_name else None,
        phone=phone.strip() if phone else None,
        role=role,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def create_oauth_user(email: str, provider: str) -> User:
    existing = get_user_by_email(email)
    if existing:
        return existing

    random_password = secrets.token_urlsafe(32)
    # Derive a unique username from the email prefix
    base_username = email.split("@")[0][:60]
    username = base_username
    suffix = 1
    while get_user_by_username(username):
        username = f"{base_username}{suffix}"
        suffix += 1

    user = User(
        email=email.strip().lower(),
        username=username,
        full_name=email.split("@")[0],
        role="student",
    )
    user.set_password(random_password)
    db.session.add(user)
    db.session.commit()
    log.info("Created new user from %s OAuth: %s", provider, email)
    return user


# ── Email Service (Flask-Mail + SMTP fallback + Console Logger) ──

# MAIL_* settings take precedence over the legacy SMTP_* settings so the
# transition is seamless. Nothing is hardcoded — everything comes from env.
_mail_server = os.environ.get("MAIL_SERVER") or os.environ.get("SMTP_HOST") or "smtp.gmail.com"
_mail_port = int(os.environ.get("MAIL_PORT") or os.environ.get("SMTP_PORT") or "587")
_mail_use_tls = (os.environ.get("MAIL_USE_TLS") or os.environ.get("SMTP_USE_TLS") or "true").lower() in ("1", "true", "yes", "on")
_mail_use_ssl = (os.environ.get("MAIL_USE_SSL") or os.environ.get("SMTP_USE_SSL") or "false").lower() in ("1", "true", "yes", "on")
_mail_username = os.environ.get("MAIL_USERNAME") or os.environ.get("SMTP_USERNAME") or ""
_mail_password = os.environ.get("MAIL_PASSWORD") or os.environ.get("SMTP_PASSWORD") or ""
_mail_from_name = os.environ.get("MAIL_FROM_NAME") or os.environ.get("SMTP_FROM_NAME") or "Prayash"


def _resolve_from_email(from_email: str, username: str) -> str:
    """Resolve the sender address for SMTP.

    Gmail (and most providers) only allow sending FROM the authenticated
    account. If no explicit From is configured (or it's still a placeholder
    domain), fall back to the authenticated username so delivery never fails.
    """
    cleaned = (from_email or "").strip()
    if cleaned and not cleaned.endswith(("prayash.local", "localhost", "example.com")):
        return cleaned
    return username


_mail_from_email = _resolve_from_email(
    os.environ.get("MAIL_FROM_EMAIL") or os.environ.get("SMTP_FROM_EMAIL") or "",
    _mail_username,
)

_MAIL_CONFIG = {
    "server": _mail_server,
    "port": _mail_port,
    "use_tls": _mail_use_tls,
    "use_ssl": _mail_use_ssl,
    "username": _mail_username,
    "password": _mail_password,
    "from_email": _mail_from_email,
    "from_name": _mail_from_name,
}

_SMTP_CONFIG = {
    "host": _MAIL_CONFIG["server"],
    "port": _MAIL_CONFIG["port"],
    "username": _MAIL_CONFIG["username"],
    "password": _MAIL_CONFIG["password"],
    "from_email": _MAIL_CONFIG["from_email"],
    "from_name": _MAIL_CONFIG["from_name"],
    "use_tls": _MAIL_CONFIG["use_tls"],
}


def _configure_mail(app) -> None:
    """Wire Flask-Mail up to the environment-based MAIL_* configuration."""
    app.config.update(
        MAIL_SERVER=_MAIL_CONFIG["server"],
        MAIL_PORT=_MAIL_CONFIG["port"],
        MAIL_USE_TLS=_MAIL_CONFIG["use_tls"],
        MAIL_USE_SSL=_MAIL_CONFIG["use_ssl"],
        MAIL_USERNAME=_MAIL_CONFIG["username"],
        MAIL_PASSWORD=_MAIL_CONFIG["password"],
        MAIL_DEFAULT_SENDER=(_MAIL_CONFIG["from_name"], _MAIL_CONFIG["from_email"]),
    )
    mail.init_app(app)

    if not (_MAIL_CONFIG["username"] and _MAIL_CONFIG["password"]):
        log.warning(
            "Email sending is DISABLED: MAIL_USERNAME/MAIL_PASSWORD are not set. "
            "OTP codes will only be printed to the console. Fill them in .env "
            "(Gmail App Password) to deliver real emails."
        )
    else:
        security = "TLS" if _MAIL_CONFIG["use_tls"] else "SSL" if _MAIL_CONFIG["use_ssl"] else "plain"
        log.info(
            "Email transport ready: %s:%s (%s), from=%s",
            _MAIL_CONFIG["server"],
            _MAIL_CONFIG["port"],
            security,
            _MAIL_CONFIG["from_email"],
        )


def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    """Send an email. Uses Flask-Mail (SMTP) when credentials are configured,
    otherwise falls back to the standard-library smtplib, and finally to the
    console logger. Returns True if the message was 'sent' (logged or delivered)
    so the caller never leaks whether an account exists."""
    # Log delivery metadata. Production logs never include the message body,
    # because OTP and reset emails contain one-time secrets.
    production_logs = os.environ.get("FLASK_ENV", "development") == "production"
    log.info("EMAIL TO: %s", to_email)
    log.info("SUBJECT: %s", subject)
    if production_logs:
        log.info("EMAIL BODY: redacted")
    else:
        log.info("BODY:\n%s\n", html_body if not text_body else text_body)

    # 1) Flask-Mail (preferred transport)
    if _MAIL_CONFIG["username"] and _MAIL_CONFIG["password"]:
        try:
            msg = Message(subject, recipients=[to_email])
            msg.sender = (_MAIL_CONFIG["from_name"], _MAIL_CONFIG["from_email"])
            if text_body:
                msg.body = text_body
            msg.html = html_body
            mail.send(msg)
            log.info("Email sent via Flask-Mail to %s", to_email)
            return True
        except Exception as exc:
            log.warning("Flask-Mail send failed (trying smtplib fallback): %s", exc)

    # 2) Standard-library smtplib fallback
    if _SMTP_CONFIG["username"] and _SMTP_CONFIG["password"]:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{_SMTP_CONFIG['from_name']} <{_SMTP_CONFIG['from_email']}>"
            msg["To"] = to_email

            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(_SMTP_CONFIG["host"], _SMTP_CONFIG["port"]) as server:
                if _SMTP_CONFIG["use_tls"]:
                    server.starttls()
                server.login(_SMTP_CONFIG["username"], _SMTP_CONFIG["password"])
                server.sendmail(_SMTP_CONFIG["from_email"], to_email, msg.as_string())
            log.info("Email sent via smtplib to %s", to_email)
            return True
        except Exception as exc:
            log.warning("SMTP send failed (falling back to console): %s", exc)

    return True


def _generate_otp(length: int = OTP_LENGTH) -> str:
    """Generate a numeric OTP of the given length using a secure PRNG."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def create_otp(user: User, purpose: str = "verify_email", ttl_minutes: int = OTP_EXPIRY_MINUTES) -> VerificationOTP:
    """Create a new OTP for email verification or password reset.
    Invalidates any previous unused OTPs for the same user+purpose so only
    the most recent code can ever be used (one-time use, no replay)."""
    # Invalidate old OTPs
    old_otps = VerificationOTP.query.filter_by(
        user_id=user.id, purpose=purpose, used=False
    ).all()
    for old in old_otps:
        old.used = True

    otp_code = _generate_otp(OTP_LENGTH)
    now = _utc_now()
    expires_at = now + timedelta(minutes=ttl_minutes)

    otp = VerificationOTP(
        user_id=user.id,
        email=user.email,
        otp=otp_code,
        purpose=purpose,
        expires_at=expires_at,
        created_at=now,
    )
    db.session.add(otp)
    db.session.commit()
    return otp


def get_active_otp(user: User, purpose: str = "verify_email") -> VerificationOTP | None:
    """Return the most recent unused, non-expired OTP for user+purpose."""
    now = _utc_now()
    return (
        VerificationOTP.query.filter_by(
            user_id=user.id, purpose=purpose, used=False
        )
        .filter(VerificationOTP.expires_at > now)
        .order_by(VerificationOTP.id.desc())
        .first()
    )


def check_otp(user: User, otp_code: str, purpose: str = "verify_email") -> str:
    """Verify an OTP and return a machine-readable status string.

    Return values:
      - ``'valid'``         code matched; the OTP is now consumed
      - ``'invalid'``       code did not match (attempts consumed)
      - ``'expired'``       code has expired — request a new one
      - ``'used'``          code was already used or superseded
      - ``'max_attempts'``  too many failed attempts — code is locked
    """
    now = _utc_now()
    record = get_active_otp(user, purpose)

    if record:
        if record.otp == otp_code:
            record.used = True
            db.session.commit()
            return "valid"
        # Wrong code — consume an attempt, lock the code after OTP_MAX_ATTEMPTS
        record.attempts += 1
        exceeded = record.attempts >= OTP_MAX_ATTEMPTS
        if exceeded:
            record.used = True
        db.session.commit()
        return "max_attempts" if exceeded else "invalid"

    # No live OTP — explain why so the UI can guide the user
    latest = (
        VerificationOTP.query.filter_by(user_id=user.id, purpose=purpose)
        .order_by(VerificationOTP.id.desc())
        .first()
    )
    if latest is not None:
        if latest.used:
            return "used"
        latest_expires = _as_naive_utc(latest.expires_at)
        if latest_expires is not None and latest_expires <= now:
            return "expired"
    return "invalid"


def verify_otp(user: User, otp_code: str, purpose: str = "verify_email") -> bool:
    """Verify an OTP code for the given user and purpose.
    Returns True if valid, False otherwise.
    Also invalidates the OTP after successful verification."""
    return check_otp(user, otp_code, purpose) == "valid"


def get_otp_attempts_remaining(user: User, purpose: str = "verify_email") -> int:
    """Return how many verification attempts remain for the active OTP."""
    record = get_active_otp(user, purpose)
    if record is None:
        return 0
    return max(0, OTP_MAX_ATTEMPTS - record.attempts)


def otp_cooldown_remaining(user: User, purpose: str = "verify_email") -> int:
    """Seconds remaining before a new OTP may be requested for this user+purpose."""
    record = (
        VerificationOTP.query.filter_by(user_id=user.id, purpose=purpose)
        .order_by(VerificationOTP.id.desc())
        .first()
    )
    if record is None:
        return 0
    created = _as_naive_utc(record.created_at)
    if created is None:
        return 0
    elapsed = (_utc_now() - created).total_seconds()
    return max(0, int(OTP_RESEND_COOLDOWN_SECONDS - elapsed))


def invalidate_user_otps(user: User, purpose: str = "verify_email") -> None:
    """Mark every unused OTP for user+purpose as used so none can be replayed."""
    records = VerificationOTP.query.filter_by(
        user_id=user.id, purpose=purpose, used=False
    ).all()
    for rec in records:
        rec.used = True
    if records:
        db.session.commit()


def mark_email_verified(user: User) -> None:
    """Mark user's email as verified."""
    user.email_verified = True
    db.session.commit()


def create_password_reset_token(user: User) -> PasswordResetToken:
    from datetime import timedelta
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    reset = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    db.session.add(reset)
    db.session.commit()
    return reset


def verify_reset_token(token: str) -> User | None:
    """Look up a user by a valid, unused, non-expired reset token.
    Does NOT mark the token as used so the same token can be
    verified on GET and later consumed on POST."""
    now = datetime.now(timezone.utc)
    record = PasswordResetToken.query.filter_by(
        token=token, used=False
    ).filter(PasswordResetToken.expires_at > now).first()
    if record:
        return User.query.get(record.user_id)
    return None


def consume_reset_token(token: str) -> bool:
    """Mark a reset token as used so it cannot be replayed.
    Returns True if the token was found and consumed."""
    now = datetime.now(timezone.utc)
    record = PasswordResetToken.query.filter_by(
        token=token, used=False
    ).filter(PasswordResetToken.expires_at > now).first()
    if record:
        record.used = True
        db.session.commit()
        return True
    return False


def update_user_password(user: User, new_password: str) -> None:
    user.set_password(new_password)
    db.session.commit()


def get_career_profile(user_id: int) -> CareerProfile | None:
    return CareerProfile.query.filter_by(user_id=user_id).first()


def save_career_profile(*, user_id: int, intent: str, target_role: str) -> CareerProfile:
    profile = get_career_profile(user_id)
    if profile is None:
        profile = CareerProfile(user_id=user_id)
        db.session.add(profile)
    profile.intent = intent
    profile.target_role = target_role
    profile.target_role_source = "user"
    profile.confidence = "self-reported"
    db.session.commit()
    return profile


def _json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def career_goal_payload(goal: CareerGoal | None) -> dict[str, Any] | None:
    if goal is None:
        return None
    return {
        "id": goal.id,
        "target_role": goal.target_role,
        "target_occupation_code": goal.target_occupation_code or "",
        "alternative_roles": _json_list(goal.alternative_roles_json),
        "geography": goal.geography,
        "seniority": goal.seniority,
        "time_per_week": goal.time_per_week,
        "learning_budget": goal.learning_budget,
        "immediate_goal": goal.immediate_goal or "",
    }


def get_career_goal(user_id: int) -> CareerGoal | None:
    return CareerGoal.query.filter_by(user_id=user_id).first()


def save_career_goal(*, user_id: int, values: dict[str, Any]) -> CareerGoal:
    goal = get_career_goal(user_id)
    if goal is None:
        goal = CareerGoal(user_id=user_id)
        db.session.add(goal)
    goal.target_role = values["target_role"]
    goal.alternative_roles_json = json.dumps(values["alternative_roles"], ensure_ascii=False)
    goal.geography = values["geography"]
    goal.seniority = values["seniority"]
    goal.time_per_week = values["time_per_week"]
    goal.learning_budget = values["learning_budget"]
    goal.target_occupation_code = values.get("target_occupation_code") or ""
    goal.immediate_goal = values.get("immediate_goal") or ""
    db.session.commit()
    return goal


def delete_career_goal(user_id: int) -> bool:
    goal = get_career_goal(user_id)
    if goal is None:
        return False
    db.session.delete(goal)
    db.session.commit()
    return True


def _new_resume_profile(user_id: int) -> ResumeProfile:
    profile = ResumeProfile(user_id=user_id, extracted_skills_json="[]", evidence_spans_json="[]", confidence=0.0)
    db.session.add(profile)
    db.session.commit()
    return profile


def get_resume_profile(user_id: int, *, create: bool = False) -> ResumeProfile | None:
    profile = ResumeProfile.query.filter_by(user_id=user_id).first()
    return _new_resume_profile(user_id) if profile is None and create else profile


def resume_profile_payload(profile: ResumeProfile | None) -> dict[str, Any]:
    if profile is None:
        return {"extracted_skills": [], "evidence_spans": [], "confidence": 0.0}
    return {
        "id": profile.id,
        "extracted_skills": _json_list(profile.extracted_skills_json),
        "evidence_spans": _json_list(profile.evidence_spans_json),
        "confidence": profile.confidence,
    }


def correct_resume_skill(
    *,
    user_id: int,
    action: str,
    skill_id: str | None,
    skill: str | None,
    evidence_span: str | None,
    confidence: float | None,
    status: str | None = None,
) -> ResumeProfile | None:
    profile = get_resume_profile(user_id, create=True)
    if profile is None:
        return None
    skills = _json_list(profile.extracted_skills_json)
    index = next((position for position, item in enumerate(skills) if str(item.get("id")) == skill_id), None)
    if action == "add":
        if not skill:
            return None
        skills.append({
            "id": uuid.uuid4().hex,
            "skill": skill,
            "evidence_span": evidence_span or "",
            "confidence": confidence if confidence is not None else 0.5,
            "status": "user-added",
            "source_section": "user",
        })
    elif action == "edit":
        if index is None or not skill:
            return None
        updates = {
            "skill": skill,
            "evidence_span": evidence_span if evidence_span is not None else skills[index].get("evidence_span", ""),
            "confidence": confidence if confidence is not None else skills[index].get("confidence", 0.5),
        }
        if status:
            updates["status"] = status
        skills[index].update(updates)
    elif action == "delete":
        if index is None:
            return None
        skills.pop(index)
    else:
        return None
    profile.extracted_skills_json = json.dumps(skills, ensure_ascii=False)
    profile.confidence = round(sum(float(item.get("confidence", 0.0)) for item in skills) / len(skills), 3) if skills else 0.0
    db.session.commit()
    return profile


def replace_resume_skills(user_id: int, skills: list[dict[str, Any]]) -> ResumeProfile:
    profile = get_resume_profile(user_id, create=True)
    stored = []
    for item in skills[:40]:
        name = str(item.get("skill") or "").strip()[:120]
        if not name:
            continue
        stored.append({
            "id": str(item.get("id") or uuid.uuid4().hex),
            "skill": name,
            "evidence_span": str(item.get("evidence_span") or "")[:280],
            "confidence": float(item.get("confidence") or 0.5),
            "status": str(item.get("status") or "needs_review"),
            "source_section": str(item.get("source_section") or "resume"),
        })
    profile.extracted_skills_json = json.dumps(stored, ensure_ascii=False)
    profile.confidence = round(sum(float(item.get("confidence", 0.0)) for item in stored) / len(stored), 3) if stored else 0.0
    db.session.commit()
    return profile


def action_item_payload(item: ActionItem | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "id": item.id,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "action_type": item.action_type,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "priority": item.priority,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
    }


def get_current_action(user_id: int) -> ActionItem | None:
    open_item = (
        ActionItem.query.filter_by(user_id=user_id)
        .filter(ActionItem.status.in_(("not_started", "in_progress", "needs_review")))
        .order_by(ActionItem.created_at.desc())
        .first()
    )
    if open_item is not None:
        return open_item
    return ActionItem.query.filter_by(user_id=user_id).order_by(ActionItem.created_at.desc()).first()


def save_action_item(*, user_id: int, values: dict[str, Any]) -> ActionItem:
    current = get_current_action(user_id)
    if current is not None and current.status in {"not_started", "in_progress"}:
        item = current
    else:
        item = ActionItem(user_id=user_id)
        db.session.add(item)
    item.source_type = values.get("source_type") or "skill_gap"
    item.source_id = values.get("source_id") or ""
    item.action_type = values.get("action_type") or "learn_skill"
    item.title = values["title"]
    item.description = values.get("description") or ""
    item.status = values.get("status") or "not_started"
    item.priority = int(values.get("priority") or 1)
    item.completed_at = None
    db.session.commit()
    return item


def update_action_status(*, user_id: int, action_id: int, status: str) -> ActionItem | None:
    item = ActionItem.query.filter_by(id=action_id, user_id=user_id).first()
    if item is None or status not in ActionItem.STATUSES:
        return None
    item.status = status
    item.completed_at = _utc_now() if status == "completed" else None
    db.session.commit()
    return item


def target_job_match_payload(row: TargetJobMatch | None) -> dict[str, Any] | None:
    if row is None:
        return None
    try:
        result = json.loads(row.result_json or "{}")
    except json.JSONDecodeError:
        result = {}
    return {
        "id": row.id,
        "title": row.title,
        "company": row.company,
        "location": row.location,
        "description_raw": row.description_raw,
        "content_hash": row.content_hash,
        "evidence_source_type": getattr(row, "evidence_source_type", None) or "profile",
        "evidence_source_key": getattr(row, "evidence_source_key", None) or "profile",
        "evidence_source_label": getattr(row, "evidence_source_label", None) or "Current evidence profile",
        "resume_version_id": getattr(row, "resume_version_id", None),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "result": result,
        "export_supported": False,
    }


def get_owned_target_job_match(user_id: int, match_id: int) -> TargetJobMatch | None:
    return TargetJobMatch.query.filter_by(id=match_id, user_id=user_id).first()


def list_owned_target_job_matches(user_id: int) -> list[TargetJobMatch]:
    return TargetJobMatch.query.filter_by(user_id=user_id).order_by(TargetJobMatch.created_at.desc()).all()


def save_target_job_match(*, user_id: int, values: dict[str, Any]) -> tuple[TargetJobMatch, bool]:
    """Reuse the owned row for the same description hash and evidence source (Option B)."""
    description = values["description_raw"]
    digest = _content_hash(description)
    source_key = values.get("evidence_source_key") or "profile"
    existing = TargetJobMatch.query.filter_by(
        user_id=user_id,
        content_hash=digest,
        evidence_source_key=source_key,
    ).first()
    now = _utc_now()
    payload = json.dumps(values.get("result") or {}, ensure_ascii=False)
    if existing is not None:
        existing.title = values.get("title") or existing.title
        existing.company = values.get("company") or existing.company
        existing.location = values.get("location") or existing.location
        existing.description_raw = description
        existing.result_json = payload
        existing.evidence_source_type = values.get("evidence_source_type") or "profile"
        existing.evidence_source_label = values.get("evidence_source_label") or "Current evidence profile"
        existing.resume_version_id = values.get("resume_version_id")
        existing.updated_at = now
        db.session.commit()
        return existing, False
    row = TargetJobMatch(
        user_id=user_id,
        title=values.get("title") or "",
        company=values.get("company") or "",
        location=values.get("location") or "",
        description_raw=description,
        content_hash=digest,
        evidence_source_type=values.get("evidence_source_type") or "profile",
        evidence_source_key=source_key,
        evidence_source_label=values.get("evidence_source_label") or "Current evidence profile",
        resume_version_id=values.get("resume_version_id"),
        result_json=payload,
        created_at=now,
        updated_at=now,
    )
    db.session.add(row)
    db.session.commit()
    return row, True


def update_owned_target_job_match(*, user_id: int, match_id: int, values: dict[str, Any]) -> TargetJobMatch | None:
    row = get_owned_target_job_match(user_id, match_id)
    if row is None:
        return None
    if "title" in values:
        row.title = values.get("title") or ""
    if "company" in values:
        row.company = values.get("company") or ""
    if "location" in values:
        row.location = values.get("location") or ""
    row.updated_at = _utc_now()
    db.session.commit()
    return row


def delete_owned_target_job_match(*, user_id: int, match_id: int) -> bool:
    row = get_owned_target_job_match(user_id, match_id)
    if row is None:
        return False
    Application.query.filter_by(user_id=user_id, target_job_match_id=match_id).update(
        {Application.target_job_match_id: None}
    )
    db.session.delete(row)
    db.session.commit()
    return True


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def job_posting_payload(job: JobPosting) -> dict[str, Any]:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "description_raw": job.description_raw,
        "source_url": job.source_url,
        "content_hash": job.content_hash,
        "created_at": job.created_at.isoformat(),
    }


def resume_version_payload(version: ResumeVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "name": version.name,
        "content_hash": version.content_hash,
        "created_at": version.created_at.isoformat(),
    }


def application_payload(application: Application) -> dict[str, Any]:
    job = db.session.get(JobPosting, application.job_posting_id)
    match_id = getattr(application, "target_job_match_id", None)
    match = get_owned_target_job_match(application.user_id, match_id) if match_id else None
    version = None
    if application.resume_version_id:
        version = get_owned_resume_version(application.user_id, application.resume_version_id)
    return {
        "id": application.id,
        "job_posting_id": application.job_posting_id,
        "resume_version_id": application.resume_version_id,
        "resume_version_name": version.name if version else None,
        "analysis_snapshot_id": application.analysis_snapshot_id,
        "target_job_match_id": match_id,
        "comparison_available": match is not None,
        "status": application.status,
        "follow_up_date": application.follow_up_date.isoformat() if application.follow_up_date else None,
        "notes": application.notes,
        "job": {"title": job.title, "company": job.company, "source_url": job.source_url} if job else None,
        "export_supported": False,
    }


def snapshot_payload(snapshot: AnalysisSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "snapshot_hash": snapshot.snapshot_hash,
        "comparison_timestamp": snapshot.comparison_timestamp.isoformat(),
        "result": json.loads(snapshot.result_json or "{}"),
    }


def create_job_posting(*, user_id: int, title: str, company: str, description_raw: str, source_url: str) -> JobPosting:
    job = JobPosting(
        user_id=user_id,
        title=title,
        company=company,
        description_raw=description_raw,
        source_url=source_url,
        content_hash=_content_hash(description_raw),
    )
    db.session.add(job)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = JobPosting.query.filter_by(user_id=user_id, content_hash=_content_hash(description_raw)).first()
        if existing is None:
            raise
        return existing
    return job


def get_owned_job(user_id: int, job_id: int) -> JobPosting | None:
    return JobPosting.query.filter_by(id=job_id, user_id=user_id).first()


def create_resume_version(*, user_id: int, name: str, content_text: str) -> ResumeVersion:
    version = ResumeVersion(
        user_id=user_id,
        name=name,
        content_text=content_text,
        content_hash=_content_hash(content_text),
    )
    db.session.add(version)
    db.session.commit()
    return version


def get_owned_resume_version(user_id: int, version_id: int) -> ResumeVersion | None:
    return ResumeVersion.query.filter_by(id=version_id, user_id=user_id).first()


def create_application(
    *,
    user_id: int,
    job_posting_id: int,
    resume_version_id: int | None = None,
    status: str = "Bookmarked",
    notes: str = "",
    target_job_match_id: int | None = None,
) -> Application:
    application = Application(
        user_id=user_id,
        job_posting_id=job_posting_id,
        resume_version_id=resume_version_id,
        status=status,
        notes=notes,
        target_job_match_id=target_job_match_id,
    )
    db.session.add(application)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = Application.query.filter_by(user_id=user_id, job_posting_id=job_posting_id).first()
        if existing is None:
            raise
        return existing
    return application


def get_or_create_owned_job_posting(
    *,
    user_id: int,
    title: str,
    company: str,
    description_raw: str,
    source_url: str = "",
) -> JobPosting:
    digest = _content_hash(description_raw)
    existing = JobPosting.query.filter_by(user_id=user_id, content_hash=digest).first()
    if existing is not None:
        if title:
            existing.title = title[:200]
        if company:
            existing.company = company[:160]
        db.session.commit()
        return existing
    return create_job_posting(
        user_id=user_id,
        title=title or "Saved job",
        company=company,
        description_raw=description_raw,
        source_url=source_url,
    )


def save_application_from_target_job_match(*, user_id: int, match: TargetJobMatch) -> tuple[Application, bool]:
    """Reuse one application per user and job-description hash. Comparison engine stays Target Job Match."""
    job = get_or_create_owned_job_posting(
        user_id=user_id,
        title=match.title or "Saved job",
        company=match.company or "",
        description_raw=match.description_raw,
    )
    resume_version_id = match.resume_version_id
    if resume_version_id is not None and get_owned_resume_version(user_id, resume_version_id) is None:
        resume_version_id = None
    existing = Application.query.filter_by(user_id=user_id, job_posting_id=job.id).first()
    if existing is not None:
        existing.target_job_match_id = match.id
        if resume_version_id is not None:
            existing.resume_version_id = resume_version_id
        existing.updated_at = _utc_now()
        db.session.commit()
        return existing, False
    application = create_application(
        user_id=user_id,
        job_posting_id=job.id,
        resume_version_id=resume_version_id,
        status="Bookmarked",
        target_job_match_id=match.id,
    )
    created = application.target_job_match_id == match.id and Application.query.filter_by(
        user_id=user_id, job_posting_id=job.id
    ).count() == 1
    if not created:
        application.target_job_match_id = match.id
        db.session.commit()
        return application, False
    return application, True


def get_owned_application(user_id: int, application_id: int) -> Application | None:
    return Application.query.filter_by(id=application_id, user_id=user_id).first()


def list_owned_applications(user_id: int) -> list[Application]:
    return Application.query.filter_by(user_id=user_id).order_by(Application.updated_at.desc()).all()


def create_analysis_snapshot(
    *,
    user_id: int,
    job_posting_id: int,
    resume_version_id: int,
    result: dict[str, Any],
    snapshot_hash: str,
) -> AnalysisSnapshot:
    snapshot = AnalysisSnapshot(
        user_id=user_id,
        job_posting_id=job_posting_id,
        resume_version_id=resume_version_id,
        result_json=json.dumps(result, ensure_ascii=False),
        snapshot_hash=snapshot_hash,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


def create_partnership_request(*, organization: str, contact_email: str, use_case: str) -> PartnershipRequest | None:
    try:
        item = PartnershipRequest(organization=organization, contact_email=contact_email, use_case=use_case)
        db.session.add(item)
        db.session.commit()
        return item
    except Exception:
        db.session.rollback()
        log.exception("Could not store partnership request")
        return None


def record_partnership_response(request_id: int, message: str) -> PartnershipRequest | None:
    try:
        item = db.session.get(PartnershipRequest, request_id)
        if item is None:
            return None
        item.response_message = message
        item.responded_at = _utc_now()
        item.status = "responded"
        db.session.commit()
        return item
    except Exception:
        db.session.rollback()
        log.exception("Could not store partnership response")
        return None


def record_upload(*, filename: str, file_type: str, mode: str, risk_score: float, risk_label: str, reasoning: dict[str, Any], user_id: int | None = None) -> Upload | None:
    try:
        upload = Upload(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            mode=mode,
            risk_score=float(risk_score),
            risk_label=risk_label,
            reasoning_json=json.dumps(reasoning, ensure_ascii=False),
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


def get_all_users() -> list[User]:
    """Return all users ordered by creation date (newest first)."""
    return User.query.order_by(User.created_at.desc()).all()





def get_detailed_metrics() -> dict[str, Any]:
    """Return detailed admin metrics including user stats."""
    users = get_all_users()
    uploads = Upload.query.order_by(Upload.created_at.desc()).all()
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).limit(10).all()

    total_users = len(users)
    verified_users = sum(1 for u in users if u.email_verified)
    admin_users = sum(1 for u in users if u.role == "admin")
    oauth_users = sum(1 for u in users if u.password_hash and len(u.password_hash) > 60 and "oauth" in (u.email or ""))
    recent_users = users[:5]

    total_uploads = len(uploads)
    mode_counts = {"standard": 0, "advanced": 0}
    risk_buckets = {"low": 0, "moderate": 0, "elevated": 0}
    average_risk = 0.0

    for upload in uploads:
        mode_counts[upload.mode if upload.mode in mode_counts else "standard"] += 1
        if upload.risk_score < RISK_LOW:
            risk_buckets["low"] += 1
        elif upload.risk_score < RISK_MODERATE:
            risk_buckets["moderate"] += 1
        else:
            risk_buckets["elevated"] += 1
        average_risk += upload.risk_score

    if total_uploads:
        average_risk /= total_uploads

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "admin_users": admin_users,
        "oauth_users": oauth_users,
        "recent_users": recent_users,
        "total_uploads": total_uploads,
        "average_risk": round(average_risk, 3),
        "mode_counts": mode_counts,
        "risk_buckets": risk_buckets,
        "recent_uploads": uploads[:8],
        "all_uploads": uploads,
        "recent_feedback": feedback_items,
    }


def dashboard_metrics() -> dict[str, Any]:
    uploads = Upload.query.order_by(Upload.created_at.desc()).all()
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).limit(5).all()
    total_uploads = len(uploads)
    mode_counts = {"standard": 0, "advanced": 0}
    risk_buckets = {"low": 0, "moderate": 0, "elevated": 0}
    average_risk = 0.0

    for upload in uploads:
        mode_counts[upload.mode if upload.mode in mode_counts else "standard"] += 1
        if upload.risk_score < RISK_LOW:
            risk_buckets["low"] += 1
        elif upload.risk_score < RISK_MODERATE:
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
