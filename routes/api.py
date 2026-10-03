"""
Prayash — Analysis & Career Chat API Routes
============================================
Resume analysis (risk, roles, roadmap, RIASEC), SSE streaming, skills-gap,
career paths, the legacy career-chat endpoints, feedback, and misc JSON APIs.

Kept as plain ``@app.route`` functions (registered via ``register_api``)
so endpoint names stay as the front-end and tests expect them.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from flask import Response, current_app, jsonify, render_template, request, stream_with_context, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf
from werkzeug.utils import secure_filename

from llm_cooldown import is_ollama_on_cooldown, mark_ollama_unavailable
from resume_parser import (
    analyze_resume_quality,
    extract_skills_from_text,
    parse_resume_enhanced,
)
from resume_parser import extract_resume_text as parse_resume_file
from risk_assessor import analyze_resume as assess_resume
from risk_assessor import (
    _score_risk,
    _top_matches,
    analyze_skills_gap,
    generate_learning_roadmap,
    get_available_roles,
    load_artifacts,
    suggest_career_paths,
)
from services.resume_service import compute_ats_score
from security import _RATE_LIMIT_MAX_REQUESTS, _RATE_LIMIT_WINDOW, rate_limit
from storage import record_feedback, record_upload
from utils import RISK_LOW, RISK_MODERATE, clean_text, get_cache_bust_hash, risk_label

log = logging.getLogger("prayash.api")

# ── Skill → role affinity (curated) ──────────────────────────────────
# The bundled job corpus is synthetic: profile texts carry no real skill
# vocabulary, so keyword matching cannot rank roles. These curated keyword
# sets map the 20 role archetypes in the corpus to the skills each one
# actually requires. Scores stay explainable: coverage of the role's
# keyword set by the user's skills.
_ROLE_SKILL_MAP: dict[str, list[str]] = {
    "Data Analyst": ["python", "sql", "pandas", "power bi", "tableau", "excel", "statistics", "analytics", "data", "dashboard"],
    "Software Engineer": ["python", "java", "javascript", "git", "docker", "react", "flask", "django", "api", "testing"],
    "Business Analyst": ["sql", "excel", "requirements", "stakeholder", "analytics", "reporting", "power bi", "process", "agile"],
    "Product Manager": ["roadmap", "stakeholder", "agile", "analytics", "strategy", "user research", "prioritization", "kpi"],
    "Marketing Specialist": ["seo", "content", "social media", "campaign", "analytics", "branding", "copywriting", "email"],
    "Graphic Designer": ["photoshop", "illustrator", "figma", "branding", "typography", "layout", "design", "creative"],
    "UX Designer": ["figma", "wireframe", "prototype", "user research", "usability", "design", "persona", "accessibility"],
    "HR Specialist": ["recruitment", "onboarding", "payroll", "employee", "compliance", "interview", "engagement"],
    "Accountant": ["tally", "excel", "gst", "bookkeeping", "audit", "reconciliation", "tax", "ledger"],
    "Financial Analyst": ["excel", "modeling", "valuation", "forecasting", "sql", "reporting", "budget"],
    "Consultant": ["stakeholder", "presentation", "strategy", "research", "analysis", "communication", "project"],
    "Customer Support": ["communication", "crm", "ticketing", "zendesk", "empathy", "escalation", "phone"],
    "Sales Manager": ["crm", "negotiation", "pipeline", "leads", "quota", "b2b", "forecasting", "relationship"],
    "Teacher": ["curriculum", "lesson", "classroom", "mentoring", "assessment", "pedagogy", "tutoring"],
    "Nurse": ["patient", "clinical", "triage", " medication", "care", "vital", "emergency"],
    "Doctor": ["diagnosis", "clinical", "patient", "surgery", "treatment", "medical"],
    "Civil Engineer": ["autocad", "survey", "construction", "structural", "estimation", "site", "concrete"],
    "Electrician": ["wiring", "installation", "maintenance", "electrical", "safety", "troubleshooting"],
    "Mechanic": ["repair", "engine", "diagnostics", "maintenance", "vehicle", "tools"],
    "Lawyer": ["legal", "litigation", "contract", "compliance", "research", "drafting", "court"],
    "Plumber": ["pipe", "installation", "repair", "maintenance", "drainage", "fixtures"],
}

def clamp01(v: float) -> float:
    """Clamp a value into the 0-1 interval."""
    return max(0.0, min(1.0, float(v)))

def _job_board_links(job_role: str) -> list[dict[str, str]]:
    """Deep-link search URLs for the major job boards, per role."""
    q = quote(str(job_role or "career"))
    slug = q.lower().replace("%20", "-")
    return [
        {"label": "Indeed", "url": f"https://www.indeed.com/jobs?q={q}"},
        {"label": "LinkedIn", "url": f"https://www.linkedin.com/jobs/search/?keywords={q}"},
        {"label": "Naukri", "url": f"https://www.naukri.com/{slug}-jobs"},
    ]

def _match_jobs_by_skills(skills: list[str], bundle: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    """Rank role archetypes by curated skill-keyword coverage.

    For each archetype the corpus's ~150 industry variants are averaged so
    the returned risk score and trait chips reflect real bundled data.
    Returns at most *limit* roles with positive coverage, best first.
    """
    joined = " " + " ".join(s.lower() for s in skills) + " "
    tokens = set(re.findall(r"[a-z][a-z0-9+#.-]{1,}", joined))

    # Aggregate variants per archetype: mean risk + mean attribute scores.
    agg: dict[str, dict[str, Any]] = {}
    for profile in bundle.get("job_profiles", []):
        role = str(profile.get("job_role") or "")
        entry = agg.setdefault(role, {"n": 0, "risk": 0.0, "attrs": None})
        entry["n"] += 1
        entry["risk"] += float(profile.get("risk_score") or 0.0)
        attrs = profile.get("skills")
        if isinstance(attrs, (list, tuple)) and attrs:
            vals = [float(a) for a in attrs]
            if entry["attrs"] is None:
                entry["attrs"] = vals
            else:
                entry["attrs"] = [a + b for a, b in zip(entry["attrs"], vals)]

    scored: list[dict[str, Any]] = []
    for role, kws in _ROLE_SKILL_MAP.items():
        if role not in agg:
            continue
        matched = sum(1 for kw in kws if kw in joined or kw in tokens)
        if matched == 0:
            continue
        first = next(p for p in bundle.get("job_profiles", []) if p.get("job_role") == role)
        mean_risk = agg[role]["risk"] / max(1, agg[role]["n"])
        mean_attrs = agg[role]["attrs"]
        chips: list[str] | None = None
        if mean_attrs:
            means = [v / agg[role]["n"] for v in mean_attrs]
            labels = ["Skill complexity", "Domain knowledge", "Communication", "Collaboration"]
            top2 = sorted(zip(means, labels), reverse=True)[:2]
            chips = [f"{label} {v:.0%}" for v, label in top2]
        scored.append({
            "job_role": role,
            "industry": first.get("industry", ""),
            "risk_score": mean_risk,
            "trait_chips": chips,
            "similarity": min(1.0, matched / 5.0),  # 5 covered keywords ⇒ 100%
        })

    scored.sort(key=lambda m: m["similarity"], reverse=True)
    return scored[:limit]

# ── LLM API (OpenRouter / DeepSeek / OpenAI) ──
# openai is imported lazily on first use — importing it at module load
# pulled ~1s of SDK + pandas into every startup for code that only runs
# when an LLM API key is actually configured.
_HAS_OPENAI: bool | None = None  # None = not yet checked


def _openai_available() -> bool:
    """True if the openai SDK is importable (checked once, lazily)."""
    global _HAS_OPENAI
    if _HAS_OPENAI is None:
        try:
            import openai  # noqa: F401

            _HAS_OPENAI = True
        except Exception:
            _HAS_OPENAI = False
    return _HAS_OPENAI


_log_openai = logging.getLogger("prayash.llm")

# ── Project root (parent of routes/) ────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


# ── Auth Assistant API ──
# Context-aware conversational guidance endpoint
# Currently returns static contextual tips; can be extended with NLP/LLM

_AUTH_ASSISTANT_KNOWLEDGE = {
    "login": {
        "description": "Sign in to your Prayash account",
        "tips": [
            "Enter the email or username you used when signing up.",
            "Passwords are case-sensitive. Check that Caps Lock is off!",
            "Can't remember your password? Use the 'Forgot password?' link below.",
            "Having trouble? Try signing in with Google or GitHub instead.",
        ],
        "alternatives": ["google", "github", "linkedin"],
        "security": "🔒 Always verify you're on the official Prayash site before entering credentials.",
    },
    "signup": {
        "description": "Create your free Prayash account",
        "tips": [
            "Use your real name — it'll appear on your profile.",
            "Your username must be at least 4 characters. Use letters, numbers, and underscores.",
            "Use an email you have access to — you'll need to verify it!",
            "Create a strong password: 8+ chars, uppercase, lowercase, number, and special character.",
            "Adding a phone number is optional but helps with account recovery.",
        ],
        "alternatives": ["google", "github", "linkedin"],
        "security": "🔒 Your password is hashed and salted. We never store plain-text passwords.",
    },
    "verify": {
        "description": "Verify your email address with a 6-digit code",
        "tips": [
            "Check your inbox for the 6-digit verification code.",
            "The code expires in 10 minutes — don't wait too long!",
            "Check your Spam or Promotions folder if you don't see the email.",
            "You can request a new code after 30 seconds.",
        ],
        "alternatives": [],
        "security": "🔒 Never share your verification code with anyone. Prayash will never call or text you for it.",
    },
    "forgot": {
        "description": "Reset your password via email",
        "tips": [
            "Enter the email address associated with your Prayash account.",
            "Check your inbox (and Spam folder) for the reset code.",
            "The reset code expires in 10 minutes for your security.",
            "If you signed up with Google/GitHub, try signing in that way instead!",
        ],
        "alternatives": ["google", "github"],
        "security": "🔒 If you didn't request a password reset, you can safely ignore the email.",
    },
    "forgot_otp": {
        "description": "Enter the password reset code sent to your email",
        "tips": [
            "Enter the 6-digit code from your email.",
            "Check Spam / Promotions if you don't see the email.",
            "The code expires in 10 minutes.",
            "You can go back to request a new code if needed.",
        ],
        "alternatives": [],
        "security": "🔒 Password reset codes are single-use. Each new request invalidates the previous code.",
    },
    "reset": {
        "description": "Create a new password for your account",
        "tips": [
            "Choose a password you haven't used before on Prayash.",
            "Make it at least 8 characters with uppercase, lowercase, a number, and a special character.",
            "Try a passphrase like 'Correct-Horse-Battery-$42' — memorable AND strong!",
            "After resetting, log out of other devices if you think someone else had access.",
        ],
        "alternatives": [],
        "security": "🔒 Consider using a password manager like Bitwarden or iCloud Keychain to store your new password safely.",
    },
}


def register_api(app) -> None:
    """Register the analysis / career-chat / misc API routes on *app*."""

    @app.get("/api/auth-assistant/context")
    @rate_limit
    def api_auth_assistant_context():
        """Return contextual tips and guidance for the auth assistant."""
        page = request.args.get("page", "login").strip().lower()
        if page not in _AUTH_ASSISTANT_KNOWLEDGE:
            page = "login"
        context = dict(_AUTH_ASSISTANT_KNOWLEDGE[page])
        context["page"] = page
        return jsonify({"success": True, "context": context})

    @app.get("/api/rag-status")
    @rate_limit
    def api_rag_status():
        """RAG pipeline performance monitoring endpoint.

        SAHAY_AI-inspired: mirrors their ``/performance`` view which shows
        RAG cache info, model status, and response metrics.

        Returns:
            JSON with cache status, model info, and uptime.
        """
        from rag_retriever import rag_service

        return jsonify(
            {
                "success": True,
                "rag_service": rag_service.get_status(),
                "active_sessions": len(_CAREER_CHAT_SESSIONS),
                "rate_limit_window": _RATE_LIMIT_WINDOW,
                "rate_limit_max": _RATE_LIMIT_MAX_REQUESTS,
            }
        )

    @app.get("/healthz")
    def healthz() -> tuple[dict[str, str], int]:
        # Quick check that model artifacts are loadable
        from risk_assessor import load_artifacts
        from security import _CACHE_BACKEND

        try:
            bundle, courses = load_artifacts()
            ml_ok = bool(bundle) and bool(courses)
        except Exception:
            ml_ok = False
        return {
            "status": "ok",
            "version": get_cache_bust_hash(),
            "ml_pipeline": "ready" if ml_ok else "unavailable",
            "cache": _CACHE_BACKEND,  # "redis" or "memory"
        }, 200

    # ── CSRF Token endpoint ──
    @app.get("/api/csrf-token")
    def api_csrf_token():
        return jsonify({"csrf_token": generate_csrf()})

    # ── Password Strength Checker ──
    @app.post("/api/check-password")
    @rate_limit
    def api_check_password():
        data = request.get_json(silent=True) or {}
        pw = (data.get("password") or "").strip()
        if not pw:
            return jsonify({"score": 0, "label": "Empty", "color": "var(--error)"})
        score = 0
        if len(pw) >= 8:
            score += 1
        if len(pw) >= 12:
            score += 1
        if any(c.isupper() for c in pw):
            score += 1
        if any(c.islower() for c in pw):
            score += 1
        if any(c.isdigit() for c in pw):
            score += 1
        if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in pw):
            score += 1
        labels = ["Very weak", "Weak", "Fair", "Good", "Strong", "Very strong"]
        colors = ["var(--error)", "var(--error)", "#eab308", "#22c55e", "#22c55e", "#16a34a"]
        widths = ["16%", "33%", "50%", "66%", "83%", "100%"]
        idx = min(score, 5)
        return jsonify({"score": score, "label": labels[idx], "color": colors[idx], "width": widths[idx]})

    @app.post("/api/feedback")
    @rate_limit
    def api_feedback():
        payload = request.get_json(silent=True) if request.is_json else {}
        message = (request.form.get("message") or (payload or {}).get("message", "")).strip()
        rating_raw = request.form.get("rating") or (payload or {}).get("rating")
        upload_id_raw = request.form.get("upload_id") or (payload or {}).get("upload_id")
        if not message:
            return jsonify({"success": False, "error": "Feedback message is required."}), 400

        rating = None
        upload_id = None
        try:
            rating = int(rating_raw) if rating_raw is not None and rating_raw != "" else None
        except Exception:
            rating = None
        try:
            upload_id = int(upload_id_raw) if upload_id_raw is not None and upload_id_raw != "" else None
        except Exception:
            upload_id = None

        feedback = record_feedback(
            message=message,
            rating=rating,
            upload_id=upload_id,
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        if feedback is None:
            return jsonify({"success": False, "error": "Could not store feedback."}), 500
        return jsonify({"success": True})

    # ── Analysis helpers ─────────────────────────────────────────────

    def _build_support_resources() -> list[dict[str, str]]:
        return [
            {
                "title": "Learning resources",
                "description": "Use roadmap suggestions to strengthen high-impact skills in the next 2 to 6 weeks.",
                "link": url_for("methodology"),
                "cta": "Explore methodology",
            },
            {
                "title": "Job search help",
                "description": "Use top role matches as search keywords for alerts, applications, and profile updates.",
                "link": url_for("insights"),
                "cta": "Open insights",
            },
            {
                "title": "Education and training",
                "description": "Compare short certificates and longer pathways for your target roles.",
                "link": url_for("partnerships"),
                "cta": "See partnerships",
            },
            {
                "title": "Support and privacy",
                "description": "Review how your data is handled and where to get additional guidance.",
                "link": url_for("privacy"),
                "cta": "Read privacy details",
            },
        ]

    def _build_guided_next_steps(analysis: dict[str, Any]) -> dict[str, list[str]]:
        top_roles = analysis.get("top_roles") or []
        roadmap = analysis.get("roadmap") or []
        risk_label = str(analysis.get("risk_label") or "Moderate")

        role_names = [str(role.get("job_role") or "").strip() for role in top_roles if role.get("job_role")]
        primary_roles = [name for name in role_names if name][:2]

        learning_actions: list[str] = []
        for item in roadmap[:3]:
            course = str(item.get("course") or "").strip()
            skill = str(item.get("skill") or "core skill").strip()
            if course:
                learning_actions.append(f"Start '{course}' and focus on {skill} this week.")

        if not learning_actions:
            learning_actions.append(
                "Pick one high-impact skill gap and schedule three focused practice sessions this week."
            )

        job_search_actions: list[str] = []
        if primary_roles:
            for role_name in primary_roles:
                job_search_actions.append(f"Save 10 recent postings for {role_name} and track repeated requirements.")
            job_search_actions.append("Update your resume summary using keywords from your strongest role matches.")
        else:
            job_search_actions.extend(
                [
                    "Collect 10 postings in your target field and list repeated skills.",
                    "Tailor your resume headline for one target role before applying.",
                ]
            )

        education_actions = [
            "Compare one short certificate and one longer credential for your target direction.",
            "Set a realistic 4, 8, or 12-week timeline and add deadlines to your calendar.",
        ]
        if risk_label.lower() == "elevated":
            education_actions.insert(
                0, "Prioritize transferable digital and analytical skills to reduce automation exposure."
            )
        elif risk_label.lower() == "low":
            education_actions.insert(
                0, "Deepen specialization in your strongest areas to preserve your low-risk profile."
            )
        else:
            education_actions.insert(0, "Build adjacent skills that improve resilience and role flexibility.")

        support_resources = [
            "Review the methodology page to understand how scores and role matches are produced.",
            "Review the privacy page for clear data handling details.",
            "Use advanced mode when you want additional narrative guidance.",
        ]

        return {
            "learning_actions": learning_actions,
            "job_search_actions": job_search_actions,
            "education_training_actions": education_actions,
            "support_resources": support_resources,
        }

    def _build_report_guide(analysis: dict[str, Any]) -> dict[str, list[str]]:
        risk_label = str(analysis.get("risk_label") or "Moderate")
        mode = str(analysis.get("mode") or "standard")

        return {
            "how_this_works": [
                "Upload or paste your resume.",
                "Prayash runs local ML scoring for risk, role match, roadmap, and RIASEC fit.",
                "Advanced mode adds optional narrative guidance while preserving core ML outputs.",
            ],
            "what_your_report_means": [
                f"Your current automation band is {risk_label}.",
                "Top role matches show where your profile aligns today.",
                "Roadmap items suggest practical learning moves based on detected skills.",
            ],
            "what_to_do_next": [
                "Choose 1 to 2 actions and complete them in the next 14 days.",
                "Apply to roles that overlap with your strongest matches.",
                f"Re-run your report after updates, using {mode} mode as your baseline.",
            ],
            "need_help": [
                "Use the methodology page for model logic and assumptions.",
                "Use the privacy page for data handling details.",
                "Share feedback after your run so recommendations can improve over time.",
            ],
        }

    def _enrich_top_roles(analysis: dict[str, Any]) -> None:
        """Clean up and enrich ``analysis['top_roles']`` for the dashboard.

        The ML profiles carry two fields that leak training internals into
        the API payload: ``text`` (the raw vectorizer blob) and ``skills``
        (four numeric attribute scores, not real skill names). Each role is
        rewritten to drop ``text`` and convert the attribute scores into
        human-readable, per-role ``trait_chips`` (top-2 attributes) plus
        ``job_board_links`` for the frontend job cards.
        """
        _TRAIT_LABELS: dict[str, str] = {
            "skill_complexity_score": "Skill complexity",
            "domain_specific_knowledge_level": "Domain knowledge",
            "communication_requirement": "Communication",
            "team_collaboration_level": "Collaboration",
        }
        for role in analysis.get("top_roles") or []:
            role.pop("text", None)
            raw_attrs = role.pop("skills", None)
            if isinstance(raw_attrs, dict) and raw_attrs:
                top2 = sorted(raw_attrs.items(), key=lambda kv: kv[1], reverse=True)[:2]
                role["trait_chips"] = [label for _attr, label in top2]
            elif isinstance(raw_attrs, (list, tuple)) and raw_attrs:
                # Legacy ordered-list form: align positions to the labels,
                # then keep the two strongest attributes.
                labels = list(_TRAIT_LABELS.values())
                pairs = [(float(v), labels[i]) for i, v in enumerate(raw_attrs) if i < len(labels)]
                role["trait_chips"] = [f"{label} {v:.0%}" for v, label in sorted(pairs, reverse=True)[:2]]
            if "job_board_links" not in role:
                q = quote(str(role.get("job_role") or "career"))
                slug = q.lower().replace("%20", "-")
                role["job_board_links"] = [
                    {"label": "Indeed", "url": f"https://www.indeed.com/jobs?q={q}"},
                    {"label": "LinkedIn", "url": f"https://www.linkedin.com/jobs/search/?keywords={q}"},
                    {"label": "Naukri", "url": f"https://www.naukri.com/{slug}-jobs"},
                ]

    def _run_analysis_workflow(resume_text: str, mode: str) -> dict[str, Any]:
        """Run the full analysis pipeline.

        Model artifacts are expected to have been prepared at startup via
        ``ensure_model_artifacts()``.  If the artifacts are missing the
        analysis will raise ``RuntimeError``, which the caller should handle.
        """
        analysis = assess_resume(resume_text, mode=mode)
        _enrich_top_roles(analysis)
        analysis.setdefault("guided_next_steps", _build_guided_next_steps(analysis))
        analysis.setdefault("support_resources", _build_support_resources())
        analysis.setdefault("report_guide", _build_report_guide(analysis))
        return analysis

    # ── SSE: Real-time analysis streaming ──
    @app.get("/api/analyze-stream")
    @rate_limit
    def api_analyze_stream():
        text = request.args.get("text", "").strip()
        mode = request.args.get("mode", "standard") or "standard"
        if mode not in {"standard", "advanced"}:
            mode = "standard"
        if not text or len(text.strip()) < 20:
            return jsonify({"success": False, "error": "Resume text is required."}), 400

        def generate() -> Generator[str, None, None]:
            aid = uuid.uuid4().hex[:8]

            def emit(step: str, status: str, pct: int, data: dict | None = None):
                yield f"data: {json.dumps({'id': aid, 'step': step, 'status': status, 'percent': pct, 'data': data})}\n\n"

            yield from emit("init", "Starting analysis...", 0)
            try:
                yield from emit("parse", "Parsing resume text...", 10)
                analysis = _run_analysis_workflow(text, mode)
                yield from emit("risk", "Running automation risk prediction...", 40)
                yield from emit("roles", "Matching to O*NET roles...", 60)
                yield from emit("roadmap", "Generating learning roadmap...", 80)
                if mode == "advanced":
                    yield from emit("llama", "Running Llama 3 narrative...", 95)
                record_upload(
                    filename="streamed_resume.txt",
                    file_type="text",
                    mode=mode,
                    risk_score=analysis.get("risk_score", 0.0),
                    risk_label=analysis.get("risk_label", "Low"),
                    reasoning=analysis.get("reasoning", {}),
                    user_id=current_user.id if current_user.is_authenticated else None,
                )
                analysis.update({"success": True})
                yield from emit("complete", "Analysis complete!", 100, analysis)
            except Exception as exc:
                log.exception("Stream analysis failed")
                yield from emit("error", str(exc), -1, {"error": str(exc)})

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @rate_limit
    def _handle_upload_request():
        payload = request.get_json(silent=True) if request.is_json else {}
        resume_text = request.form.get("resume_text") or (payload or {}).get("resume_text", "")
        mode = request.form.get("mode") or (payload or {}).get("mode", "standard")
        uploaded_file = request.files.get("resume_file")

        if uploaded_file and uploaded_file.filename:
            resume_text = parse_resume_file(uploaded_file)

        resume_text = clean_text(resume_text)
        mode = clean_text(mode).lower() or "standard"

        if not resume_text:
            return jsonify({"success": False, "error": "Upload a resume or paste resume text first."}), 400

        if mode not in {"standard", "advanced"}:
            mode = "standard"

        try:
            analysis = _run_analysis_workflow(resume_text, mode)
            record_upload(
                filename=uploaded_file.filename if uploaded_file and uploaded_file.filename else "pasted_resume.txt",
                file_type=(
                    uploaded_file.filename.rsplit(".", 1)[-1].lower()
                    if uploaded_file and uploaded_file.filename and "." in uploaded_file.filename
                    else "text"
                ),
                mode=analysis.get("mode", mode),
                risk_score=analysis.get("risk_score", 0.0),
                risk_label=analysis.get("risk_label", "Low"),
                reasoning=analysis.get("reasoning", {}),
                user_id=current_user.id if current_user.is_authenticated else None,
            )
            analysis.update({"success": True})
            return jsonify(analysis)
        except Exception as exc:
            return jsonify({"success": False, "error": str(exc)}), 500

    @app.post("/api/upload")
    def api_upload():
        return _handle_upload_request()

    @app.post("/api/analyze")
    def api_analyze():
        return _handle_upload_request()

    # ── Skills Gap Analysis Endpoint ──────────────────────────────────

    @app.get("/api/skills-gap/roles")
    @rate_limit
    @login_required
    def api_skills_gap_roles():
        """Return the list of available target roles for skill gap analysis."""
        return jsonify({"success": True, "roles": get_available_roles()})

    @app.post("/api/skills-gap/analyze")
    @rate_limit
    @login_required
    def api_skills_gap_analyze():
        """Analyze skills gap between resume skills and a target role.

        Accepts ``resume_text`` as before, or ``user_skills`` (a list of
        already-extracted skills from the latest analysis) — the workspace
        Skill Gap page reuses those when the resume text is no longer in the
        form (it is intentionally never persisted server-side).
        """
        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
        target_role = (request.form.get("target_role") or data.get("target_role", "")).strip()
        raw_skills = data.get("user_skills") if isinstance(data, dict) else None
        user_skills = [str(s).strip() for s in raw_skills if str(s).strip()] if isinstance(raw_skills, (list, tuple)) else []

        if not target_role:
            return jsonify({"success": False, "error": "Target role is required."}), 400
        if (not resume_text or len(resume_text) < 20) and not user_skills:
            return jsonify({"success": False, "error": "Resume text is required (min 20 characters)."}), 400

        cleaned_text = clean_text(resume_text)

        result = analyze_skills_gap(cleaned_text, target_role, user_skills=user_skills)
        if "error" in result:
            return jsonify(
                {"success": False, "error": result["error"], "available_roles": result.get("available_roles", [])}
            ), 400

        return jsonify({"success": True, "analysis": result})    # ── Resume Strength Score API ───────────────────────────────────────

    @app.post("/score_resume")
    @rate_limit
    def api_score_resume():
        """Score a resume's strength on a 0-100 scale with sub-scores.

        Accepts either:
          - multipart/form-data with a file under "resume" (or "resume_file")
          - application/json (or form) with "resume_text"

        Returns:
            JSON: {
              success, result: {
                final_score, skill_score, experience_score, quality_score,
                feedback, skills, strengths, improvements, word_count
              }
            }
        """
        uploaded_file = request.files.get("resume") or request.files.get("resume_file")
        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or (data or {}).get("resume_text", "")).strip()

        if uploaded_file and uploaded_file.filename:
            try:
                resume_text = parse_resume_file(uploaded_file)
            except Exception:
                return jsonify({"success": False, "error": "Could not read the uploaded file."}), 400

        resume_text = clean_text(resume_text)
        if not resume_text or len(resume_text) < 20:
            return jsonify({"success": False, "error": "Provide a resume file or at least 20 characters of resume text."}), 400

        ats = compute_ats_score(resume_text)
        skills = extract_skills_from_text(resume_text)
        skill_list = skills.get("all_skills") or []
        parsed = parse_resume_enhanced(resume_text)

        # ── Sub-scores (0-100 each) ──
        # Skill: breadth of detected skills + proof of application (projects).
        n_skills = len(skill_list)
        skill_score = min(100, n_skills * 6 + (10 if parsed.get("projects") else 0))

        # Experience: career signals — work history section, quantified
        # results, tenure keywords and progression language.
        experience_score = 25
        sections_l = str(parsed.get("sections_found") or []).lower()
        if "experience" in sections_l:
            experience_score += 30
        if re.search(r"\b\d{1,3}(?:[%kKx]| percent)\b|\b\d{2,4}\+?\b", resume_text):
            experience_score += 20
        if re.search(r"\b(intern|internship|freelance|part-time|full-time|years?)\b", resume_text, re.IGNORECASE):
            experience_score += 15
        if re.search(r"\b(senior|lead|headed|promoted|managed)\b", resume_text, re.IGNORECASE):
            experience_score += 10
        experience_score = min(100, experience_score)

        # Quality: ATS compliance (structure, contact info, formatting).
        quality_score = min(100, int(ats.get("score", 0)))

        final_score = round(skill_score * 0.4 + experience_score * 0.3 + quality_score * 0.3)

        # ── Feedback ──
        if final_score >= 80:
            feedback = "Strong resume. Fine-tune keywords for each application and keep quantifying your impact."
        elif final_score >= 70:
            feedback = "Good resume, needs improvement. Add measurable results and tighten the experience section."
        elif final_score >= 40:
            feedback = "Average resume. List more skills, quantify achievements, and structure sections clearly."
        else:
            feedback = "Resume needs work. Add an experience section, list concrete skills, and quantify your results."
        strengths = [c["label"] for c in ats.get("checklist", []) if c.get("passed")][:6]
        improvements = [c["detail"] for c in ats.get("checklist", []) if not c.get("passed")][:6]

        return jsonify({
            "success": True,
            "result": {
                "final_score": final_score,
                "skill_score": skill_score,
                "experience_score": experience_score,
                "quality_score": quality_score,
                "feedback": feedback,
                "skills": skill_list[:15],
                "strengths": strengths,
                "improvements": improvements,
                "word_count": ats.get("word_count", 0),
            },
        })

    # ── Job Match API ───────────────────────────────────────────────────

    @app.post("/match_jobs")
    @rate_limit
    def api_match_jobs():
        """Return job matches for a resume or an explicit skill list.

        Accepts JSON (or form): { skills: [...], resume_text: "..." }.
        With only ``skills``, matches are ranked by keyword overlap between
        the skill list and each role's profile text. With ``resume_text``,
        the full ML similarity pipeline is used.

        Returns:
            JSON: { success, jobs: [{ title, score, skills, risk_level,
                    risk_score, industry, job_board_links, trait_chips }] }
        """
        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or (data or {}).get("resume_text", "")).strip()
        skill_input = (data or {}).get("skills") or request.form.get("skills") or []

        if isinstance(skill_input, str):
            skill_input = [s.strip() for s in skill_input.split(",") if s.strip()]
        skills = [str(s) for s in skill_input if str(s).strip()]

        if (not resume_text or len(resume_text) < 20) and not skills:
            return jsonify({"success": False, "error": "Provide resume text (min 20 chars) or a list of skills."}), 400

        bundle, _courses = load_artifacts()
        if not bundle:
            return jsonify({"success": False, "error": "Model artifacts are unavailable."}), 503

        if resume_text and len(resume_text) >= 20:
            # Full ML similarity against all job profiles.
            matches = _top_matches(bundle, clean_text(resume_text), limit=8)
        else:
            # Curated skill → archetype coverage ranking (the synthetic corpus
            # carries no real skill vocabulary, so text overlap is useless).
            matches = _match_jobs_by_skills(skills, bundle, limit=8)

        jobs: list[dict[str, Any]] = []
        for m in matches:
            if m.get("similarity", 0) <= 0 and resume_text:
                continue
            score = round(clamp01(m.get("similarity", 0.0)) * 100)
            jobs.append({
                "title": m.get("job_role", ""),
                "score": score,
                "skills": skills[:6],
                "risk_level": risk_label(float(m.get("risk_score", 0.0))),
                "risk_score": round(float(m.get("risk_score", 0.0)), 3),
                "industry": m.get("industry", ""),
                "job_board_links": _job_board_links(m.get("job_role", "")),
                "trait_chips": m.get("trait_chips") or None,  # null → frontend falls back to queried skills
            })

        return jsonify({"success": True, "jobs": jobs, "total": len(jobs)})

    # ── Risk Prediction API ─────────────────────────────────────────────

    @app.post("/predict_risk")
    @rate_limit
    def api_predict_risk():
        """Predict automation-risk for a resume.

        Accepts either:
          - multipart/form-data with a file under "resume" (or "resume_file")
          - application/json (or form) with "resume_text"

        Returns:
            JSON: { success, risk_level, risk_score, explanation,
                    bands: {low, moderate} }
        """
        uploaded_file = request.files.get("resume") or request.files.get("resume_file")
        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or (data or {}).get("resume_text", "")).strip()

        if uploaded_file and uploaded_file.filename:
            try:
                resume_text = parse_resume_file(uploaded_file)
            except Exception:
                return jsonify({"success": False, "error": "Could not read the uploaded file."}), 400

        resume_text = clean_text(resume_text)
        if not resume_text or len(resume_text) < 20:
            return jsonify({"success": False, "error": "Resume text is required (min 20 characters)."}), 400

        bundle, _courses = load_artifacts()
        if not bundle:
            return jsonify({"success": False, "error": "Model artifacts are unavailable."}), 503

        cleaned = clean_text(resume_text)
        risk_score = _score_risk(bundle, cleaned)
        level = risk_label(risk_score)

        if level == "Elevated":
            explanation = (
                f"High automation exposure ({risk_score:.0%}). Repetitive, rule-based "
                "tasks dominate this profile — prioritize the reskilling actions below."
            )
        elif level == "Moderate":
            explanation = (
                f"Moderate exposure ({risk_score:.0%}). Parts of this role can be "
                "automated; strengthening transferable skills will keep you ahead."
            )
        else:
            explanation = (
                f"Low exposure ({risk_score:.0%}). Your profile leans on judgment and "
                "interpersonal work — keep skills current to stay positioned."
            )

        return jsonify({
            "success": True,
            "risk_level": level,
            "risk_score": round(risk_score, 3),
            "explanation": explanation,
            "bands": {"low": RISK_LOW, "moderate": RISK_MODERATE},
        })

    # ── Career Paths API ────────────────────────────────────────────

    # ── Career Paths API ────────────────────────────────────────────

    @app.post("/api/career-paths")
    @rate_limit
    def api_career_paths():
        """Suggest career paths based on resume skills."""
        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
        if not resume_text or len(resume_text) < 20:
            return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400
        paths = suggest_career_paths(resume_text)
        return jsonify({"success": True, "paths": paths, "total": len(paths)})

    # ── Learning Roadmap API ────────────────────────────────────────────

    @app.post("/api/learning-roadmap")
    @rate_limit
    def api_learning_roadmap():
        """Generate a structured learning roadmap based on resume skills."""
        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
        if not resume_text or len(resume_text) < 20:
            return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400
        roadmap = generate_learning_roadmap(resume_text)
        total_weeks = sum(
            int(s.get("duration", "0").split("-")[0] or "0") for area in roadmap for s in area.get("stages", [])
        )
        return jsonify({"success": True, "roadmap": roadmap, "areas": len(roadmap), "total_weeks": total_weeks})

    # ── Personalized Roadmap API ──────────────────────────────────────

    @app.post("/api/personalized-roadmap")
    @rate_limit
    @login_required
    def api_personalized_roadmap():
        """Generate a personalized learning roadmap based on skill gap analysis."""
        from personalized_roadmap import generate_personalized_roadmap

        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
        target_role = (request.form.get("target_role") or data.get("target_role", "")).strip()
        if not resume_text or len(resume_text) < 20:
            return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400
        if not target_role:
            return jsonify({"success": False, "error": "Target role is required."}), 400
        weekly_hours = data.get("weekly_hours", 8)
        try:
            weekly_hours = max(1, min(40, int(weekly_hours)))
        except (ValueError, TypeError):
            weekly_hours = 8
        roadmap = generate_personalized_roadmap(
            resume_text=resume_text, target_role=target_role,
            user_skills=data.get("user_skills", []), missing_skills=data.get("missing_skills", []),
            matched_skills=data.get("matched_skills", []), high_priority=data.get("high_priority", []),
            medium_priority=data.get("medium_priority", []), low_priority=data.get("low_priority", []),
            weekly_hours=weekly_hours,
        )
        if "error" in roadmap:
            return jsonify({"success": False, "error": roadmap["error"]}), 400
        return jsonify({"success": True, "roadmap": roadmap})

    # ── Reskilling Roadmap API ─────────────────────────────────────────

    @app.post("/api/reskilling-roadmap")
    @rate_limit
    @login_required
    def api_reskilling_roadmap():
        """Generate a reskilling roadmap for career transition."""
        from personalized_roadmap import generate_reskilling_roadmap

        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
        current_career = (request.form.get("current_career") or data.get("current_career", "")).strip()
        automation_risk = (request.form.get("automation_risk") or data.get("automation_risk", "Moderate")).strip()
        recommended_transition = (request.form.get("recommended_transition") or data.get("recommended_transition", "")).strip()
        if not resume_text or len(resume_text) < 20:
            return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400
        if not recommended_transition:
            return jsonify({"success": False, "error": "Recommended transition career is required."}), 400
        weekly_hours = data.get("weekly_hours", 8)
        try:
            weekly_hours = max(1, min(40, int(weekly_hours)))
        except (ValueError, TypeError):
            weekly_hours = 8
        roadmap = generate_reskilling_roadmap(
            resume_text=resume_text, current_career=current_career,
            automation_risk=automation_risk, recommended_transition=recommended_transition,
            weekly_hours=weekly_hours,
        )
        if "error" in roadmap:
            return jsonify({"success": False, "error": roadmap["error"]}), 400
        return jsonify({"success": True, "roadmap": roadmap})

    # ── Roadmap Progress API ─────────────────────────────────────────

    @app.get("/api/roadmap-progress")
    @rate_limit
    @login_required
    def api_get_roadmap_progress():
        """Get saved roadmap progress for the current user."""
        from storage import get_roadmap_progress

        target_role = request.args.get("target_role", "").strip()
        if not target_role:
            return jsonify({"success": False, "error": "Target role is required."}), 400
        progress = get_roadmap_progress(current_user.id, target_role)
        return jsonify({"success": True, "progress": progress})

    @app.post("/api/roadmap-progress")
    @rate_limit
    @login_required
    def api_save_roadmap_progress():
        """Save roadmap progress for the current user."""
        from storage import save_roadmap_progress

        data = request.get_json(silent=True) or {}
        target_role = (data.get("target_role") or "").strip()
        progress = data.get("progress", {})
        weekly_hours = data.get("weekly_hours", 8)
        if not target_role:
            return jsonify({"success": False, "error": "Target role is required."}), 400
        ok = save_roadmap_progress(current_user.id, target_role, progress, weekly_hours)
        if not ok:
            return jsonify({"success": False, "error": "Could not save progress."}), 500
        return jsonify({"success": True})

    # ── Career Profile API (Workplace → Profile page) ─────────────────

    @app.get("/api/profile")
    @rate_limit
    @login_required
    def api_get_profile():
        """Return the signed-in user's career profile (null fields when unset)."""
        from storage import get_user_profile

        return jsonify({"success": True, "profile": get_user_profile(current_user.id)})

    @app.post("/api/profile")
    @rate_limit
    @login_required
    def api_save_profile():
        """Create or update the signed-in user's career profile.

        Accepts JSON: { education, occupation, experience_level,
        preferred_roles, preferred_industry, skills, career_goal }.
        Every field is optional; only provided fields are written.
        """
        from storage import save_user_profile

        data = request.get_json(silent=True) or {}

        def _clean(field: str, cap: int) -> str | None:
            value = str(data.get(field) or "").strip()
            if not value:
                return None
            return value[:cap]

        payload = {
            "education": _clean("education", 120),
            "occupation": _clean("occupation", 120),
            "experience_level": _clean("experience_level", 40),
            "preferred_roles": _clean("preferred_roles", 255),
            "preferred_industry": _clean("preferred_industry", 120),
            "skills": _clean("skills", 500),
            "career_goal": _clean("career_goal", 2000),
        }
        if not any(payload.values()):
            return jsonify({"success": False, "error": "Provide at least one profile field."}), 400

        saved = save_user_profile(current_user.id, payload)
        if saved is None:
            return jsonify({"success": False, "error": "Could not save your profile. Please try again."}), 500
        return jsonify({"success": True, "profile": saved, "message": "Profile saved successfully."})

    # ── Analysis History API (Workplace → History page) ───────────────

    @app.get("/api/history")
    @rate_limit
    @login_required
    def api_get_history():
        """Return the signed-in user's recent analysis records.

        Reads the existing ``uploads`` table — the same rows already written
        by every completed analysis — so no new tracking code is needed.
        """
        from storage import get_user_history

        try:
            limit = int(request.args.get("limit", 30))
        except (TypeError, ValueError):
            limit = 30
        return jsonify({"success": True, "history": get_user_history(current_user.id, limit=limit)})

    @app.delete("/api/history/<int:upload_id>")
    @rate_limit
    @login_required
    def api_delete_history(upload_id: int):
        """Delete one of the user's own analysis records."""
        from storage import delete_user_history_entry

        if not delete_user_history_entry(current_user.id, upload_id):
            return jsonify({"success": False, "error": "History entry not found."}), 404
        return jsonify({"success": True, "message": "History entry deleted."})

    # ── Career Chat Session Management (with TTL-based cleanup) ──

    @app.post("/api/career-chat")
    @rate_limit
    def api_career_chat():
        """AI Career Chat endpoint (SAHAY_AI-inspired).

        Accepts a user question and optional resume context, returns AI-generated
        career advice.        Uses Ollama / API providers when available, falls back to a
        rule-based response.
        """
        from rag_retriever import build_rag_context

        data = request.get_json(silent=True) or {}
        question = (data.get("message") or "").strip()
        session_id = (data.get("session_id") or "").strip()
        resume_text = (data.get("resume_text") or "").strip()

        if not question:
            return jsonify({"success": False, "error": "Please enter a question."}), 400

        # Clean stale sessions before looking up/creating the current one
        _cleanup_stale_career_sessions()

        # Create or retrieve session
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in _CAREER_CHAT_SESSIONS:
            _CAREER_CHAT_SESSIONS[session_id] = []

        # Track this session's last-active timestamp
        _CAREER_CHAT_LAST_ACTIVE[session_id] = time.time()

        history = _CAREER_CHAT_SESSIONS[session_id]

        # Limit history to last 10 messages to manage context window
        recent_history = history[-10:] if len(history) > 10 else history

        # Try Ollama for AI-powered response (same pipeline as Advanced mode)
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        ollama_model = os.environ.get("OLLAMA_MODEL", "llama3")
        llm_available = False
        answer = ""

        # If Ollama is running, use it (skip immediately after a recent failure so
        # the rule-based fallback answers without stalling on a dead connection)
        try:
            if is_ollama_on_cooldown():
                raise ConnectionError("Ollama skipped (recent failure)")

            system_prompt = (
                "You are a helpful AI career advisor assistant. "
                "Answer career-related questions concisely and practically. "
                "When a resume or document is included in the context, answer using "
                "its actual content first (skills, experience, education, projects) "
                "before giving general career advice. "
                "Give specific, actionable advice based on the user's resume and question."
            )

            # Build RAG-enhanced context from resume if provided
            context_parts = [system_prompt]
            if resume_text:
                rag_context, _rag_meta = build_rag_context(
                    resume_text, question, top_k=3, max_context_chars=1500, session_id=session_id
                )
                if rag_context:
                    context_parts.append(f"\n{rag_context}")
                else:
                    context_parts.append(f"\nUser's resume context:\n{resume_text[:2000]}")

            # Add recent conversation history
            if recent_history:
                context_parts.append("\nConversation history:")
                for msg in recent_history[-6:]:  # Last 6 messages for relevance
                    role_label = "User" if msg["role"] == "user" else "Assistant"
                    context_parts.append(f"{role_label}: {msg['content'][:500]}")

            context_parts.append(f"\nUser question: {question}")
            context_parts.append("\nAssistant:")
            full_prompt = "\n".join(context_parts)

            resp = requests.post(
                f"{ollama_host}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "max_length": 300},
                },
                timeout=(2, 8),
            )
            if resp.ok:
                result = resp.json()
                answer = (result.get("response") or "").strip()
                llm_available = bool(answer)
        except Exception:
            mark_ollama_unavailable()
            log.debug("Ollama not available for career chat, using fallback")

        # ── Try API Key Provider (DeepSeek / OpenAI / OpenRouter) as second LLM tier ──
        if not llm_available:
            try:
                _llm_provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
                _deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
                _openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
                _openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

                # Determine which provider to use
                _api_key = None
                _base_url = None
                _model = None

                if _llm_provider == "openrouter" and _openrouter_key:
                    _api_key = _openrouter_key
                    _base_url = "https://openrouter.ai/api/v1"
                    _model = os.environ.get("LLM_MODEL", "openai/gpt-4o")
                elif _llm_provider == "deepseek" and _deepseek_key:
                    _api_key = _deepseek_key
                    _base_url = "https://api.deepseek.com/v1"
                    _model = os.environ.get("LLM_MODEL", "deepseek-chat")
                elif _llm_provider == "openai" and _openai_key:
                    _api_key = _openai_key
                    _base_url = "https://api.openai.com/v1"
                    _model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
                elif not _llm_provider and _openrouter_key:
                    _api_key = _openrouter_key
                    _base_url = "https://openrouter.ai/api/v1"
                    _model = os.environ.get("LLM_MODEL", "openai/gpt-4o")
                elif not _llm_provider and _deepseek_key:
                    _api_key = _deepseek_key
                    _base_url = "https://api.deepseek.com/v1"
                    _model = os.environ.get("LLM_MODEL", "deepseek-chat")
                elif not _llm_provider and _openai_key:
                    _api_key = _openai_key
                    _base_url = "https://api.openai.com/v1"
                    _model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

                if _api_key and _openai_available():
                    # Build optional default headers (used by OpenRouter for analytics)
                    _default_headers: dict[str, str] = {}
                    if os.environ.get("OPENROUTER_SITE_URL"):
                        _default_headers["HTTP-Referer"] = os.environ["OPENROUTER_SITE_URL"]
                    if os.environ.get("OPENROUTER_SITE_NAME"):
                        _default_headers["X-Title"] = os.environ["OPENROUTER_SITE_NAME"]

                    import openai

                    _client = openai.OpenAI(
                        api_key=_api_key,
                        base_url=_base_url,
                        default_headers=_default_headers or None,
                    )

                    # Build message list with system prompt, resume, history, and question
                    _messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
                    if resume_text:
                        rag_context, _rag_meta = build_rag_context(
                            resume_text, question, top_k=3, max_context_chars=1500
                        )
                        _messages.append(
                            {
                                "role": "system",
                                "content": rag_context
                                if rag_context
                                else f"User's resume context:\n{resume_text[:2000]}",
                            }
                        )
                    for _msg in recent_history[-6:]:
                        _messages.append({"role": _msg["role"], "content": _msg["content"][:500]})
                    _messages.append({"role": "user", "content": question})

                    _completion = _client.chat.completions.create(
                        model=_model,
                        messages=_messages,
                        temperature=0.3,
                        max_tokens=300,
                        timeout=15,
                    )
                    _api_answer = (_completion.choices[0].message.content or "").strip()
                    if _api_answer:
                        answer = _api_answer
                        llm_available = True
                        # Resolve provider name for logging (handles auto-detection)
                        _provider_name = (
                            _llm_provider
                            or (_openrouter_key and "openrouter")
                            or (_deepseek_key and "deepseek")
                            or (_openai_key and "openai")
                            or "unknown"
                        )
                        _log_openai.info(
                            "Career chat via %s (%s), session=%s",
                            _provider_name,
                            _model,
                            session_id,
                        )
            except Exception as _llm_err:
                _log_openai.warning("API provider (%s) failed: %s", _llm_provider or "auto", _llm_err)
                _log_openai.debug("API provider not available for career chat, using rule-based fallback")

        # ── Fallback: rule-based response when no LLM is available ──
        if not llm_available:
            answer = _rule_based_career_answer(question, resume_text=resume_text, history=history)

        # Store in conversation history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

        # Trim history to prevent memory growth
        if len(history) > 50:
            _CAREER_CHAT_SESSIONS[session_id] = history[-50:]

        return jsonify(
            {
                "success": True,
                "reply": answer,
                "answer": answer,
                "session_id": session_id,
                "llm_powered": llm_available,
            }
        )

    # ── Career Chat Document Context API ─────────────────────────────────
    # Lets the chat widget accept uploaded documents (resume, cover letter,
    # etc.) so the assistant can personalise its guidance to that content.

    @app.post("/api/career-chat/context")
    @rate_limit
    @login_required
    def api_career_chat_context():
        """Extract text from an attached document to use as chat context.

        Accepts a multipart file upload (PDF, DOCX, TXT, MD, CSV, RTF, XLSX or
        an image) and returns the extracted plain text plus a summary of
        detected skills, so the front-end can feed it back into every chat
        request as ``resume_text``. Images have no extractable text; for those
        the endpoint returns a short descriptive context plus image metadata.

        Returns:
            200 JSON: {success, filename, text, char_count, is_image, skills, skill_count}
            400/413: error responses for unsupported or unreadable files.
        """
        uploaded_file = request.files.get("file")
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({"success": False, "error": "Please attach a file."}), 400

        filename = (uploaded_file.filename or "").strip()
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in _CAREER_CHAT_ALLOWED_EXTS:
            return jsonify(
                {
                    "success": False,
                    "error": "Unsupported file type. Please attach a PDF, DOCX, TXT, MD, CSV, RTF, XLSX, or an image (PNG/JPG/JPEG).",
                }
            ), 400

        # Securely persist the upload: sanitise the original name and prefix it with
        # a random UUID so files can never collide or escape the uploads directory.
        upload_dir = Path(current_app.config.get("CAREER_CHAT_UPLOAD_DIR", str(BASE_DIR / "uploads")))
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            safe_name = secure_filename(filename) or "upload"
            stored_name = f"{uuid.uuid4().hex}_{safe_name}"
            uploaded_file.save(upload_dir / stored_name)
            log.info("Saved career-chat attachment: %s", stored_name)
        except Exception:
            log.exception("Could not save career-chat attachment: %s", filename)
        uploaded_file.stream.seek(0)  # rewind so the in-memory parsers can read it

        if ext in _CAREER_CHAT_IMAGE_EXTS:
            width, height = _image_dimensions(uploaded_file)
            text = (
                f"Attached image: {filename} ({width}x{height} pixels). "
                "The user shared an image, so no text could be extracted. "
                "Acknowledge the image and offer general career or resume guidance."
            )
            is_image = True
        else:
            is_image = False
            if ext == "xlsx":
                text = _parse_spreadsheet_text(uploaded_file)
            else:
                try:
                    text = parse_resume_file(uploaded_file)
                except Exception:
                    log.exception("Could not parse chat context file: %s", filename)
                    text = ""
            text = clean_text(text)
            if not text or len(text) < 20:
                return jsonify(
                    {
                        "success": False,
                        "error": "Could not read enough text from that file. Try a PDF, DOCX, TXT, or XLSX file.",
                    }
                ), 400

        skills = extract_skills_from_text(text)
        return jsonify(
            {
                "success": True,
                "filename": filename,
                "text": text,
                "char_count": len(text),
                "is_image": is_image,
                "skills": (skills.get("all_skills") or [])[:15],
                "skill_count": skills.get("count", 0),
            }
        )

    # ── Career Chat Streaming SSE Endpoint ──────────────────────────────

    @app.post("/api/career-chat/stream")
    @rate_limit
    def api_career_chat_stream():
        """Streaming SSE endpoint for AI Career Chat.
        Accepts the same input as POST /api/career-chat but streams tokens
        back as server-sent events using the OpenRouter API."""
        data = request.get_json(silent=True) or {}
        question = (data.get("message") or "").strip()
        session_id = (data.get("session_id") or "").strip()
        resume_text = (data.get("resume_text") or "").strip()

        if not question:
            return jsonify({"success": False, "error": "Please enter a question."}), 400

        _cleanup_stale_career_sessions()

        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in _CAREER_CHAT_SESSIONS:
            _CAREER_CHAT_SESSIONS[session_id] = []

        _CAREER_CHAT_LAST_ACTIVE[session_id] = time.time()

        history = _CAREER_CHAT_SESSIONS[session_id]
        recent_history = history[-10:] if len(history) > 10 else history

        system_prompt = (
            "You are Prayash, a helpful AI career advisor assistant. "
            "Answer career-related questions concisely and practically. "
            "When a resume or document is included in the context, answer using "
            "its actual content first (skills, experience, education, projects) "
            "before giving general career advice. "
            "Give specific, actionable advice based on the user's resume and question."
        )

        def generate():
            from rag_retriever import build_rag_context

            def sse(event, data_dict):
                yield f"event: {event}\ndata: {json.dumps(data_dict)}\n\n"

            full_answer = ""

            try:
                # Try OpenRouter via OpenAI SDK with streaming
                _api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
                _llm_provider = os.environ.get("LLM_PROVIDER", "").strip().lower()

                # Check for a configured key/provider before touching the SDK —
                # _openai_available() imports the (heavy) openai package lazily.
                if (_llm_provider or _api_key) and _openai_available():
                    _base_url = "https://openrouter.ai/api/v1"
                    _model = os.environ.get("LLM_MODEL", "anthropic/claude-opus-5-fast")

                    _default_headers = {}
                    if os.environ.get("OPENROUTER_SITE_URL"):
                        _default_headers["HTTP-Referer"] = os.environ["OPENROUTER_SITE_URL"]
                    if os.environ.get("OPENROUTER_SITE_NAME"):
                        _default_headers["X-Title"] = os.environ["OPENROUTER_SITE_NAME"]

                    import openai

                    _client = openai.OpenAI(
                        api_key=_api_key,
                        base_url=_base_url,
                        default_headers=_default_headers or None,
                    )

                    _messages = [{"role": "system", "content": system_prompt}]
                    if resume_text:
                        rag_context, _rag_meta = build_rag_context(
                            resume_text, question, top_k=3, max_context_chars=1500
                        )
                        _messages.append(
                            {
                                "role": "system",
                                "content": rag_context
                                if rag_context
                                else f"User's resume context:\n{resume_text[:2000]}",
                            }
                        )
                    for _msg in recent_history[-6:]:
                        _messages.append({"role": _msg["role"], "content": _msg["content"][:500]})
                    _messages.append({"role": "user", "content": question})

                    yield from sse("meta", {"session_id": session_id})

                    _stream = _client.chat.completions.create(
                        model=_model,
                        messages=_messages,
                        temperature=0.3,
                        max_tokens=400,
                        stream=True,
                        timeout=15,
                    )

                    for _chunk in _stream:
                        _delta = _chunk.choices[0].delta if _chunk.choices else None
                        if _delta and _delta.content:
                            full_answer += _delta.content
                            yield from sse("token", {"content": _delta.content})

                    yield from sse("done", {"answer": full_answer, "session_id": session_id})
                    log.info("Streaming career chat via OpenRouter (%s), session=%s", _model, session_id)
                    return

            except Exception as exc:
                log.warning("Streaming career chat failed: %s", exc)

            # Fallback: rule-based answer (sent as one event)
            full_answer = _rule_based_career_answer(question, resume_text=resume_text, history=recent_history)

            yield from sse("meta", {"session_id": session_id})
            yield from sse("token", {"content": full_answer})
            yield from sse("done", {"answer": full_answer, "session_id": session_id})

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/insights-summary")
    @rate_limit
    def api_insights_summary():
        """Get a full insights summary: parsed data, career paths, roadmap."""
        data = request.get_json(silent=True) if request.is_json else {}
        resume_text = (request.form.get("resume_text") or data.get("resume_text", "")).strip()
        if not resume_text or len(resume_text) < 20:
            return jsonify({"success": False, "error": "Please provide at least 20 characters of resume text."}), 400

        parsed = parse_resume_enhanced(resume_text)
        quality = analyze_resume_quality(parsed)
        skills = extract_skills_from_text(resume_text)
        paths = suggest_career_paths(resume_text)
        roadmap = generate_learning_roadmap(resume_text)
        total_weeks = sum(
            int(s.get("duration", "0").split("-")[0] or "0") for area in roadmap for s in area.get("stages", [])
        )
        skill_categories = skills.get("by_category", {})
        top_skills_sample = skills.get("all_skills", [])[:20]

        return jsonify(
            {
                "success": True,
                "skills": {
                    "count": skills.get("count", 0),
                    "categories": len(skill_categories),
                    "by_category": skill_categories,
                    "top_skills": top_skills_sample,
                },
                "quality": {
                    "score": quality.get("completeness_score", 0),
                    "grade": quality.get("grade", "N/A"),
                    "strengths": quality.get("strengths", []),
                    "missing": quality.get("missing_sections", []),
                },
                "parsed": {
                    "sections_found": parsed.get("sections_found", []),
                    "contact": parsed.get("contact", {}),
                    "education": parsed.get("education", []),
                    "experience": parsed.get("experience", []),
                    "projects": parsed.get("projects", []),
                    "certifications": parsed.get("certifications", []),
                    "achievements": parsed.get("achievements", []),
                },
                "career_paths": {"paths": paths, "total": len(paths)},
                "learning_roadmap": {"roadmap": roadmap, "areas": len(roadmap), "total_weeks": total_weeks},
            }
        )

    @app.post("/api/compare")
    @rate_limit
    def api_compare():
        payload = request.get_json(silent=True) if request.is_json else {}
        a = (request.form.get("text_a") or (payload or {}).get("text_a", "")).strip()
        b = (request.form.get("text_b") or (payload or {}).get("text_b", "")).strip()
        mode = request.form.get("mode") or (payload or {}).get("mode", "standard") or "standard"
        if mode not in {"standard", "advanced"}:
            mode = "standard"
        if not a or not b:
            return jsonify({"success": False, "error": "Both texts required"}), 400
        try:
            ra = _run_analysis_workflow(a, mode)
            rb = _run_analysis_workflow(b, mode)
            return jsonify(
                {
                    "success": True,
                    "mode": mode,
                    "risk_delta": round(abs(ra["risk_score"] - rb["risk_score"]), 3),
                    "risk_a": ra["risk_score"],
                    "risk_b": rb["risk_score"],
                    "label_a": ra["risk_label"],
                    "label_b": rb["risk_label"],
                    "top_role_a": (ra.get("top_roles") or [{}])[0].get("job_role", "N/A"),
                    "top_role_b": (rb.get("top_roles") or [{}])[0].get("job_role", "N/A"),
                    "riasec_a": ra.get("riasec", {}).get("primary", "N/A"),
                    "riasec_b": rb.get("riasec", {}).get("primary", "N/A"),
                }
            )
        except Exception as exc:
            log.exception("Comparison failed")
            return jsonify({"success": False, "error": str(exc)}), 500


    @app.post("/api/export")
    @rate_limit
    def api_export():
        """Render the printable career report (templates/report.html) for the
        analysis payload returned by /api/analyze and /api/analyze-stream.

        The front-end's "Export PDF" button (static/script.js) posts
        ``{"analysis": <lastAnalysis>}`` and opens the returned HTML in a
        print dialog. This endpoint used to be missing, so every export
        attempt failed with a 404.
        """
        payload = request.get_json(silent=True) if request.is_json else {}
        analysis = (payload or {}).get("analysis")
        if not isinstance(analysis, dict) or not analysis:
            return jsonify({"success": False, "error": "No analysis to export."}), 400
        try:
            html = render_template("report.html", analysis=analysis)
            return jsonify({"success": True, "html": html})
        except Exception as exc:
            log.exception("Report export failed")
            return jsonify({"success": False, "error": str(exc)}), 500


# ── Career Chat helpers (module-level so tests can reach them) ──────

_CAREER_CHAT_ALLOWED_EXTS = {"pdf", "docx", "txt", "md", "csv", "rtf", "xlsx", "png", "jpg", "jpeg"}
_CAREER_CHAT_IMAGE_EXTS = {"png", "jpg", "jpeg"}

_CAREER_CHAT_SESSIONS: dict[str, list[dict[str, str]]] = {}
"""In-memory conversation history per session ID.
Structure: {session_id: [{"role": "user"|"assistant", "content": str}, ...]}"""

_CAREER_CHAT_LAST_ACTIVE: dict[str, float] = {}
"""Tracks the last active timestamp (time.time) for each session ID.
Used by _cleanup_stale_career_sessions() to evict idle sessions."""

_CAREER_CHAT_TTL = 1800  # 30 minutes in seconds


def _cleanup_stale_career_sessions() -> None:
    """Remove sessions that have been idle for longer than _CAREER_CHAT_TTL.
    Call this before any career-chat session lookup to keep the in-memory
    store from accumulating stale entries."""
    now = time.time()
    stale = [sid for sid, last_active in _CAREER_CHAT_LAST_ACTIVE.items() if now - last_active > _CAREER_CHAT_TTL]
    for sid in stale:
        _CAREER_CHAT_SESSIONS.pop(sid, None)
        _CAREER_CHAT_LAST_ACTIVE.pop(sid, None)
    if stale:
        log.debug("Cleaned up %d stale career chat session(s)", len(stale))


def _image_dimensions(uploaded_file) -> tuple[int, int]:
    """Return (width, height) for an uploaded image, falling back to (0, 0)."""
    try:
        from PIL import Image

        uploaded_file.stream.seek(0)
        with Image.open(uploaded_file.stream) as img:
            return img.size
    except Exception:
        log.exception("Could not read image dimensions for chat context")
        return 0, 0


def _parse_spreadsheet_text(uploaded_file) -> str:
    """Convert an Excel workbook into readable text tables using pandas/openpyxl."""
    try:
        import pandas as pd

        uploaded_file.stream.seek(0)
        sheets = pd.read_excel(uploaded_file.stream, sheet_name=None)
    except Exception:
        log.exception("Could not parse spreadsheet chat context file")
        return ""

    parts: list[str] = []
    for sheet_name, frame in sheets.items():
        parts.append(f"Sheet: {sheet_name}")
        parts.append(frame.to_string(index=False))
    return "\n\n".join(parts)


def _rule_based_career_answer(question: str, resume_text: str = "", history: list[dict[str, str]] | None = None) -> str:
    """Rule-based fallback answer for the career chat when no LLM is available.

    Order matters — more specific topics are matched first so that, e.g.,
    "Tips for job interviews?" returns interview advice rather than the generic
    job-search answer, and "Help me plan my career path" gets dedicated
    career-path guidance instead of the same job-search text.

    When a resume (or other attached document) is available its extracted
    skills are woven into the answer so the guidance is personalised to the
    user instead of returning the same generic text every time.
    """
    q = (question or "").lower()
    resume_text = (resume_text or "").strip()

    def has_any(keywords: list[str]) -> bool:
        # Word-boundary prefix match: "skill" matches "skills" and "learning"
        # matches "learn", but "earn" never matches inside "learn" or "bearn".
        return any(re.search(rf"\b{re.escape(kw)}", q) for kw in keywords)

    # ── Resume-aware personalisation ──
    skills = extract_skills_from_text(resume_text) if len(resume_text) >= 20 else None
    skill_names = (skills.get("all_skills") or [])[:8] if skills else []
    top_skills = ", ".join(skill_names) if skill_names else ""

    # ── Answer from the attached document (factual Q&A) ──
    # When a file is attached, parse it once so questions about education,
    # experience, projects, certifications, and the profile summary are
    # answered from the document's actual content instead of generic advice.
    parsed_doc = None
    if len(resume_text) >= 20:
        try:
            parsed_doc = parse_resume_enhanced(resume_text)
        except Exception:
            parsed_doc = None

    if parsed_doc:

        def _bullet_lines(items: list) -> str:
            lines = [str(x).strip() for x in items if str(x).strip()]
            return "\n".join(f"• {line}" for line in lines[:6])

        # Fallback for documents without clearly-separated section headers:
        # scan the raw text for the sentences that actually mention the topic.
        def _snippet(keywords: list[str], limit: int = 4) -> str:
            hits: list[str] = []
            for part in re.split(r"(?<=[.!?])\s+", resume_text):
                p = part.strip()
                if not p or len(p) < 12:
                    continue
                if any(re.search(rf"\b{re.escape(kw)}", p, re.IGNORECASE) for kw in keywords) and p not in hits:
                    hits.append(p)
                if len(hits) >= limit:
                    break
            return "\n".join(f"• {h}" for h in hits)

        edu = _bullet_lines(parsed_doc.get("education") or [])
        exp = _bullet_lines(parsed_doc.get("experience") or [])
        proj = _bullet_lines(parsed_doc.get("projects") or [])
        cert = _bullet_lines(parsed_doc.get("certifications") or [])
        # Raw-text fallbacks for when section parsing came up empty
        if not edu:
            edu = _snippet(
                ["education", "degree", "university", "college", "school", "bachelor", "master", "phd", "bsc", "msc"]
            )
        if not exp:
            exp = _snippet(
                ["experience", "worked", "work at", "employment", "intern", "role at", "led", "built", "developed"]
            )
        if not proj:
            proj = _snippet(["project", "portfolio", "dashboard", "app", "platform", "system"])
        if not cert:
            cert = _snippet(["certif", "license", "course", "training", "credential"])

        # Education questions
        if has_any(["education", "degree", "university", "college", "school", "academic"]):
            if edu:
                return f"🎓 From your attached document, here's the education I found:\n{edu}\n\nWant me to suggest roles that build on this background?"
            return "Your attached document doesn't show a clear education section. Try asking about your skills or experience instead."

        # Experience / work-history questions
        if has_any(["experience", "work", "employment", "job history", "what have you done"]):
            if exp:
                return f"💼 From your attached document, here's the experience I found:\n{exp}\n\nAsk me how to position this for your next application."
            if edu:
                return f"Your attached document doesn't show a clear experience section, but your education includes:\n{edu}"
            return "Your attached document doesn't show a clear experience section. Try asking about your skills or education."

        # Projects / portfolio questions
        if has_any(["project", "portfolio", "built", "created"]):
            if proj:
                return f"🛠️ From your attached document, here are the projects I found:\n{proj}\n\nWant tips on presenting these in interviews?"
            if exp:
                return f"Your attached document doesn't list a dedicated projects section, but your experience includes:\n{exp}"
            return "Your attached document doesn't list any projects. Try asking about your skills or experience."

        # Certification questions
        if has_any(["certif", "license", "credential"]):
            if cert:
                return f"📜 From your attached document, here are the certifications I found:\n{cert}"
            return "Your attached document doesn't show any certifications. Try asking about your education or skills."

        # Profile summary / tell-me-about questions
        if has_any(
            ["summarize", "summary", "tell me about", "overview", "what's in", "about my resume", "about this resume"]
        ):
            parts = []
            if edu:
                parts.append(f"Education:\n{edu}")
            if exp:
                parts.append(f"Experience:\n{exp}")
            if proj:
                parts.append(f"Projects:\n{proj}")
            if top_skills:
                parts.append(f"Key skills: {top_skills}.")
            if parts:
                return (
                    "📄 Here's a summary of your attached document:\n\n"
                    + "\n\n".join(parts)
                    + "\n\nWhat would you like to focus on next?"
                )
            return "I've read your attached document. Ask me about your skills, roles that fit, or what to learn next."

        # Role-fit questions — rank careers using the actual document
        if has_any(
            [
                "roles fit",
                "which roles",
                "what roles",
                "role match",
                "best fit",
                "fit my profile",
                "suitable role",
                "career options",
            ]
        ):
            try:
                paths = suggest_career_paths(resume_text)[:5]
            except Exception:
                paths = []
            if paths:
                lines = [f"• {p.get('role')} — {p.get('score', 0):.0f}% match" for p in paths]
                return (
                    "🎯 Based on your attached document, here are the roles that fit your profile:\n"
                    + "\n".join(lines)
                    + (f"\n\nTop skills driving these matches: {top_skills}." if top_skills else "")
                    + "\n\nAsk me for a learning roadmap toward any of these."
                )
            if top_skills:
                return f"Based on your attached document, your strongest skills are {top_skills}. Tell me your target role and I'll suggest how to position yourself."

    if has_any(["interview", "mock", "crack", "behavioral"]):
        if top_skills:
            return (
                f"Great — to prep for interviews with your profile ({top_skills}): "
                "1) Review common questions for your target roles, "
                "2) Prepare STAR-format stories that showcase those exact skills, "
                "3) Practice technical questions with LeetCode or HackerRank, "
                "4) Research each company's culture and recent news, "
                "5) Run mock interviews with friends or platforms like Pramp, "
                "6) Prepare thoughtful questions to ask the interviewer."
            )
        return (
            "To prepare for interviews: 1) Review common questions for your target role, "
            "2) Prepare STAR-format stories from your experience, "
            "3) Practice technical questions with platforms like LeetCode or HackerRank, "
            "4) Research the company's culture and recent news, "
            "5) Do mock interviews with friends or platforms like Pramp, "
            "6) Prepare thoughtful questions to ask the interviewer."
        )
    if has_any(["salary", "pay", "earn", "compensation", "negotiate"]):
        if top_skills:
            return (
                f"For roles that use {top_skills}, salary ranges vary by location, "
                "experience, and industry. Use Glassdoor, Levels.fyi, and LinkedIn Salary "
                "to benchmark market rates for your target titles. Negotiate total "
                "compensation — base salary, equity, bonus, and benefits — not just the number."
            )
        return (
            "Salary ranges vary by location, experience, and industry. "
            "Use sites like Glassdoor, Levels.fyi, and LinkedIn Salary to research "
            "market rates for your target roles. Consider total compensation including "
            "benefits, equity, and bonuses."
        )
    if has_any(["resume", "cv", "ats", "achievement"]):
        if top_skills:
            return (
                f"To strengthen your resume around {top_skills}: 1) Add specific, "
                "quantifiable achievements that prove those skills, "
                "2) Mirror the keywords from target job descriptions, "
                "3) Put the strongest skills in a clear professional summary, "
                "4) Keep the layout clean and ATS-friendly (PDF recommended), "
                "5) Make sure your contact info (email, LinkedIn) is visible."
            )
        return (
            "To improve your resume: 1) Add specific, quantifiable achievements, "
            "2) Use keywords from target job descriptions, "
            "3) Include a professional summary section, "
            "4) Keep your format clean and ATS-friendly (PDF recommended), "
            "5) Ensure your contact info (email, LinkedIn) is clearly visible."
        )
    if has_any(["career", "path", "roadmap", "growth", "goal"]):
        if top_skills:
            return (
                f"Based on your skills ({top_skills}), here's a career map: "
                "1) Compare your skills against job postings to pick 2-3 target roles, "
                "2) List the skills each role asks for that you don't have yet, "
                "3) Follow a learning roadmap to close the biggest gaps first, "
                "4) Set 3-month and 12-month milestones with measurable outcomes, "
                "5) Re-check your progress after each milestone and adjust. "
                "Want me to suggest courses or roles to explore next?"
            )
        return (
            "Let's map out your career path: 1) Review the top role matches from your "
            "analysis report to see where your profile fits today, "
            "2) Identify the skills you'll need for your target role, "
            "3) Follow the learning roadmap in your report to close skill gaps, "
            "4) Set 3-month and 12-month goals with measurable milestones, "
            "5) Re-run your analysis after each milestone to track progress. "
            "Want me to suggest specific courses or roles to explore?"
        )
    if has_any(["job", "apply", "position", "hiring", "search", "role"]):
        if top_skills:
            return (
                f"For your job search, lead with your strongest skills ({top_skills}). "
                "Use them as search keywords for alerts and applications, tailor your "
                "resume summary to the target role, and track repeated requirements "
                "across 10 recent postings before you apply."
            )
        return (
            "For job searching, use your top role matches from the analysis as search keywords. "
            "Tailor your resume summary to highlight the skills most relevant to your target role. "
            "Consider setting up job alerts for your strongest matching positions."
        )
    if has_any(["skill", "learn", "study", "course", "improve"]):
        if top_skills:
            return (
                f"You already have {top_skills}. To grow further: 1) Compare a current "
                "job posting in your target field against these skills and note the gaps, "
                "2) Pick one missing skill and complete a short course on it this month, "
                "3) Practice with small projects so the skill sticks, "
                "4) Add the new skill to your resume once you've used it. "
                "Attach your resume and ask me which skill to prioritize next."
            )
        return (
            "Based on your resume analysis, I recommend focusing on skill development. "
            "Check the learning roadmap in your analysis report for personalized course recommendations. "
            "Start with the top suggested Coursera courses for your skill gaps."
        )
    if has_any(["hello", "hi", "hey", "help", "about"]):
        return (
            "Hi! I'm your AI career assistant. I can help with:\n"
            "• Skill development and learning recommendations\n"
            "• Job search strategies and career advice\n"
            "• Resume improvement tips\n"
            "• Interview preparation\n"
            "• Salary and compensation questions\n"
            "📎 Tip: click the paperclip to attach your resume (PDF, DOCX, or TXT) "
            "so my answers are personalized to your profile.\n"
            "What would you like to know?"
        )
    if top_skills:
        return (
            f"That's a good question. Looking at your profile, I can see skills like "
            f"{top_skills}. If you tell me your target role, I can suggest which of these "
            "to highlight and which to learn next. Try asking: 'What roles fit my skills?' "
            "or 'What should I learn next for a specific career?'"
        )
    return (
        "That's a great question! For more personalized advice, click the 📎 paperclip "
        "to attach your resume — I'll tailor my guidance to your skills and profile. "
        "You can also run a resume analysis first for a full role match and learning roadmap."
    )
