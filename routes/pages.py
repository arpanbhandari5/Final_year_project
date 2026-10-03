"""
Prayash — Public Page Routes
=============================
Static / informational pages plus the authenticated workspace page.

Kept as plain ``@app.route`` functions (registered via ``register_pages``)
so their endpoint names (``index``, ``workspace``, ``methodology`` …) stay
exactly as templates and ``url_for`` expect them.
"""

from __future__ import annotations

import logging

from flask import render_template, request
from flask_login import login_required

from utils import is_valid_email

log = logging.getLogger("prayash.pages")


def register_pages(app) -> None:
    """Register the informational page routes on *app*."""

    @app.get("/")
    def index() -> str:
        return render_template("index.html", active_page="home", title="Prayash: Learning for better future")

    @app.get("/workspace")
    @login_required
    def workspace() -> str:
        """The authenticated workspace IS the AI Career Advisor dashboard.

        Every "Workspace" link in the UI (navbar user menu, footer, and the
        post-login landing URL) points at this endpoint, so it serves the
        AI Career Advisor dashboard (templates/workspace.html) with the
        grouped sidebar (Dashboard / Analysis / Career / Tools / Account).
        The legacy guided-flow app remains available separately at /career.
        """
        return render_template("workspace.html", active_page="workspace", title="Workspace | Prayash")

    @app.get("/workspace/skills-gap")
    @login_required
    def skills_gap() -> str:
        """Dedicated skills gap analysis page (SAHAY_AI-inspired)."""
        return render_template("skills_gap.html", active_page="workspace", title="Skills Gap Analysis | Prayash")

    @app.get("/methodology")
    def methodology() -> str:
        return render_template("methodology.html", active_page="methodology", title="Methodology | Prayash")

    @app.get("/privacy")
    def privacy() -> str:
        return render_template("privacy.html", active_page="privacy", title="Privacy | Prayash")

    @app.get("/insights")
    def insights() -> str:
        return render_template("insights.html", active_page="insights", title="Insights | Prayash")

    @app.get("/performance")
    def performance() -> str:
        """RAG pipeline performance monitoring page.

        SAHAY_AI-inspired: mirrors their ``/performance`` view which reports
        RAG cache status, model info, and response metrics.
        """
        return render_template("performance.html", active_page="performance", title="Performance | Prayash")

    @app.get("/career")
    def career_analysis() -> str:
        return render_template("career.html", active_page="career", title="Career Analysis | Prayash")

    @app.get("/career-advisor")
    @login_required
    def career_advisor() -> str:
        """Standalone AI Career Advisor dashboard (single-page, connected pipeline).

        Distinct from /workspace (the authenticated dashboard) and /career
        (the legacy guided flow). Uses its own scoped assets:
        templates/career_advisor.html + static/career-advisor.{css,js}
        Several advisor endpoints (/api/skills-gap/*, /api/career-chat/context)
        are login-required, so the page itself requires auth for consistency.
        """
        return render_template("career_advisor.html", active_page="career", title="AI Career Advisor | Prayash")

    @app.route("/partnerships", methods=["GET", "POST"])
    def partnerships() -> str:
        submitted = False
        error = None
        if request.method == "POST":
            org = (request.form.get("organization") or "").strip()
            contact = (request.form.get("contact_email") or "").strip()
            use_case = (request.form.get("use_case") or "").strip()
            if not org or not contact or not use_case:
                error = "All fields are required."
            elif not is_valid_email(contact):
                error = "Please enter a valid email address."
            else:
                log.info("Partnership inquiry: org=%s, contact=%s, use_case=%s", org, contact, use_case)
                submitted = True
        return render_template(
            "partnerships.html",
            active_page="partnerships",
            title="Partnerships | Prayash",
            submitted=submitted,
            error=error,
        )
