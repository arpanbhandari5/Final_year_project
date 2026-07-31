from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from flask_login import UserMixin

log = logging.getLogger("prayash.storage")
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
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
    # Always log (useful in development and for auditing)
    log.info("=" * 50)
    log.info("EMAIL TO: %s", to_email)
    log.info("SUBJECT: %s", subject)
    log.info("BODY:\n%s\n", html_body if not text_body else text_body)
    log.info("=" * 50)

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
