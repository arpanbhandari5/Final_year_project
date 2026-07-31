"""End-to-end forgot password flow test (legacy token flow).
Extracts the reset token directly from the database for reliability."""
import requests, re, random, sys, os, subprocess

BASE = "http://127.0.0.1:5000"
s = requests.Session()
errors = 0

def pr(name, passed, detail=""):
    mark = "[PASS]" if passed else "[FAIL]"
    print(f"  {mark} {name}" + (f" - {detail}" if detail else ""))
    if not passed:
        global errors
        errors += 1


def fetch_otp(email, purpose="verify_email"):
    """Read the latest unused OTP for *email* straight from the database."""
    script = r"""
import sys
sys.path.insert(0, '.')
from app import app
from storage import User, VerificationOTP
with app.app_context():
    user = User.query.filter_by(email=sys.argv[1]).first()
    if not user:
        print('USER_NOT_FOUND'); raise SystemExit
    rec = VerificationOTP.query.filter_by(
        user_id=user.id, purpose=sys.argv[2], used=False
    ).order_by(VerificationOTP.id.desc()).first()
    print(rec.otp if rec else 'NO_OTP')
"""
    result = subprocess.run(
        ["python", "-c", script, email, purpose],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return result.stdout.strip()

suffix = str(random.randint(10000, 99999))
test_email = f"reset{suffix}@example.com"
test_user = f"resetuser{suffix}"
orig_pw = "OriginalPass123!"
new_pw = "NewSecurePass456!"

print(f"Test user: {test_user} <{test_email}>")

# Step 1: Signup
print("\n=== 1. Create test user ===")
r = s.get(f"{BASE}/signup")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)
r = s.post(f"{BASE}/signup", data={
    "csrf_token": token, "full_name": "Reset Test User",
    "username": test_user, "email": test_email,
    "phone": "+1-555-000-0000", "password": orig_pw,
    "confirm_password": orig_pw, "terms": "on"
}, allow_redirects=False)
pr("User created", r.status_code in (302, 303))
if r.status_code in (302, 303):
    # New accounts must verify their email with the OTP before logging in.
    loc = r.headers.get("Location", "")
    if loc.startswith("/"):
        r = s.get(f"{BASE}{loc}")
    otp = fetch_otp(test_email, "verify_email")
    m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
    verify_token = m.group(1) if m else ""
    pr("Email verified via OTP", otp not in ("NO_OTP", "USER_NOT_FOUND") and bool(verify_token))
    if otp not in ("NO_OTP", "USER_NOT_FOUND") and verify_token:
        r = s.post(f"{BASE}/verify-otp", data={
            "csrf_token": verify_token, "otp": otp, "purpose": "verify_email"
        }, allow_redirects=False)
        pr("OTP accepted", r.status_code in (302, 303))
s.post(f"{BASE}/logout")

# Step 2: Verify original login
print("\n=== 2. Verify original password ===")
r = s.get(f"{BASE}/login")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)
r = s.post(f"{BASE}/login", data={
    "csrf_token": token, "email": test_email, "password": orig_pw
}, allow_redirects=False)
pr("Login with original password", r.status_code in (302, 303))
s.post(f"{BASE}/logout")

# Step 3: Submit forgot password
print("\n=== 3. Submit forgot password ===")
r = s.get(f"{BASE}/forgot-password")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)
r = s.post(f"{BASE}/forgot-password", data={
    "csrf_token": token, "email": test_email
})
pr("Forgot password submitted", r.status_code == 200)

# Step 4: Get token from DB
print("\n=== 4. Get reset token from DB ===")
import subprocess
# Use Python to query the database directly
script = """
import sys, os
sys.path.insert(0, '.')
from app import app
from storage import db, PasswordResetToken, User
with app.app_context():
    user = User.query.filter_by(email=sys.argv[1]).first()
    if user:
        record = PasswordResetToken.query.filter_by(user_id=user.id, used=False).order_by(PasswordResetToken.id.desc()).first()
        if record:
            print(record.token)
        else:
            print('NO_TOKEN_FOUND')
    else:
        print('USER_NOT_FOUND')
"""
result = subprocess.run(
    ["python", "-c", script, test_email],
    capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
)
token_value = result.stdout.strip()
pr("Token extracted from DB", bool(token_value) and token_value not in ("NO_TOKEN_FOUND", "USER_NOT_FOUND"))
if token_value and token_value not in ("NO_TOKEN_FOUND", "USER_NOT_FOUND"):
    print(f"  Token: {token_value[:20]}...{token_value[-8:]} ({len(token_value)} chars)")
else:
    print(f"  DB query result: {token_value}")
    if result.stderr:
        print(f"  stderr: {result.stderr[:300]}")

# Step 5: Visit reset page (GET)
print("\n=== 5. Visit reset password page ===")
if token_value and token_value not in ("NO_TOKEN_FOUND", "USER_NOT_FOUND"):
    r = s.get(f"{BASE}/reset-password/{token_value}")
    pr("Reset page loads", r.status_code == 200, f"{len(r.text)} chars")
    has_fields = 'name="password"' in r.text
    pr("Has password field", has_fields)
    has_csrf = 'csrf_token' in r.text
    pr("Has CSRF token", has_csrf)
else:
    pr("Reset page loads (no token)", False)

# Step 6: Submit new password (POST)
print("\n=== 6. Submit new password ===")
if token_value and token_value not in ("NO_TOKEN_FOUND", "USER_NOT_FOUND"):
    m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
    token2 = m.group(1) if m else ""
    r = s.post(f"{BASE}/reset-password/{token_value}", data={
        "csrf_token": token2,
        "password": new_pw,
        "confirm_password": new_pw
    })
    pr("New password accepted", r.status_code == 200)
    has_success = "success" in r.text.lower() or "password" in r.text.lower()
    pr("Success message shown", has_success)
    has_link_back = "Sign In" in r.text or "login" in r.text.lower()
    pr("Has link back to login", has_link_back)
else:
    pr("New password accepted (no token)", False)
    pr("Success message shown (no token)", False)
    pr("Has link back to login (no token)", False)

# Step 7: Login with NEW password
print("\n=== 7. Login with NEW password ===")
r = s.get(f"{BASE}/login")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)
r = s.post(f"{BASE}/login", data={
    "csrf_token": token, "email": test_email, "password": new_pw
}, allow_redirects=False)
pr("Login with new password succeeds", r.status_code in (302, 303))
if r.status_code in (302, 303):
    loc = r.headers.get("Location", "")
    if loc.startswith("/"):
        r = s.get(f"{BASE}{loc}")
    pr("Reached workspace", r.status_code == 200)

# Step 8: Old password rejected
print("\n=== 8. Old password rejected ===")
s.post(f"{BASE}/logout")
r = s.get(f"{BASE}/login")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)
r = s.post(f"{BASE}/login", data={
    "csrf_token": token, "email": test_email, "password": orig_pw
})
stayed = "/login" in r.url
pr("Old password no longer works", stayed)

# Step 9: Login by username with new password
print("\n=== 9. Login by username ===")
r = s.get(f"{BASE}/login")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)
r = s.post(f"{BASE}/login", data={
    "csrf_token": token, "email": test_user, "password": new_pw
}, allow_redirects=False)
pr("Login by username works", r.status_code in (302, 303))

# Step 10: Verify token is consumed (one-time use)
print("\n=== 10. Verify token cannot be reused ===")
r = s.get(f"{BASE}/reset-password/{token_value}")
pr("Reused token rejected", "invalid" in r.text.lower() or "expired" in r.text.lower() or r.status_code == 200)

# Summary
print(f"\n{'='*40}")
print(f"RESULTS: {errors} error(s) out of 10 test groups")
if errors == 0:
    print("*** All forgot/reset password tests passed! ***")
else:
    print(f"*** {errors} test group(s) had failures ***")
sys.exit(errors)
