from __future__ import annotations

import os
import json
import uuid
import hashlib
from datetime import datetime
from typing import Any

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
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


class CareerProfile(db.Model):
    __tablename__ = "career_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    intent = db.Column(db.String(80), nullable=False, default="")
    target_role = db.Column(db.String(160), nullable=False, default="")
    target_role_source = db.Column(db.String(24), nullable=False, default="user")
    confidence = db.Column(db.String(24), nullable=False, default="self-reported")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResumeProfile(db.Model):
    __tablename__ = "resume_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    extracted_skills_json = db.Column(db.Text, nullable=False, default="[]")
    evidence_spans_json = db.Column(db.Text, nullable=False, default="[]")
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobPosting(db.Model):
    __tablename__ = "job_postings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(160), nullable=False, default="")
    description_raw = db.Column(db.Text, nullable=False)
    source_url = db.Column(db.String(1000), nullable=False, default="")
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class ResumeVersion(db.Model):
    __tablename__ = "resume_versions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    content_text = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class AnalysisSnapshot(db.Model):
    __tablename__ = "analysis_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_postings.id"), nullable=False)
    resume_version_id = db.Column(db.Integer, db.ForeignKey("resume_versions.id"), nullable=False)
    snapshot_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    result_json = db.Column(db.Text, nullable=False, default="{}")
    comparison_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class Application(db.Model):
    __tablename__ = "applications"

    STATUSES = ("Bookmarked", "Applying", "Applied", "Interviewing", "Accepted", "Rejected")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_postings.id"), nullable=False, index=True)
    resume_version_id = db.Column(db.Integer, db.ForeignKey("resume_versions.id"), nullable=True)
    analysis_snapshot_id = db.Column(db.Integer, db.ForeignKey("analysis_snapshots.id"), nullable=True)
    status = db.Column(db.String(24), nullable=False, default="Bookmarked", index=True)
    follow_up_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class OnetOccupation(db.Model):
    __tablename__ = "onet_occupations"

    id = db.Column(db.Integer, primary_key=True)
    onet_soc_code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    job_zone = db.Column(db.String(32), nullable=False, default="")
    release_version = db.Column(db.String(32), nullable=False, index=True)
    release_date = db.Column(db.String(16), nullable=False, default="2026")
    imported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OnetTask(db.Model):
    __tablename__ = "onet_tasks"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    task_id = db.Column(db.String(80), nullable=False, default="")
    statement = db.Column(db.Text, nullable=False)
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OnetSkill(db.Model):
    __tablename__ = "onet_skills"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    element_id = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    scale_id = db.Column(db.String(16), nullable=False, default="")
    value = db.Column(db.Float, nullable=True)
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OnetTechnology(db.Model):
    __tablename__ = "onet_technologies"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(120), nullable=False, default="")
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OnetInterest(db.Model):
    __tablename__ = "onet_interests"

    id = db.Column(db.Integer, primary_key=True)
    occupation_id = db.Column(db.Integer, db.ForeignKey("onet_occupations.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    score = db.Column(db.Float, nullable=True)
    release_version = db.Column(db.String(32), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CanonicalSkill(db.Model):
    __tablename__ = "canonical_skills"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, unique=True, index=True)
    slug = db.Column(db.String(180), nullable=False, unique=True, index=True)
    category = db.Column(db.String(80), nullable=False, default="technical")
    description = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class SkillAlias(db.Model):
    __tablename__ = "skill_aliases"

    id = db.Column(db.Integer, primary_key=True)
    canonical_skill_id = db.Column(db.Integer, db.ForeignKey("canonical_skills.id"), nullable=False, index=True)
    alias = db.Column(db.String(160), nullable=False, unique=True, index=True)
    normalized_alias = db.Column(db.String(160), nullable=False, index=True)


class SkillPrerequisite(db.Model):
    __tablename__ = "skill_prerequisites"

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("canonical_skills.id"), nullable=False, index=True)
    prerequisite_skill_id = db.Column(db.Integer, db.ForeignKey("canonical_skills.id"), nullable=False, index=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)


class LearningPlan(db.Model):
    __tablename__ = "learning_plans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, default="Ordered Learning Path")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LearningPlanItem(db.Model):
    __tablename__ = "learning_plan_items"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("learning_plans.id"), nullable=False, index=True)
    target_skill_id = db.Column(db.Integer, db.ForeignKey("canonical_skills.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(32), nullable=False)
    external_url = db.Column(db.String(1000), nullable=True)
    estimated_hours = db.Column(db.Float, nullable=False, default=1.0)
    prerequisite_order = db.Column(db.Integer, nullable=False, default=0)
    completion_status = db.Column(db.String(24), nullable=False, default="not_started")


class ProgressEvent(db.Model):
    __tablename__ = "progress_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    learning_plan_item_id = db.Column(db.Integer, db.ForeignKey("learning_plan_items.id"), nullable=False, index=True)
    event_type = db.Column(db.String(32), nullable=False)
    note = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


def _default_admin_credentials() -> tuple[str, str]:
    username = os.environ.get("ADMIN_EMAIL", "admin123@prayash")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    return username, password


def init_database(app) -> None:
    db.init_app(app)
    with app.app_context():
        db.create_all()
        migrate_lightweight_schema()
        seed_default_users()


def migrate_lightweight_schema() -> None:
    """Keep local SQLite review databases usable until Alembic is introduced."""
    tables = inspect(db.engine).get_table_names()
    if "partnership_requests" not in tables:
        return
    existing = {column["name"] for column in inspect(db.engine).get_columns("partnership_requests")}
    additions = {
        "response_message": "TEXT",
        "responded_at": "DATETIME",
    }
    with db.engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE partnership_requests ADD COLUMN {name} {column_type}"))


def seed_default_users() -> None:
    admin_username, admin_password = _default_admin_credentials()
    admin_user = User.query.filter_by(username=admin_username).first()
    if admin_user is None:
        admin_user = User(username=admin_username, role="admin")
        db.session.add(admin_user)
    admin_user.role = "admin"
    admin_user.set_password(admin_password)

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
        "alternative_roles": _json_list(goal.alternative_roles_json),
        "geography": goal.geography,
        "seniority": goal.seniority,
        "time_per_week": goal.time_per_week,
        "learning_budget": goal.learning_budget,
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
    db.session.commit()
    return goal


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


def correct_resume_skill(*, user_id: int, action: str, skill_id: str | None, skill: str | None, evidence_span: str | None, confidence: float | None) -> ResumeProfile | None:
    profile = get_resume_profile(user_id, create=True)
    skills = _json_list(profile.extracted_skills_json)
    index = next((position for position, item in enumerate(skills) if str(item.get("id")) == skill_id), None)
    if action == "add":
        if not skill:
            return None
        skills.append({"id": uuid.uuid4().hex, "skill": skill, "evidence_span": evidence_span or "", "confidence": confidence if confidence is not None else 0.5})
    elif action == "edit":
        if index is None or not skill:
            return None
        skills[index].update({"skill": skill, "evidence_span": evidence_span if evidence_span is not None else skills[index].get("evidence_span", ""), "confidence": confidence if confidence is not None else skills[index].get("confidence", 0.5)})
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


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def job_posting_payload(job: JobPosting) -> dict[str, Any]:
    return {"id": job.id, "title": job.title, "company": job.company, "description_raw": job.description_raw, "source_url": job.source_url, "content_hash": job.content_hash, "created_at": job.created_at.isoformat()}


def resume_version_payload(version: ResumeVersion) -> dict[str, Any]:
    return {"id": version.id, "name": version.name, "content_hash": version.content_hash, "created_at": version.created_at.isoformat()}


def application_payload(application: Application) -> dict[str, Any]:
    job = db.session.get(JobPosting, application.job_posting_id)
    return {
        "id": application.id,
        "job_posting_id": application.job_posting_id,
        "resume_version_id": application.resume_version_id,
        "analysis_snapshot_id": application.analysis_snapshot_id,
        "status": application.status,
        "follow_up_date": application.follow_up_date.isoformat() if application.follow_up_date else None,
        "notes": application.notes,
        "job": {"title": job.title, "company": job.company, "source_url": job.source_url} if job else None,
    }


def snapshot_payload(snapshot: AnalysisSnapshot) -> dict[str, Any]:
    return {"id": snapshot.id, "snapshot_hash": snapshot.snapshot_hash, "comparison_timestamp": snapshot.comparison_timestamp.isoformat(), "result": json.loads(snapshot.result_json or "{}")}


def create_job_posting(*, user_id: int, title: str, company: str, description_raw: str, source_url: str) -> JobPosting:
    job = JobPosting(user_id=user_id, title=title, company=company, description_raw=description_raw, source_url=source_url, content_hash=_content_hash(description_raw))
    db.session.add(job)
    db.session.commit()
    return job


def get_owned_job(user_id: int, job_id: int) -> JobPosting | None:
    return JobPosting.query.filter_by(id=job_id, user_id=user_id).first()


def create_resume_version(*, user_id: int, name: str, content_text: str) -> ResumeVersion:
    version = ResumeVersion(user_id=user_id, name=name, content_text=content_text, content_hash=_content_hash(content_text))
    db.session.add(version)
    db.session.commit()
    return version


def get_owned_resume_version(user_id: int, version_id: int) -> ResumeVersion | None:
    return ResumeVersion.query.filter_by(id=version_id, user_id=user_id).first()


def create_application(*, user_id: int, job_posting_id: int, resume_version_id: int | None = None, status: str = "Bookmarked", notes: str = "") -> Application:
    application = Application(user_id=user_id, job_posting_id=job_posting_id, resume_version_id=resume_version_id, status=status, notes=notes)
    db.session.add(application)
    db.session.commit()
    return application


def get_owned_application(user_id: int, application_id: int) -> Application | None:
    return Application.query.filter_by(id=application_id, user_id=user_id).first()


def list_owned_applications(user_id: int) -> list[Application]:
    return Application.query.filter_by(user_id=user_id).order_by(Application.updated_at.desc()).all()


def create_analysis_snapshot(*, user_id: int, job_posting_id: int, resume_version_id: int, result: dict[str, Any], snapshot_hash: str) -> AnalysisSnapshot:
    snapshot = AnalysisSnapshot(user_id=user_id, job_posting_id=job_posting_id, resume_version_id=resume_version_id, result_json=json.dumps(result, ensure_ascii=False), snapshot_hash=snapshot_hash)
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


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


def create_partnership_request(*, organization: str, contact_email: str, use_case: str) -> PartnershipRequest | None:
    try:
        item = PartnershipRequest(organization=organization, contact_email=contact_email, use_case=use_case)
        db.session.add(item)
        db.session.commit()
        return item
    except Exception:
        db.session.rollback()
        return None


def record_partnership_response(request_id: int, message: str) -> PartnershipRequest | None:
    try:
        item = db.session.get(PartnershipRequest, request_id)
        if item is None:
            return None
        item.response_message = message
        item.responded_at = datetime.utcnow()
        item.status = "responded"
        db.session.commit()
        return item
    except Exception:
        db.session.rollback()
        return None


def dashboard_metrics() -> dict[str, Any]:
    uploads = Upload.query.order_by(Upload.created_at.desc()).all()
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).limit(5).all()
    partnership_requests = PartnershipRequest.query.order_by(PartnershipRequest.created_at.desc()).limit(20).all()
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
        "partnership_requests": partnership_requests,
    }
