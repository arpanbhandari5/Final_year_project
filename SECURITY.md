# 🔐 Prayash — Security Overview

This document describes the security controls implemented across Prayash's
authentication, session, and HTTP layers. Every control below is implemented in
code (`security.py`, `routes/auth.py`, `storage.py`, `app.py`) and — where noted
— covered by the automated test suite and live end-to-end verification.

> **Testing status:** `pytest tests/` covers signup, login, OTP, lockout,
> email fallback, and the full reset flow. Live verification (real Gmail SMTP
> delivery of OTP emails, live forgot-password walkthrough) has also been
> performed against the running server.

---

## Table of contents

1. [Password storage & hashing](#1-password-storage--hashing)
2. [Signup validation](#2-signup-validation)
3. [OTP engine](#3-otp-engine)
4. [Forgot password](#4-forgot-password)
5. [Verification & reset](#5-verification--reset)
6. [Login & brute-force protection](#6-login--brute-force-protection)
7. [Session & cookie hardening](#7-session--cookie-hardening)
8. [OAuth (Google / GitHub / LinkedIn)](#8-oauth-google--github--linkedin)
9. [Email delivery](#9-email-delivery)
10. [Global HTTP hardening](#10-global-http-hardening)
11. [Rate limiting](#11-rate-limiting)
12. [Operational notes](#12-operational-notes)
13. [Known limitations](#13-known-limitations)

---

## 1. Password storage & hashing

- ✅ **Werkzeug `generate_password_hash`** (adaptive **scrypt**/PBKDF2, per-user
  salt) — encapsulated in `User.set_password()` (`storage.py`).
- ✅ **`check_password_hash`** for verification — `User.check_password()`.
  Constant-ish time; no plaintext comparison anywhere.
- ✅ **Single touchpoint:** no route ever hashes directly. All writes go through
  `set_password` (signup, OAuth creation, password reset, seeding).
- ✅ Column is `password_hash` — never `password`; no plaintext ever stored.

## 2. Signup validation

- ✅ Full name ≥ 2 chars; username ≥ 4 chars, regex `^[a-zA-Z0-9_]+$`.
- ✅ Email format via `is_valid_email()`; duplicate email/username rejected.
- ✅ Optional phone format `[\d\s\+\-\(\)]{7,20}`; terms checkbox required.
- ✅ **Password strength:** ≥ 8 chars + uppercase + lowercase + digit + special
  (`validate_password_strength`), plus confirm-password match.
- ✅ New accounts start `email_verified=False` → forced OTP verification.
- ✅ Signup is CSRF-protected. (Not IP rate-limited — see [Known limitations](#13-known-limitations).)

## 3. OTP engine

- ✅ **Cryptographically secure** 6-digit codes via `secrets.randbelow(10)`
  (never `random`).
- ✅ **DB-backed** `VerificationOTP` table — OTPs are never stored in the
  session.
- ✅ **10-minute expiry** (`OTP_EXPIRY_MINUTES`) enforced on lookup.
- ✅ **5-attempt lockout** (`OTP_MAX_ATTEMPTS`) — wrong codes consume attempts;
  code locks at max.
- ✅ **One-time use** — `used` flag consumed on success; new requests invalidate
  previous unused codes.
- ✅ **Purpose separation** — `verify_email` vs `reset_password` codes cannot
  cross-use.
- ✅ **60s resend cooldown** per email.

## 4. Forgot password

- ✅ Email validation + normalization (strip/lowercase).
- ✅ **Anti-enumeration** — identical "sent" response for known/unknown emails.
- ✅ Cooldown + rate limiting; **dev-only on-screen OTP** (never in production —
  gated by `FLASK_ENV`).
- ✅ Session stores only `reset_email` — never the OTP itself.

## 5. Verification & reset

- ✅ `/reset-password/otp` requires a session (`reset_email`) — otherwise
  redirects back.
- ✅ **`otp_verified` gate** — the new-password form is unreachable unless a
  valid code was entered in this session.
- ✅ Distinct, user-friendly statuses for wrong / expired / used / max-attempts
  codes.
- ✅ Password strength + confirm validation on the new password.
- ✅ All outstanding reset OTPs invalidated after success; session cleaned.

## 6. Login & brute-force protection

- ✅ Email **or** username lookup; `is_active` filter blocks disabled accounts.
- ✅ Correct password + unverified email → OTP verification redirect (never
  counted as a failure).
- ✅ **Brute-force lockout:** 5 failures / 5 min **per IP+email combo**
  (`_LOGIN_ATTEMPT_STORE`), checked **before** any DB work.
- ✅ Attempt-countdown feedback shown when ≤ 3 attempts remain.
- ✅ Failure counter **cleared on successful login**; `last_login` updated.
- ✅ `remember` → 7-day permanent session; otherwise session cookie only.
- ✅ CSRF enforced on every POST; `next_url` preserved across login.
- ✅ Lockout covered by unit tests (`tests/test_login_lockout.py`) — including
  per-email and per-IP scoping, window expiry, and success-resets-counter.

## 7. Session & cookie hardening

- ✅ `SESSION_COOKIE_HTTPONLY=True` — JS cannot read the cookie.
- ✅ `SESSION_COOKIE_SAMESITE="Lax"` — CSRF defense-in-depth.
- ✅ `SESSION_COOKIE_SECURE=True` when `FLASK_ENV=production`.
- ✅ `SECRET_KEY` from env (dev fallback only).
- ✅ Logout clears the session **before** `logout_user()` (no residue).

## 8. OAuth (Google / GitHub / LinkedIn)

- ✅ Provider-config check before redirect — graceful failure if unconfigured.
- ✅ OAuth users get a random 32-byte password (cannot login with an unknown
  password).
- ✅ Synthetic-email + primary-email endpoint fallbacks for GitHub/LinkedIn.
- ✅ `OAUTHLIB_INSECURE_TRANSPORT=1` only in development; production requires
  HTTPS.

## 9. Email delivery

- ✅ **Triple transport chain:** Flask-Mail → stdlib `smtplib` → console logging;
  sending never crashes the flow.
- ✅ `MAIL_FROM_EMAIL` resolves to the authenticated username (Gmail rule).
- ✅ No credential leakage on failure; mail enabled only when username+password
  are set (real Gmail App Password verified live).

## 10. Global HTTP hardening

- ✅ **CSP with per-request nonce** (`default-src 'self'`, strict `script-src`).
- ✅ `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`.
- ✅ `Referrer-Policy: strict-origin-when-cross-origin`.
- ✅ `Permissions-Policy` — camera/mic/geolocation disabled.
- ✅ Aggressive immutable caching for versioned static assets.

## 11. Rate limiting

- ✅ Sliding-window limiter: **30 req/min per IP** (`@rate_limit`) on OTP,
  feedback, chat, skills-gap, and ML/LLM endpoints.
- ✅ Bypassed under `TESTING` so the suite runs freely.
- ✅ Login uses the purpose-built IP+email lockout instead of the coarse IP
  limiter.

## 12. Operational notes

- ✅ `.env` is gitignored; all secrets (OAuth, SMTP, admin, Flask secret) are
  env-driven via `.env` / `python-dotenv`.
- ✅ Default admin seeded from env (`ADMIN_EMAIL` / `ADMIN_PASSWORD`) with
  `role="admin"`; admin-only dashboard + API checks.
- ✅ Uploads capped at 8 MB (413 handler).
- ✅ `/healthz` reports ML-pipeline readiness; structured logging throughout.

## 13. Known limitations

- ✅ **Rate-limit / login-lockout / OTP-cooldown counters are Redis-backed**
  when `REDIS_URL` is configured — the counters live in Redis (atomic across
  gunicorn workers) via `security.py`, which exposes a dict-like store over
  either backend. Without `REDIS_URL` they fall back to in-memory dicts
  (correct for the single-process dev server; `/healthz` reports which
  backend is active).
- ⚠️ **`/signup` is not IP rate-limited** — it creates a DB row and sends an
  OTP email per request; consider adding `@rate_limit` if exposed to the public
  internet.
- ⚠️ **`MAIL_DEFAULT_SENDER` in `.env` is effectively overridden** by
  `storage._configure_mail()` (harmless redundancy).
- ℹ️ The in-memory fallback (no `REDIS_URL`) resets lockout/rate-limit
  counters on server restart; the Redis backend survives restarts and is
  shared across processes.
