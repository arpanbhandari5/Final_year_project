"""
Prayash — Shared Extensions
============================
Centralises the Flask extensions so that blueprints, models and services
import one canonical instance instead of constructing their own copies.

Each extension is created here *without* an application and is bound later
via ``init_app(app)`` in the application factory (see ``app.py``).
"""

from __future__ import annotations

from flask_compress import Compress
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
mail = Mail()
csrf = CSRFProtect()
login_manager = LoginManager()
compress = Compress()
