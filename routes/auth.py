"""
Prayash — Authentication & OAuth Routes
=======================================
Login, signup, OTP verification, password reset, logout, and OAuth
(Google / GitHub / LinkedIn) flows.

Kept as plain ``@app.route`` functions (registered via ``register_auth``)
so endpoint names (``login``, ``signup``, ``verify_otp_page``, …) stay
exactly as templates, ``url_for`` and ``login_manager.login_view`` expect.

The OAuth blueprints are created and wired to their ``oauth_authorized``
handlers here, then registered on the app by ``register_auth``.
"""

from __future__ import annotations

import logging
import os
import re

from flask import jsonify, redirect, render_template, request, session, url_for
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.github import make_github_blueprint
from flask_dance.contrib.google import make_google_blueprint
from flask_login import current_user, login_required, login_user, logout_user
from oauthlib.oauth2.rfc6749.errors import (
    MismatchingStateError,
    OAuth2Error,
)

from extensions import csrf, db
from security import (
    _LOGIN_ATTEMPT_STORE,
    _LOGIN_MAX_ATTEMPTS,
    _check_login_lockout,
    _clear_login_attempts,
    _get_login_lockout_remaining,
    _login_attempt_key,
    _otp_request_cooldown,
    _record_failed_login,
    _record_otp_request,
    rate_limit,
    validate_password_strength,
)
from storage import (
    OTP_LENGTH,
    authenticate_user,
    check_otp,
    create_oauth_user,
    create_otp,
    create_user,
    get_linked_providers,
    get_otp_attempts_remaining,
    get_user_by_email,
    get_user_by_oauth,
    get_user_by_username,
    link_oauth_account,
    invalidate_user_otps,
    mark_email_verified,
    send_email,
    unlink_oauth_account,
    update_user_password,
    verify_otp,
)
from utils import is_valid_email

log = logging.getLogger("prayash.auth")

# Optional OAuth providers - gracefully degrade when flask-dance-contrib is absent
try:
    from flask_dance.contrib.linkedin import make_linkedin_blueprint
except ImportError:
    make_linkedin_blueprint = None  # type: ignore[assignment]

# Set by register_auth() once the LinkedIn blueprint is (or isn't) built,
# so the global context processor can tell templates whether it's available.
LINKEDIN_AVAILABLE = False


def _is_dev_mode() -> bool:
    """True in development (default); False when FLASK_ENV=production.

    Used to surface the OTP code on-screen when email delivery is not
    available, so the forgot-password flow remains usable locally.
    """
    return os.environ.get("FLASK_ENV", "development") != "production"


def _oauth_is_configured(provider: str) -> bool:
    """Return True when the environment variables for *provider* are set."""
    prefix = provider.upper()
    cid = os.environ.get(f"{prefix}_OAUTH_CLIENT_ID", "")
    csec = os.environ.get(f"{prefix}_OAUTH_CLIENT_SECRET", "")
    return bool(cid and csec)


def _extract_otp_code() -> str:
    """Read the OTP code from the request.

    Prefers the JS-combined ``otp`` field but falls back to assembling the
    individual ``otp_digit_*`` fields so the form also works without JS.
    """
    otp_code = (request.form.get("otp") or "").strip()
    if otp_code:
        return otp_code
    digits = []
    for key, value in request.form.items():
        if key.startswith("otp_digit_"):
            digits.append((int(key.rsplit("_", 1)[1]), (value or "").strip()))
    digits.sort()
    return "".join(d for _, d in digits)


def _build_otp_email(purpose: str, otp_code: str) -> tuple[str, str, str]:
    """Build a professional HTML + plain-text OTP email.

    Returns ``(subject, html_body, text_body)``.
    """
    if purpose == "reset_password":
        subject = "Reset your Prayash password"
        heading = "Password Reset Request"
        intro = "We received a request to reset your password. Use this 6-digit code to continue:"
        hint = (
            "This code expires in 10 minutes. If you didn't request a password reset, you can safely ignore this email."
        )
    else:
        subject = "Verify your Prayash account"
        heading = "Verify Your Email"
        intro = "Welcome to Prayash! Use this 6-digit code to verify your email:"
        hint = "This code expires in 10 minutes. If you didn't create an account, ignore this email."

    html = f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;padding:24px;background:#0f0f14;border-radius:16px;color:#e2e8f0">
    <h2 style="color:#d3bbff;margin:0 0 16px">{heading}</h2>
    <p style="margin:0 0 8px">{intro}</p>
    <div style="font-size:36px;letter-spacing:8px;text-align:center;padding:20px;background:#1a1a24;border-radius:12px;margin:16px 0;color:#d3bbff;font-weight:bold">{otp_code}</div>
    <p style="color:#94a3b8;font-size:13px;margin:0">{hint}</p>
    </div>"""
    text = f"{heading}\n\n{intro}\n\nYour 6-digit code: {otp_code}\n\n{hint}"
    return subject, html, text


def send_otp(email: str, otp: str, purpose: str = "reset_password") -> bool:
    """Send an OTP email (email verification or password reset).

    Thin wrapper around ``_build_otp_email`` + ``send_email`` so callers only
    need the recipient and the code. Delivery is resilient: it uses Flask-Mail,
    falls back to smtplib, and finally to console logging, so the flow never
    breaks locally when SMTP credentials are absent.
    """
    subject, html_body, text_body = _build_otp_email(purpose, otp)
    return send_email(email, subject, html_body, text_body)


def _handle_forgot_password_otp() -> str:
    """Handle a forgot-password (OTP) request and render the form.

    Shared by the ``/forgot-password`` and ``/forgot-password/otp`` URLs so
    both entry points behave identically (validation, cooldown, anti-
    enumeration, and dev-mode on-screen code).
    """
    error = None
    sent = False
    email = session.get("reset_email", "")

    if request.method == "POST":
        email_input = (request.form.get("email") or "").strip().lower()
        if not email_input or not is_valid_email(email_input):
            error = "Enter a valid email address."
        else:
            # Cooldown is applied to every submission (whether or not the
            # email exists) so the form cannot be used to probe the database.
            cooldown = _otp_request_cooldown(email_input)
            if cooldown > 0:
                error = f"Please wait {cooldown} second(s) before requesting another code."
            else:
                user = get_user_by_email(email_input)
                _record_otp_request(email_input)
                if user:
                    otp = create_otp(user, purpose="reset_password")
                    send_otp(user.email, otp.otp, purpose="reset_password")
                    session["reset_email"] = user.email
                    # A new code invalidates any earlier verification from a
                    # previous (possibly abandoned) reset attempt.
                    session.pop("otp_verified", None)
                    email = user.email
                # Always show success to prevent email enumeration
                sent = True

    return render_template(
        "forgot_password.html",
        active_page="",
        title="Forgot Password | Prayash",
        error=error,
        sent=sent,
        email=email if sent else "",
    )


def register_auth(app) -> None:
    """Register the authentication routes and OAuth blueprints on *app*."""

    # ── OAuth Blueprints ────────────────────────────────────────────
    # Google OAuth: Requires GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env
    #   Register redirect URI in Google Cloud Console:
    #     - http://localhost:5000/login/google/authorized
    #     - http://127.0.0.1:5000/login/google/authorized
    # GitHub OAuth: Requires GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET in .env
    #   Register callback URL in GitHub OAuth App:
    #     - http://localhost:5000/login/github/authorized
    # LinkedIn OAuth: Requires LINKEDIN_OAUTH_CLIENT_ID and LINKEDIN_OAUTH_CLIENT_SECRET in .env
    #   Register redirect URI in LinkedIn Developer Console
    # Microsoft OAuth: NOT IMPLEMENTED (no blueprint registered)
    google_bp = make_google_blueprint(
        client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        # Use the full URL scopes exactly as Google returns them.  The short
        # forms ("email profile openid") cause oauthlib to raise a
        # "Scope has changed" Warning exception when the token response's
        # scope does not match the requested scope string.
        scope=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
        redirect_to="google_login_callback",
    )
    github_bp = make_github_blueprint(
        client_id=os.environ.get("GITHUB_OAUTH_CLIENT_ID", ""),
        client_secret=os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", ""),
        redirect_to="github_login_callback",
    )

    app.register_blueprint(google_bp, url_prefix="/login")
    app.register_blueprint(github_bp, url_prefix="/login")

    # ── LinkedIn OAuth (only if flask-dance contrib supports it) ──
    linkedin_bp = None
    if make_linkedin_blueprint is not None:
        linkedin_bp = make_linkedin_blueprint(
            client_id=os.environ.get("LINKEDIN_OAUTH_CLIENT_ID", ""),
            client_secret=os.environ.get("LINKEDIN_OAUTH_CLIENT_SECRET", ""),
            scope=["r_liteprofile", "r_emailaddress"],
            redirect_to="linkedin_login_callback",
        )
        app.register_blueprint(linkedin_bp, url_prefix="/login")

    global LINKEDIN_AVAILABLE
    LINKEDIN_AVAILABLE = linkedin_bp is not None

    # ── OAuth Authorized Handlers ─────────────────────────────────
    # ── Shared OAuth identity resolution (account linking) ──
    def _handle_oauth_identity(blueprint, token, provider: str, email: str, provider_user_id: str | None) -> bool:
        """Resolve an OAuth identity to a user, linking accounts.

        Order: (1) durable provider-identity match (oauth_accounts),
        (2) email match — attaches the identity to the existing account
        so the user keeps their password login and data, (3) create a
        new account. When the session carries an attach marker
        (oauth_attach_<provider>), the identity is attached to that
        signed-in user instead — required when the provider email
        differs from the local account email.
        """
        if not token:
            log.warning("%s OAuth failed — no token received", provider)
            return False

        # Attach flow: signed-in user explicitly attaching this provider.
        attach_user_id = session.pop(f"oauth_attach_{provider}", None)
        if attach_user_id:
            from storage import User as _User

            attach_user = db.session.get(_User, int(attach_user_id))
            if attach_user is not None:
                link_oauth_account(attach_user, provider, provider_user_id or email)
                login_user(attach_user, remember=True)
                log.info("%s OAuth attached to existing account: %s", provider, attach_user.email)
                return False

        # 1. Durable provider-identity match
        if provider_user_id:
            user = get_user_by_oauth(provider, provider_user_id)
            if user:
                login_user(user, remember=True)
                log.info("%s OAuth login (identity match): %s", provider, user.email)
                return False

        # 2. Email match — attach the provider identity to the local account
        user = get_user_by_email(email)
        if user:
            if provider_user_id:
                link_oauth_account(user, provider, provider_user_id)
            if not user.email_verified:
                mark_email_verified(user.id)
                user.email_verified = True
            login_user(user, remember=True)
            log.info("%s OAuth login (email link): %s", provider, user.email)
            return False

        # 3. New account
        user = create_oauth_user(email, provider)
        if provider_user_id:
            link_oauth_account(user, provider, provider_user_id)
        login_user(user, remember=True)
        log.info("%s OAuth login (new account): %s", provider, email)
        return False  # Prevent Flask-Dance from storing the token

    @oauth_authorized.connect_via(google_bp)
    def google_logged_in(blueprint, token):
        if not token:
            log.warning("Google OAuth failed — no token received")
            return False
        resp = blueprint.session.get("/oauth2/v3/userinfo")
        if not resp.ok:
            log.warning("Google OAuth failed — could not fetch userinfo")
            return False
        info = resp.json()
        email = info.get("email", "").strip().lower()
        if not email:
            log.warning("Google OAuth — no email in userinfo")
            return False
        return _handle_oauth_identity(blueprint, token, "google", email, info.get("sub"))

    @oauth_authorized.connect_via(github_bp)
    def github_logged_in(blueprint, token):
        if not token:
            log.warning("GitHub OAuth failed — no token received")
            return False
        resp = blueprint.session.get("/user")
        if not resp.ok:
            log.warning("GitHub OAuth failed — could not fetch user")
            return False
        info = resp.json()
        email = info.get("email", "") or info.get("login", "") + "@github.oauth"
        email = email.strip().lower()
        if not email:
            log.warning("GitHub OAuth — no email or login in response")
            return False
        # GitHub may not expose the primary email; try the emails endpoint if needed
        if email.endswith("@github.oauth"):
            emails_resp = blueprint.session.get("/user/emails")
            if emails_resp.ok:
                emails_data = emails_resp.json()
                for entry in emails_data:
                    if entry.get("primary") and entry.get("verified"):
                        email = entry["email"].strip().lower()
                        break
        return _handle_oauth_identity(blueprint, token, "github", email, str(info.get("id") or ""))

    if linkedin_bp is not None:

        @oauth_authorized.connect_via(linkedin_bp)
        def linkedin_logged_in(blueprint, token):
            if not token:
                log.warning("LinkedIn OAuth failed — no token received")
                return False
            try:
                # LinkedIn v2 API: /me for profile, /emailAddress for email
                resp = blueprint.session.get("/v2/me?projection=(id,localizedFirstName,localizedLastName)")
                email_resp = blueprint.session.get("/v2/emailAddress?q=members&projection=(elements*(handle~))")
                if not resp.ok:
                    log.warning("LinkedIn OAuth failed — could not fetch profile")
                    return False
                info = resp.json()
                email = ""
                if email_resp.ok:
                    email_data = email_resp.json()
                    elements = email_data.get("elements", [])
                    if elements:
                        email = elements[0].get("handle~", {}).get("emailAddress", "") or ""
                if not email:
                    # Fall back to a synthetic email if LinkedIn doesn't provide one
                    lid = info.get("id", "")
                    email = f"linkedin_{lid}@linkedin.oauth" if lid else ""
                email = email.strip().lower()
                if not email:
                    log.warning("LinkedIn OAuth — no email could be derived")
                    return False
                return _handle_oauth_identity(blueprint, token, "linkedin", email, str(info.get("id") or ""))
            except Exception as exc:
                log.warning("LinkedIn OAuth error: %s", exc)
                return False
            return False

    # ── OAuth Login Routes ──────────────────────────────────────────

    # ── OAuth error tolerance (all providers) ─────────────────────
    # Flask-Dance's /login/<provider>/authorized view raises unhandled
    # exceptions (500 + debugger page) when the provider's redirect is
    # invalid:
    #   - MismatchingStateError: session cookie lost between "Sign in with
    #     <provider>" and the callback (localhost vs 127.0.0.1 mixup,
    #     stale tab, or blocked third-party cookies)
    #   - invalid_grant / missing code: user cancelled consent, or the
    #     provider returned an error param
    # Each blueprint's authorized view is wrapped so these degrade to a
    # friendly redirect back to the login page instead of a 500.
    def _wrap_authorized(view, label: str):
        """Catch OAuth2 errors inside a flask-dance authorized view."""
        from functools import wraps

        @wraps(view)
        def wrapper(*args, **kwargs):
            try:
                return view(*args, **kwargs)
            except (MismatchingStateError, OAuth2Error) as exc:
                log.warning("%s OAuth callback error: %s", label, exc)
                return redirect(url_for("login", error=f"{label} sign-in failed or was cancelled. Please try again."))
        return wrapper

    def _register_oauth_error_tolerance(blueprint, label: str) -> None:
        authorized_key = f"{blueprint.name}.authorized"
        if authorized_key in app.view_functions:
            app.view_functions[authorized_key] = _wrap_authorized(app.view_functions[authorized_key], label)
        else:  # pragma: no cover - defensive
            log.debug("No authorized view for %s; skipping error wrap", label)

    _register_oauth_error_tolerance(google_bp, "Google")
    _register_oauth_error_tolerance(github_bp, "GitHub")
    if linkedin_bp is not None:
        _register_oauth_error_tolerance(linkedin_bp, "LinkedIn")

    # Last-resort handler: any MismatchingStateError escaping a non-wrapped
    # path still degrades to the login page instead of a 500.
    def _mismatching_state_handler(error):
        log.warning("OAuth state mismatch: %s", error)
        return redirect(url_for("login", error="Sign-in failed or was cancelled. Please try again."))

    app.register_error_handler(MismatchingStateError, _mismatching_state_handler)

    @app.get("/oauth/google")
    def google_login():
        """Redirect to Google OAuth.  Uses /oauth/ path to avoid
        conflicting with the Flask-Dance blueprint at /login/google."""
        if not _oauth_is_configured("google"):
            return redirect(
                url_for(
                    "login",
                    error="Google login is not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.",
                )
            )
        return redirect(url_for("google.login"))

    @app.get("/oauth/github")
    def github_login():
        """Redirect to GitHub OAuth."""
        if not _oauth_is_configured("github"):
            return redirect(
                url_for(
                    "login",
                    error="GitHub login is not configured. Set GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET.",
                )
            )
        return redirect(url_for("github.login"))

    @app.get("/oauth/linkedin")
    def linkedin_login():
        """Redirect to LinkedIn OAuth."""
        if linkedin_bp is None:
            return redirect(
                url_for(
                    "login",
                    error="LinkedIn login is not available. Install flask-dance[linkedin] or set LINKEDIN_OAUTH_CLIENT_ID and LINKEDIN_OAUTH_CLIENT_SECRET.",
                )
            )
        if not _oauth_is_configured("linkedin"):
            return redirect(
                url_for(
                    "login",
                    error="LinkedIn login is not configured. Set LINKEDIN_OAUTH_CLIENT_ID and LINKEDIN_OAUTH_CLIENT_SECRET.",
                )
            )
        try:
            return redirect(url_for("linkedin.login"))
        except Exception:
            return redirect(url_for("login", error="LinkedIn OAuth endpoint is unavailable."))

    # ── OAuth Callback Routes ───────────────────────────────────────

    @app.get("/login/google/callback")
    def google_login_callback():
        """Callback landing after Google OAuth completes."""
        if not current_user.is_authenticated:
            return redirect(url_for("login", error="Google login failed. Please try again."))
        return redirect(url_for("workspace"))

    @app.get("/login/github/callback")
    def github_login_callback():
        """Callback landing after GitHub OAuth completes."""
        if not current_user.is_authenticated:
            return redirect(url_for("login", error="GitHub login failed. Please try again."))
        return redirect(url_for("workspace"))

    @app.get("/login/linkedin/callback")
    def linkedin_login_callback():
        """Callback landing after LinkedIn OAuth completes."""
        if not current_user.is_authenticated:
            return redirect(url_for("login", error="LinkedIn login failed. Please try again."))
        return redirect(url_for("workspace"))

    # ── Linked Accounts (attach / detach OAuth identities) ──
    @app.post("/settings/linked-accounts/<provider>/start")
    @login_required
    @csrf.exempt  # redirects into the OAuth flow; flask-dance manages its own state
    def linked_account_start(provider: str):
        """Begin attaching an OAuth identity to the signed-in account.

        Marks the session so the oauth_authorized handler attaches the
        resulting provider identity to *this* user instead of matching
        or creating an account by email.
        """
        if provider not in {"google", "github", "linkedin"}:
            return redirect(url_for("workspace"))
        session[f"oauth_attach_{provider}"] = str(current_user.id)
        blueprint_login = {"google": "google.login", "github": "github.login", "linkedin": "linkedin.login"}[provider]
        return redirect(url_for(blueprint_login))

    @app.post("/settings/linked-accounts/<provider>/remove")
    @login_required
    @csrf.exempt  # no state change beyond removing a link row; keeps the form simple
    def linked_account_remove(provider: str):
        """Detach an OAuth identity from the signed-in account."""
        unlink_oauth_account(current_user, provider)
        return redirect(url_for("workspace"))

    # ── Local Auth Routes ───────────────────────────────────────────

    @app.route("/login", methods=["GET", "POST"])
    def login() -> str:
        error = request.args.get("error") or None
        next_url = request.args.get("next") or request.form.get("next") or url_for("workspace")
        lockout_remaining = 0

        if request.method == "POST":
            # Check brute-force lockout
            if _check_login_lockout():
                lockout_remaining = _get_login_lockout_remaining()
                error = f"Too many failed attempts. Try again in {lockout_remaining} seconds."
                log.warning("Login lockout active for key %s", _login_attempt_key())
                return render_template(
                    "auth.html",
                    mode="login",
                    active_page="login",
                    title="Login | Prayash",
                    error=error,
                    next_url=next_url,
                    lockout_remaining=lockout_remaining,
                    form_data={},
                )

            email_or_username = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            remember = request.form.get("remember") == "on"
            user = authenticate_user(email_or_username, password)

            if user:
                if not user.email_verified:
                    # Password was correct — don't count as a failed login attempt
                    # Send a new OTP and redirect to verification
                    otp = create_otp(user, purpose="verify_email")
                    send_otp(user.email, otp.otp, purpose="verify_email")
                    # Stash the email in the session so the /verify-otp handler
                    # knows which account is being verified (matches the signup flow).
                    session["verify_email"] = user.email
                    error = "Please verify your email first. A new code has been sent."
                    return render_template(
                        "verify_otp.html",
                        mode="verify_email",
                        active_page="",
                        title="Verify Email | Prayash",
                        email=user.email,
                        error=error,
                    )
                _clear_login_attempts()
                user.touch_last_login()
                login_user(user, remember=remember)
                log.info("Login successful: %s (remember=%s)", user.email, remember)
                return redirect(next_url)
            else:
                _record_failed_login()
                error = "Invalid email/username or password."
                attempts_left = _LOGIN_MAX_ATTEMPTS
                entry = _LOGIN_ATTEMPT_STORE.get(_login_attempt_key())
                if entry:
                    attempts_left = max(0, _LOGIN_MAX_ATTEMPTS - entry[0])
                if attempts_left > 0 and attempts_left <= 3:
                    error = f"Invalid credentials. {attempts_left} attempt(s) remaining."

        return render_template(
            "auth.html",
            mode="login",
            active_page="login",
            title="Login | Prayash",
            error=error,
            next_url=next_url,
            form_data={},
        )

    @app.route("/signup", methods=["GET", "POST"])
    def signup() -> str:
        error = None
        form_data = {}

        if request.method == "POST":
            full_name = (request.form.get("full_name") or "").strip()
            username = (request.form.get("username") or "").strip().lower()
            email = (request.form.get("email") or "").strip().lower()
            phone = (request.form.get("phone") or "").strip()
            password = request.form.get("password") or ""
            confirm = request.form.get("confirm_password") or ""
            terms = request.form.get("terms") == "on"

            form_data = {
                "full_name": full_name,
                "username": username,
                "email": email,
                "phone": phone,
            }

            # Server-side validation
            if not full_name or len(full_name) < 2:
                error = "Full name must be at least 2 characters."
            elif not username or len(username) < 4:
                error = "Username must be at least 4 characters."
            elif not re.match(r"^[a-zA-Z0-9_]+$", username):
                error = "Username can only contain letters, numbers, and underscores."
            elif not email or not is_valid_email(email):
                error = "Enter a valid email address."
            elif phone and not re.match(r"^[\d\s\+\-\(\)]{7,20}$", phone):
                error = "Enter a valid phone number (7-20 digits)."
            elif not terms:
                error = "You must agree to the terms & conditions."
            elif validate_password_strength(password):
                error = validate_password_strength(password)
            elif password != confirm:
                error = "Passwords do not match."
            elif get_user_by_email(email):
                error = "Email already exists. Please log in."
            elif get_user_by_username(username):
                error = "Username already taken. Please choose another."
            else:
                user = create_user(
                    email=email,
                    password=password,
                    full_name=full_name,
                    username=username,
                    phone=phone or None,
                    role="student",
                )
                # Generate OTP for email verification
                otp = create_otp(user, purpose="verify_email")
                send_otp(user.email, otp.otp, purpose="verify_email")
                log.info("New user registered: %s (username=%s)", email, username)
                # Store user email in session for verification page
                session["verify_email"] = user.email
                return redirect(url_for("verify_otp_page"))

        return render_template(
            "auth.html",
            mode="signup",
            active_page="signup",
            title="Sign Up | Prayash",
            error=error,
            form_data=form_data,
        )

    # ── OTP Verification Routes ──────────────────────────────────────

    @app.route("/verify-otp", methods=["GET", "POST"])
    @rate_limit
    def verify_otp_page():
        """Show OTP verification page and handle code submission."""
        email = session.get("verify_email", "")
        if not email:
            return redirect(url_for("signup"))

        error = None

        if request.method == "POST":
            otp_code = _extract_otp_code()
            purpose = request.form.get("purpose", "verify_email")

            if not otp_code or len(otp_code) != OTP_LENGTH or not otp_code.isdigit():
                error = "Please enter a valid 6-digit code."
            else:
                user = get_user_by_email(email)
                if not user:
                    error = "User not found."
                elif verify_otp(user, otp_code, purpose):
                    mark_email_verified(user)
                    session.pop("verify_email", None)
                    # Log the user in after successful verification
                    login_user(user, remember=True)
                    log.info("Email verified: %s", email)
                    return redirect(url_for("workspace"))
                else:
                    error = "Invalid or expired code. Please try again."

        return render_template(
            "verify_otp.html",
            mode="verify_email",
            active_page="",
            title="Verify Email | Prayash",
            email=email,
            error=error,
        )

    @app.route("/resend-otp", methods=["POST"])
    @rate_limit
    def resend_otp():
        """Resend an OTP code for email verification or password reset."""
        purpose = request.form.get("purpose", "verify_email")
        if purpose not in ("verify_email", "reset_password"):
            purpose = "verify_email"

        session_key = "reset_email" if purpose == "reset_password" else "verify_email"
        email = session.get(session_key, "")
        if not email:
            email = (request.form.get("email") or "").strip().lower()

        if not email:
            return jsonify({"success": False, "error": "Email not found."}), 400

        user = get_user_by_email(email)
        if not user:
            return jsonify({"success": False, "error": "User not found."}), 404

        cooldown = _otp_request_cooldown(email)
        if cooldown > 0:
            return jsonify(
                {
                    "success": False,
                    "error": f"Please wait {cooldown} second(s) before requesting another code.",
                }
            ), 429

        _record_otp_request(email)
        otp = create_otp(user, purpose=purpose)
        send_otp(user.email, otp.otp, purpose=purpose)

        session[session_key] = user.email
        if purpose == "reset_password":
            # Resending invalidates any prior OTP verification for this reset.
            session.pop("otp_verified", None)
        message = (
            "A new reset code has been sent."
            if purpose == "reset_password"
            else "A new verification code has been sent."
        )
        payload = {"success": True, "message": message}
        if _is_dev_mode() and purpose == "verify_email":
            # Development convenience: return the code so the front-end can show it.
            # Deliberately NOT returned for reset_password so forgot-password codes
            # are only ever delivered by email.
            payload["dev_otp"] = otp.otp
        return jsonify(payload)

    # ── Forgot Password with OTP ──

    @app.route("/forgot-password", methods=["GET", "POST"])
    @rate_limit
    def forgot_password() -> str:
        """Request a password-reset code by email (OTP)."""
        return _handle_forgot_password_otp()

    @app.route("/forgot-password/otp", methods=["GET", "POST"])
    @rate_limit
    def forgot_password_otp() -> str:
        """Request a password-reset code by email (OTP, canonical URL)."""
        return _handle_forgot_password_otp()

    @app.route("/reset-password/otp", methods=["GET", "POST"])
    @rate_limit
    def reset_password_otp():
        """Verify OTP and allow password reset."""
        error = None
        success = False
        email = session.get("reset_email", "")

        if not email:
            return redirect(url_for("forgot_password_otp"))

        user = get_user_by_email(email)
        if not user:
            session.pop("reset_email", None)
            return redirect(url_for("forgot_password_otp"))

        if request.method == "POST":
            otp_code = _extract_otp_code()
            password = request.form.get("password") or ""
            confirm = request.form.get("confirm_password") or ""
            step = request.form.get("step", "otp")

            if step == "otp":
                if not otp_code or len(otp_code) != OTP_LENGTH or not otp_code.isdigit():
                    error = "Please enter a valid 6-digit code."
                else:
                    status = check_otp(user, otp_code, "reset_password")
                    if status == "valid":
                        # OTP verified, show password form
                        session["otp_verified"] = True
                        session.pop("otp_code", None)
                        return render_template(
                            "reset_password.html",
                            active_page="",
                            title="Reset Password | Prayash",
                            error=None,
                            success=False,
                            otp_verified=True,
                            email=email,
                        )
                    elif status == "invalid":
                        remaining = get_otp_attempts_remaining(user, "reset_password")
                        if remaining > 0:
                            error = f"Incorrect code. {remaining} attempt(s) remaining."
                        else:
                            error = "Incorrect code."
                    elif status == "expired":
                        error = "This code has expired. Please request a new one."
                    elif status == "used":
                        error = "This code has already been used. Please request a new one."
                    elif status == "max_attempts":
                        error = "Too many incorrect attempts. Please request a new code."
            elif step == "password":
                if not session.get("otp_verified"):
                    error = "Please verify your code first."
                else:
                    strength_error = validate_password_strength(password)
                    if strength_error:
                        error = strength_error
                    elif password != confirm:
                        error = "Passwords do not match."
                    else:
                        update_user_password(user, password)
                        # Invalidate every outstanding reset OTP (one-time use)
                        invalidate_user_otps(user, "reset_password")
                        session.pop("reset_email", None)
                        session.pop("otp_verified", None)
                        log.info("Password reset (OTP) successful for %s", email)
                        success = True

        return render_template(
            "reset_password.html",
            active_page="",
            title="Reset Password | Prayash",
            error=error,
            success=success,
            otp_verified=session.get("otp_verified", False),
            email=email,
        )

    @app.route("/logout", methods=["GET", "POST"])
    @login_required
    @csrf.exempt
    def logout():
        user_name = current_user.email
        session.clear()  # Clear session FIRST to prevent residue after logout
        logout_user()
        log.info("User logged out: %s", user_name)
        return redirect(url_for("index"))
