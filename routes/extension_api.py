"""Additive API routes for the new Pandas/Gemini/RapidAPI services.

Registered alongside existing routes; does NOT replace any working endpoint.
All calls remain server-side; no API keys are exposed to the browser.
"""

from __future__ import annotations

from flask import jsonify, request
from flask_login import login_required

from services.gemini_service import GeminiService
from services.job_api_service import JobAPIService
from services.roadmap_service import generate_roadmap


def register_extension_api(app) -> None:
    job_service = JobAPIService()
    gemini = GeminiService()

    @app.get("/api/jobs/live")
    @login_required
    def live_jobs():
        role = (request.args.get("role") or "").strip()
        location = (request.args.get("location") or "").strip()
        page = request.args.get("page", "1")
        if not role:
            return jsonify({"success": False, "error": {"code": "MISSING_ROLE", "message": "role is required"}}), 400
        if not job_service.available():
            return jsonify({"success": True, "data": {"jobs": []}, "message": "Live job search is temporarily unavailable."})
        try:
            page_num = max(int(page), 1)
        except ValueError:
            page_num = 1
        jobs = job_service.search_jobs(role=role, location=location or None, page=page_num)
        return jsonify({"success": True, "data": {"jobs": jobs}, "message": "OK"})

    @app.post("/api/roadmap/generate")
    @login_required
    def roadmap_generate():
        payload = request.get_json(silent=True) or {}
        target_role = (payload.get("target_role") or "").strip()
        skills = payload.get("skills") or []
        if not isinstance(skills, list):
            skills = []
        if not target_role:
            return jsonify({"success": False, "error": {"code": "MISSING_ROLE", "message": "target_role is required"}}), 400
        try:
            roadmap = generate_roadmap(skills, target_role)
        except ValueError as exc:
            return jsonify({"success": False, "error": {"code": "UNKNOWN_ROLE", "message": str(exc)}}), 422
        # Optional Gemini personalization layer — deterministic roadmap stays primary.
        explanation = gemini.personalize_roadmap(roadmap, user_profile=str(payload.get("user_profile") or ""))
        if explanation:
            roadmap["ai_explanation"] = explanation
        else:
            roadmap["ai_explanation"] = None
            roadmap["ai_note"] = "AI explanation temporarily unavailable."
        return jsonify({"success": True, "data": roadmap, "message": "Roadmap generated"})

    @app.post("/api/ai/resume-feedback")
    @login_required
    def resume_feedback():
        payload = request.get_json(silent=True) or {}
        resume_text = (payload.get("resume_text") or "").strip()
        skills = payload.get("skills") or []
        ats_score = payload.get("ats_score")
        if not resume_text:
            return jsonify({"success": False, "error": {"code": "MISSING_RESUME", "message": "resume_text is required"}}), 400
        analysis = gemini.analyze_resume(resume_text, skills if isinstance(skills, list) else [], ats_score if isinstance(ats_score, int) else None)
        if analysis is None:
            return jsonify({
                "success": True,
                "data": {"strengths": [], "weaknesses": [], "improvements": [], "suggested_careers": [], "recommended_skills": []},
                "message": "AI explanation temporarily unavailable.",
            })
        return jsonify({"success": True, "data": analysis, "message": "OK"})
