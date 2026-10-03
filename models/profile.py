"""
Prayash — Career Profile Model
===============================
Stores the user's career profile: education, current occupation, experience,
career interests, preferred roles/industry, skills and career goal.

The profile feeds personalised recommendations (skill gap, career paths,
assistant context) the same way SAHAY_AI uses its user profile — but kept
inside this project's existing SQLAlchemy + Flask-Login architecture.

Model:
    - UserProfile  one row per user (1:1 with users.id)
"""

from __future__ import annotations

from extensions import db
from models import utc_now


class UserProfile(db.Model):
    """One-to-one career profile attached to a user account."""

    __tablename__ = "user_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    education = db.Column(db.String(120), nullable=True)      # e.g. "B.Tech", "M.Sc"
    occupation = db.Column(db.String(120), nullable=True)     # e.g. "Student", "QA Analyst"
    experience_level = db.Column(db.String(40), nullable=True)  # e.g. "0-1", "1-3", "3-5", "5+"
    preferred_roles = db.Column(db.String(255), nullable=True)  # comma-separated roles
    preferred_industry = db.Column(db.String(120), nullable=True)
    skills = db.Column(db.String(500), nullable=True)          # comma-separated skills
    career_goal = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", backref=db.backref("career_profile", uselist=False, cascade="all, delete-orphan"))

    def to_dict(self) -> dict[str, str | None]:
        """JSON-safe representation for the frontend."""
        return {
            "education": self.education,
            "occupation": self.occupation,
            "experience_level": self.experience_level,
            "preferred_roles": self.preferred_roles,
            "preferred_industry": self.preferred_industry,
            "skills": self.skills,
            "career_goal": self.career_goal,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<UserProfile user={self.user_id}>"
