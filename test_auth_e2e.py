"""End-to-end auth system validation script.

Targets the current OTP-based flow: signup -> email verification via a
6-digit code -> login.  The verification code is read directly from the
database (same approach as test_forgot_password.py).
"""
import requests
import re
import sys
import os
import subprocess

BASE = "http://127.0.0.1:5000"
session = requests.Session()
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

# Use unique user to avoid DB conflicts from prior runs
import random
suffix = str(random.randint(10000, 99999))
TEST_USER = {
    "full_name": "Test User",
    "username": f"testuser{suffix}",
    "email": f"testuser{suffix}@example.com",
    "phone": "+1-555-123-4567",
    "password": "SecurePass123!"
}
print(f"Test user: {TEST_USER['username']} <{TEST_USER['email']}>")

# -- Step 1: Load signup page --
print("\n=== 1. Signup page loads ===")
r = session.get(f"{BASE}/signup")
pr("Page loads with status 200", r.status_code == 200, f"{len(r.text)} chars")

m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
assert m, "CSRF token not found"
signup_token = m.group(1)
pr("CSRF token extracted", True)

fields_found = []
for field in ["full_name", "username", "email", "phone", "password", "confirm_password", "terms"]:
    if field in r.text:
        fields_found.append(field)
all_required = all(f in fields_found for f in ["full_name", "username", "email", "password", "confirm_password", "terms"])
pr(f"All form fields present ({len(fields_found)} found)", all_required)

# -- Step 2: Successful signup --
print("\n=== 2. Successful signup ===")
r = session.post(f"{BASE}/signup", data={
    "csrf_token": signup_token,
    "full_name": TEST_USER["full_name"],
    "username": TEST_USER["username"],
    "email": TEST_USER["email"],
    "phone": TEST_USER["phone"],
    "password": TEST_USER["password"],
    "confirm_password": TEST_USER["password"],
    "terms": "on"
}, allow_redirects=False)

redirected = r.status_code in (302, 303)
loc = r.headers.get("Location", "?")
pr("Signup succeeded (redirect)", redirected, f"Status: {r.status_code} -> {loc}")

if redirected:
    # Follow redirect (should land on the OTP verification page)
    if loc.startswith("/"):
        r = session.get(f"{BASE}{loc}")
    else:
        r = session.get(loc)
    pr("Landed on OTP verification after signup", "/verify-otp" in r.url, f"URL: {r.url}")

# -- Step 2b: Email verification with OTP --
print("\n=== 2b. Email verification via OTP ===")
if redirected:
    otp_code = fetch_otp(TEST_USER["email"], "verify_email")
    pr("OTP extracted from database", otp_code not in ("NO_OTP", "USER_NOT_FOUND"), f"code={otp_code!r}")
    m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
    verify_token = m.group(1) if m else ""
    pr("Verify page CSRF token extracted", bool(verify_token))
    r = session.post(f"{BASE}/verify-otp", data={
        "csrf_token": verify_token,
        "otp": otp_code,
        "purpose": "verify_email",
    }, allow_redirects=False)
    pr("OTP submission accepted (redirect)", r.status_code in (302, 303), f"-> {r.headers.get('Location','?')}")
    if r.status_code in (302, 303):
        if r.headers.get("Location", "").startswith("/"):
            r = session.get(f"{BASE}{r.headers.get('Location')}")
        pr("Reached workspace after verification", r.status_code == 200, f"URL: {r.url}")
else:
    pr("Email verification via OTP", False, "Skipped (signup did not redirect)")

# -- Step 3: Duplicate email rejection --
print("\n=== 3. Duplicate email rejected ===")
r = session.get(f"{BASE}/signup")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)

r = session.post(f"{BASE}/signup", data={
    "csrf_token": token,
    "full_name": "Duplicate Email",
    "username": f"dupemail{suffix}",
    "email": TEST_USER["email"],
    "password": "SecurePass456!",
    "confirm_password": "SecurePass456!",
    "terms": "on"
})
rejected = "already" in r.text.lower() and ("registered" in r.text.lower() or "exists" in r.text.lower())
pr("Duplicate email rejected", rejected)

# -- Step 4: Duplicate username rejection --
print("\n=== 4. Duplicate username rejected ===")
r = session.get(f"{BASE}/signup")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)

r = session.post(f"{BASE}/signup", data={
    "csrf_token": token,
    "full_name": "Duplicate Username",
    "username": TEST_USER["username"],
    "email": f"dupusername{suffix}@example.com",
    "password": "SecurePass789!",
    "confirm_password": "SecurePass789!",
    "terms": "on"
})
rejected = "already" in r.text.lower() and ("taken" in r.text.lower() or "exists" in r.text.lower())
pr("Duplicate username rejected", rejected)

# -- Step 5: Weak password rejection --
print("\n=== 5. Weak password rejected ===")
r = session.get(f"{BASE}/signup")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)

r = session.post(f"{BASE}/signup", data={
    "csrf_token": token,
    "full_name": "Weak User",
    "username": f"weakuser{suffix}",
    "email": f"weak{suffix}@example.com",
    "password": "weak",
    "confirm_password": "weak",
    "terms": "on"
})
rejected = "password" in r.text.lower() and "8" in r.text
pr("Weak password (<8 chars) rejected", rejected)

# -- Step 6: Logout (POST) --
print("\n=== 6. Logout ===")
from requests.cookies import RequestsCookieJar
session.get(f"{BASE}/login")  # Ensure we're on a page
r = session.post(f"{BASE}/logout", allow_redirects=False)
pr("Logout redirects", r.status_code in (302, 303), f"-> {r.headers.get('Location','?')}")

# -- Step 7: Login by email --
print("\n=== 7. Login by email ===")
r = session.get(f"{BASE}/login")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)

r = session.post(f"{BASE}/login", data={
    "csrf_token": token,
    "email": TEST_USER["email"],
    "password": TEST_USER["password"]
}, allow_redirects=False)
pr("Login by email succeeds", r.status_code in (302, 303), f"-> {r.headers.get('Location','?')}")

# Follow to workspace
r = session.get(f"{BASE}/workspace")
pr("Accessed workspace after login", r.status_code == 200, f"URL: {r.url}")

# -- Step 8: Logout and login by username --
print("\n=== 8. Login by username ===")
session.post(f"{BASE}/logout")
r = session.get(f"{BASE}/login")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)

r = session.post(f"{BASE}/login", data={
    "csrf_token": token,
    "email": TEST_USER["username"],
    "password": TEST_USER["password"]
}, allow_redirects=False)
pr("Login by username succeeds", r.status_code in (302, 303), f"-> {r.headers.get('Location','?')}")

# -- Step 9: Wrong password rejection --
print("\n=== 9. Wrong password rejected ===")
session.post(f"{BASE}/logout")
r = session.get(f"{BASE}/login")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
token = m.group(1)

r = session.post(f"{BASE}/login", data={
    "csrf_token": token,
    "email": TEST_USER["username"],
    "password": "wrongpassword123!"
})
rejected = "invalid" in r.text.lower() or "incorrect" in r.text.lower() or "error" in r.text.lower() or "wrong" in r.text.lower()
pr("Wrong password rejected", rejected, "Stayed on login page")

# -- Step 10: Forgot password page --
print("\n=== 10. Forgot password page ===")
r = session.get(f"{BASE}/forgot-password")
pr("Forgot password page loads", r.status_code == 200, f"{len(r.text)} chars")
has_email = 'name="email"' in r.text or 'type="email"' in r.text
pr("Has email input field", has_email)
has_btn = "Reset" in r.text or "Send" in r.text or "Submit" in r.text
pr("Has submit button", has_btn)

# -- Step 11: Forgot password submission (prevent email enumeration) --
print("\n=== 11. Forgot password submit ===")
m = re.search(r'name="csrf_token"[^>]*value="(.*?)"', r.text)
if m:
    token = m.group(1)
    r = session.post(f"{BASE}/forgot-password", data={
        "csrf_token": token,
        "email": TEST_USER["email"]
    })
    pr("Forgot password shows success message", "sent" in r.text.lower() or "email" in r.text.lower() or "check" in r.text.lower())
else:
    pr("Forgot password CSRF token", False)

# -- Summary --
print(f"\n{'='*40}")
print(f"RESULTS: {errors} error(s) out of 11 test groups")
if errors == 0:
    print("*** All auth system tests passed! ***")
else:
    print(f"*** {errors} test group(s) had failures ***")
sys.exit(errors)
