"""
Prayash — Admin Routes
======================
Admin dashboard page, admin JSON API, and admin logout.

Kept as plain ``@app.route`` functions (registered via ``register_admin``)
so endpoint names (``admin_dashboard``, …) stay as templates expect them.
"""

from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from storage import authenticate_user, get_all_users, get_detailed_metrics


def register_admin(app) -> None:
    """Register the admin routes on *app*."""

    @app.route("/admin", methods=["GET", "POST"])
    @login_required
    def admin_dashboard() -> str:
        if request.method == "POST":
            username = (request.form.get("username") or "").strip().lower()
            password = request.form.get("password") or ""
            user = authenticate_user(username, password)
            if user and getattr(user, "is_admin_email", False):
                login_user(user, remember=True)
                return redirect(url_for("admin_dashboard"))
            return render_template(
                "admin.html",
                title="Admin | Prayash",
                active_page="admin",
                requires_login=True,
                login_error="Invalid admin credentials.",
                metrics={},
                chart_data=None,
            )

        if not getattr(current_user, "is_admin_email", False):
            return render_template(
                "admin.html",
                title="Admin | Prayash",
                active_page="admin",
                requires_login=True,
                login_error=None,
                metrics={},
                chart_data=None,
            )

        metrics = get_detailed_metrics()
        chart_data = {
            "modeLabels": ["Standard", "Advanced"],
            "modeValues": [metrics["mode_counts"]["standard"], metrics["mode_counts"]["advanced"]],
            "riskLabels": ["Low", "Moderate", "Elevated"],
            "riskValues": [
                metrics["risk_buckets"]["low"],
                metrics["risk_buckets"]["moderate"],
                metrics["risk_buckets"]["elevated"],
            ],
        }
        users = get_all_users()
        return render_template(
            "admin.html",
            title="Admin | Prayash",
            active_page="admin",
            requires_login=False,
            metrics=metrics,
            chart_data=chart_data,
            users=users,
        )

    @app.get("/api/admin/users")
    @login_required
    def api_admin_users():
        """Return all users for the admin panel (JSON)."""
        if not getattr(current_user, "is_admin_email", False):
            return jsonify({"success": False, "error": "Admin access required."}), 403
        users = get_all_users()
        user_list = []
        for u in users:
            user_list.append(
                {
                    "id": u.id,
                    "email": u.email,
                    "username": u.username,
                    "full_name": u.full_name,
                    "role": u.role,
                    "email_verified": u.email_verified,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                }
            )
        verified = sum(1 for u in users if u.email_verified)
        return jsonify(
            {
                "success": True,
                "users": user_list,
                "total": len(users),
                "verified": verified,
                "unverified": len(users) - verified,
            }
        )

    @app.post("/admin/logout")
    @login_required
    def admin_logout():
        logout_user()
        return redirect(url_for("login"))
