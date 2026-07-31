"""
Prayash — Smoke Tests
======================
Basic integration tests that verify the Flask application starts up,
serves all pages, and returns correct HTTP status codes.

Run with::

    pytest tests/test_app.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from uuid import uuid4

# Ensure the project root is on sys.path so that app can be imported.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure send_email is always mocked to avoid real SMTP calls in tests
os.environ.setdefault("MAIL_USERNAME", "")
os.environ.setdefault("MAIL_PASSWORD", "")
os.environ.setdefault("SMTP_USERNAME", "")
os.environ.setdefault("SMTP_PASSWORD", "")

# Point the database to a temporary file so tests don't touch the real DB.
# Use a unique temp dir per test invocation to prevent cross-test contamination.
_TEST_DB_DIR = Path(tempfile.mkdtemp())
os.environ.setdefault("DATABASE_URL",
                       f"sqlite:///{(_TEST_DB_DIR / 'test_prayash.db').as_posix()}")


@pytest.fixture
def app():
    """Create and configure a fresh Flask application for each test."""
    from app import app as flask_app

    # Disable CSRF for testing; we'll test CSRF separately via the API endpoint.
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    # Use a unique in-memory / temp database for isolation
    db_path = _TEST_DB_DIR / f"test_{uuid4().hex[:8]}.db"
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"

    with flask_app.app_context():
        from storage import db
        # Create tables inside the test DB
        db.create_all()
        from storage import seed_default_users
        seed_default_users()
        yield flask_app
        # Clean up test DB after the test
        db.drop_all()
        # Remove the temp DB file
        try:
            if db_path.exists():
                db_path.unlink()
        except PermissionError:
            pass


@pytest.fixture
def client(app):
    """A Flask test client bound to the fresh app instance."""
    return app.test_client()


# ── Page Existence Tests ───────────────────────────────────────────


@pytest.mark.parametrize(
    "route, expected_status",
    [
        ("/", 200),
        ("/login", 200),
        ("/signup", 200),
        ("/methodology", 200),
        ("/privacy", 200),
        ("/insights", 200),
        ("/partnerships", 200),
        ("/healthz", 200),
        ("/api/csrf-token", 200),
        ("/verify-otp", 302),     # Redirects to signup without session
        ("/forgot-password/otp", 200),
        ("/reset-password/otp", 302),  # Redirects to forgot-password without session
        ("/nonexistent-route", 404),
    ],
)
def test_page_status(client, route: str, expected_status: int) -> None:
    """Assert that public routes return the expected HTTP status."""
    resp = client.get(route)
    assert resp.status_code == expected_status, f"{route} returned {resp.status_code}"


def test_static_files_served(client) -> None:
    """Static CSS and JS files should be accessible."""
    for static_path in ("/static/styles.css", "/static/script.js", "/static/manifest.json"):
        resp = client.get(static_path)
        assert resp.status_code == 200, f"{static_path} returned {resp.status_code}"


# ── Authentication Flow Tests ──────────────────────────────────────


def test_signup_flow(client) -> None:
    """A new user can sign up and is redirected to OTP verification page."""
    resp = client.post(
        "/signup",
        data={
            "full_name": "Test User",
            "username": "testuser123",
            "email": "testuser@example.com",
            "password": "StrongP@ss1",
            "confirm_password": "StrongP@ss1",
            "terms": "on",
        },
        follow_redirects=False,
    )
    # Should redirect to OTP verification page
    assert resp.status_code in (302, 303), f"Expected redirect, got {resp.status_code}"
    assert "verify-otp" in resp.headers.get("Location", ""), f"Expected redirect to verify-otp, got {resp.headers.get('Location','')}"


def test_signup_rejects_missing_fields(client) -> None:
    """Signup without required fields should fail."""
    resp = client.post(
        "/signup",
        data={
            "email": "newuser@example.com",
            "password": "StrongP@ss1",
            "confirm_password": "StrongP@ss1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.lower()
    # Should show an error about missing full name or username
    assert b"name" in body or b"username" in body or b"valid email" in body


def test_signup_rejects_weak_password(client) -> None:
    """Signup with a weak password should fail."""
    resp = client.post(
        "/signup",
        data={
            "full_name": "Weak Pass",
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "short",
            "confirm_password": "short",
            "terms": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.lower()
    assert b"password" in body and (b"8" in body or b"uppercase" in body or b"character" in body)


def test_signup_rejects_duplicate_email(client) -> None:
    """Signup with an existing email should fail."""
    # First signup
    client.post(
        "/signup",
        data={
            "full_name": "First User",
            "username": "firstuser",
            "email": "dupe@example.com",
            "password": "StrongP@ss1",
            "confirm_password": "StrongP@ss1",
            "terms": "on",
        },
    )
    # Duplicate email
    resp = client.post(
        "/signup",
        data={
            "full_name": "Second User",
            "username": "seconduser",
            "email": "dupe@example.com",
            "password": "StrongP@ss1",
            "confirm_password": "StrongP@ss1",
            "terms": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.lower()
    assert b"already exists" in body or b"duplicate" in body or b"already" in body


def test_login_flow(client) -> None:
    """Default student credentials should log in and redirect to workspace.
    First verify the default student's email, then test login."""
    # First, verify the default student's email
    with client.application.app_context():
        from storage import User, db
        student = User.query.filter_by(email="student@prayash.local").first()
        assert student is not None, "Default student user not found"
        student.email_verified = True
        db.session.commit()
    
    resp = client.post(
        "/login",
        data={"email": "student@prayash.local", "password": "student"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Workspace" in resp.data or b"workspace" in resp.data


def test_verify_otp_flow(client) -> None:
    """OTP verification flow works end-to-end."""
    # Sign up a new user (redirects to OTP page)
    client.post(
        "/signup",
        data={
            "full_name": "OTP User",
            "username": "otpuser",
            "email": "otpuser@example.com",
            "password": "StrongP@ss1",
            "confirm_password": "StrongP@ss1",
            "terms": "on",
        },
    )
    
    # Get the OTP from the database
    with client.application.app_context():
        from storage import User, VerificationOTP
        user = User.query.filter_by(email="otpuser@example.com").first()
        assert user is not None
        otp = VerificationOTP.query.filter_by(
            user_id=user.id, purpose="verify_email", used=False
        ).order_by(VerificationOTP.id.desc()).first()
        assert otp is not None, "OTP not found in database"
        otp_code = otp.otp
    
    # Submit OTP for verification
    resp = client.post(
        "/verify-otp",
        data={"otp": otp_code, "purpose": "verify_email"},
        follow_redirects=False,
    )
    # Should redirect to workspace
    assert resp.status_code in (302, 303), f"Expected redirect after OTP, got {resp.status_code}"
    redirect_url = resp.headers.get("Location", "")
    assert "workspace" in redirect_url, f"Expected redirect to workspace, got {redirect_url}"


def test_login_with_unverified_email_then_verify_otp(client, monkeypatch) -> None:
    """Login with an unverified email sends a fresh OTP and the verify
    flow must complete (regression: OTP page was shown but verification
    could never succeed because no session was set)."""
    import app as app_module
    monkeypatch.setattr(app_module, "send_email", lambda *a, **k: True)

    with client.application.app_context():
        from storage import VerificationOTP, create_user, db
        u = create_user(
            email="unverified@example.com",
            password="StrongP@ss1",
            full_name="Unverified",
            username="unverified",
        )
        u.email_verified = False
        u_id = u.id
        db.session.commit()

    # Login with the correct password for an unverified account.
    resp = client.post(
        "/login",
        data={"email": "unverified@example.com", "password": "StrongP@ss1"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert b"Enter Verification Code" in resp.data

    with client.application.app_context():
        from storage import User
        otp = VerificationOTP.query.filter_by(
            user_id=u_id, purpose="verify_email", used=False
        ).order_by(VerificationOTP.id.desc()).first()
        assert otp is not None
        otp_code = otp.otp

    # Submitting the OTP must verify the user and go to the workspace.
    resp = client.post(
        "/verify-otp",
        data={"otp": otp_code, "purpose": "verify_email"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "workspace" in resp.headers.get("Location", "")

    with client.application.app_context():
        from storage import User
        fresh = db.session.get(User, u_id)
        assert fresh.email_verified is True


def test_login_with_bad_password(client) -> None:
    """Bad credentials should show an error."""
    resp = client.post(
        "/login",
        data={"email": "student@prayash.local", "password": "wrong-password"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Invalid" in resp.data or b"remaining" in resp.data


def test_workspace_requires_auth(client) -> None:
    """Unauthenticated access to /workspace should redirect to login."""
    resp = client.get("/workspace", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Login" in resp.data or b"login" in resp.data


# ── API Endpoint Tests ─────────────────────────────────────────────


def test_healthz(client) -> None:
    """The health-check endpoint returns a JSON status."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()
    assert data["status"] == "ok"


def test_csrf_token(client) -> None:
    """The CSRF token endpoint returns a fresh token."""
    resp = client.get("/api/csrf-token")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "csrf_token" in data
    assert len(data["csrf_token"]) > 20


def test_password_checker(client) -> None:
    """The password-strength endpoint scores passwords correctly."""
    resp = client.post(
        "/api/check-password",
        json={"password": "StrongP@ss1"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["score"] >= 4
    assert data["label"] in ("Strong", "Very strong")


# ── Core Analysis Pipeline Tests ───────────────────────────────────


def test_analysis_basic(client) -> None:
    """The analysis pipeline runs end-to-end with sample resume text."""
    resp = client.post(
        "/api/analyze",
        json={
            "resume_text": (
                "Computer Science graduate with Python, Java, and SQL experience. "
                "Worked on data analysis and machine learning projects. Strong "
                "communication and teamwork skills."
            ),
            "mode": "standard",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "risk_score" in data
    assert "risk_label" in data
    assert "top_roles" in data
    assert len(data["top_roles"]) > 0


def test_analysis_rejects_empty(client) -> None:
    """Analysis without resume text should return 400."""
    resp = client.post("/api/analyze", json={"mode": "standard"})
    assert resp.status_code == 400


def test_sse_stream(client) -> None:
    """The SSE streaming endpoint returns event-stream content."""
    resp = client.get(
        "/api/analyze-stream",
        query_string={"text": "Python developer with data science skills", "mode": "standard"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    # The first event should be 'init'
    body = resp.get_data(as_text=True)
    assert "Starting analysis" in body
    assert "complete" in body


# ── File Upload Tests ──────────────────────────────────────────────


def test_upload_no_file(client) -> None:
    """POST without a file returns a 400."""
    resp = client.post("/api/upload", data={})
    assert resp.status_code == 400


def test_large_file_rejected(client) -> None:
    """The 8 MB limit should be enforced (413 in production, 400 in testing)."""
    # Simulate a file larger than MAX_CONTENT_LENGTH (8 MB).
    big_data = b"x" * (9 * 1024 * 1024)
    resp = client.post(
        "/api/upload",
        data={"resume_file": (big_data, "resume.pdf")},
        content_type="multipart/form-data",
    )
    # The test client may return 400 (invalid request) instead of 413 (payload too large)
    # depending on how the WSGI server enforces MAX_CONTENT_LENGTH.
    # Both are acceptable indicators that the large file was rejected.
    assert resp.status_code in (400, 413), f"Expected 400 or 413, got {resp.status_code}"


# ── Feedback endpoint ──────────────────────────────────────────────


def test_feedback(client) -> None:
    """The feedback endpoint accepts POST requests."""
    resp = client.post(
        "/api/feedback",
        json={"message": "Great platform!", "rating": 5},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True


def test_feedback_rejects_empty(client) -> None:
    """Feedback without a message should return 400."""
    resp = client.post("/api/feedback", json={"rating": 3})
    assert resp.status_code == 400


# ── Career Chat API Tests ────────────────────────────────────────────


def test_career_chat_rejects_empty_message(client) -> None:
    """POST /api/career-chat with no message returns 400."""
    resp = client.post("/api/career-chat", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "question" in data.get("error", "").lower() or "message" in data.get("error", "").lower()


def test_career_chat_returns_valid_response(client) -> None:
    """POST /api/career-chat with a valid question returns a reply.
    Since Ollama is not available in test, the rule-based fallback is used."""
    resp = client.post(
        "/api/career-chat",
        json={"message": "What skills should I learn for data science?"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    # Both keys are returned for frontend compatibility
    assert "answer" in data, f"Expected 'answer' key in response, got {list(data.keys())}"
    assert "reply" in data, f"Expected 'reply' key in response, got {list(data.keys())}"
    assert data["answer"] == data["reply"], "'answer' and 'reply' should match"
    assert len(data["answer"]) > 0, "Reply should not be empty"
    assert "session_id" in data
    assert len(data["session_id"]) > 0
    assert isinstance(data["llm_powered"], bool)
    # llm_powered may be True if an API key is configured in .env
    # or False if using the rule-based fallback - both are valid
        # llm_powered may be True if an API key is configured in .env
        # or False if using the rule-based fallback — both are valid


def test_career_chat_session_continuity(client) -> None:
    """Using the same session_id maintains conversation history."""
    session_id = "test-session-continuity-001"

    # First message
    resp1 = client.post(
        "/api/career-chat",
        json={"message": "Tell me about Python skills", "session_id": session_id},
    )
    assert resp1.status_code == 200
    data1 = resp1.get_json()
    assert data1["session_id"] == session_id

    # Second message with same session
    resp2 = client.post(
        "/api/career-chat",
        json={"message": "What about SQL?", "session_id": session_id},
    )
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["session_id"] == session_id
    assert len(data2["answer"]) > 0


def test_career_chat_generates_new_session(client) -> None:
    """Without a session_id, the API generates one."""
    resp = client.post(
        "/api/career-chat",
        json={"message": "How do I improve my resume?"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    # A UUID-like session_id should have been generated
    assert len(data["session_id"]) >= 32, f"Expected long session_id, got '{data['session_id']}'"
    assert "-" in data["session_id"], "Expected UUID format"


def test_career_chat_fallback_topics(client) -> None:
    """Rule-based fallback responds to various career topics."""
    topics = [
        "What skills should I learn?",
        "How can I improve my resume?",
        "Tips for job interviews?",
        "Help me plan my career path",
        "How do I negotiate salary?",
    ]
    for topic in topics:
        resp = client.post("/api/career-chat", json={"message": topic})
        assert resp.status_code == 200, f"Topic '{topic}' failed with {resp.status_code}"
        data = resp.get_json()
        assert len(data["answer"]) > 20, f"Topic '{topic}' returned too-short answer"


def test_career_chat_interview_vs_career_path_distinct(client) -> None:
    """Regression: 'Tips for job interviews?' and 'Help me plan my career path'
    must return different, topic-specific answers. The old fallback matched
    'job' before 'interview' and returned the identical job-search text for
    both questions."""
    interview_resp = client.post(
        "/api/career-chat", json={"message": "Tips for job interviews?"}
    )
    career_resp = client.post(
        "/api/career-chat", json={"message": "Help me plan my career path"}
    )

    assert interview_resp.status_code == 200
    assert career_resp.status_code == 200

    interview_answer = interview_resp.get_json()["answer"].lower()
    career_answer = career_resp.get_json()["answer"].lower()

    assert interview_answer != career_answer, (
        "Interview and career-path answers must differ"
    )
    assert "interview" in interview_answer and "star" in interview_answer, (
        f"Interview answer missing interview guidance: {interview_answer[:100]}"
    )
    assert "career" in career_answer and "path" in career_answer, (
        f"Career-path answer missing career guidance: {career_answer[:100]}"
    )


def test_career_chat_resume_context(client) -> None:
    """Resume text can be sent as context."""
    resp = client.post(
        "/api/career-chat",
        json={
            "message": "What roles fit my profile?",
            "resume_text": "Python developer with 3 years of data science experience",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "Python" in data["answer"] or "data" in data["answer"] or "skill" in data["answer"].lower()


# ── PDF Section Detection Tests (SAHAY_AI-style) ───────────────────

try:
    import fitz as _fitz_module  # noqa: F401 (check availability)
    _HAS_PYMUPDF = True
except Exception:
    _HAS_PYMUPDF = False

PYMUPDF_SKIP_REASON = "PyMuPDF (fitz) not installed"


def _make_test_pdf() -> bytes:
    """Create a minimal in-memory PDF with mixed font sizes for testing layout detection.

    The PDF contains:
      - A large-font header: "EDUCATION"
      - Normal body text: "BSc in Computer Science"
      - A large-font header: "EXPERIENCE"
      - Normal body text: "Software Developer at Tech Corp"
    """
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()

    # Insert a header with large font (should be detected as a section header)
    page.insert_text(
        fitz.Point(72, 100),
        "EDUCATION",
        fontsize=24,
        fontname="helv",
    )
    # Insert body text with normal font
    page.insert_text(
        fitz.Point(72, 130),
        "BSc in Computer Science, University of Technology",
        fontsize=12,
        fontname="helv",
    )
    # Another header
    page.insert_text(
        fitz.Point(72, 180),
        "EXPERIENCE",
        fontsize=24,
        fontname="helv",
    )
    # Body text
    page.insert_text(
        fitz.Point(72, 210),
        "Software Developer at Tech Corp (2019-2024)",
        fontsize=12,
        fontname="helv",
    )

    data: bytes = doc.tobytes()
    doc.close()
    return data


def _make_test_pdf_with_metadata() -> bytes:
    """Create a minimal PDF with metadata fields set."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 100), "Hello World", fontsize=12)

    doc.set_metadata({
        "title": "Test Resume",
        "author": "John Doe",
        "subject": "Resume",
    })

    data: bytes = doc.tobytes()
    doc.close()
    return data


@pytest.mark.skipif(not _HAS_PYMUPDF, reason=PYMUPDF_SKIP_REASON)
def test_pdf_layout_extraction() -> None:
    """extract_pdf_layout() returns proper structure with spans."""
    from resume_parser import extract_pdf_layout

    pdf_bytes = _make_test_pdf()
    result = extract_pdf_layout(pdf_bytes)

    assert "text" in result, "Result should have 'text' key"
    assert "spans" in result, "Result should have 'spans' key"
    assert "metadata" in result, "Result should have 'metadata' key"
    assert "page_count" in result, "Result should have 'page_count' key"
    assert result["page_count"] == 1
    assert len(result["spans"]) > 0, "Should have extracted spans"
    # Check that both headers appear in the extracted text
    text = result["text"].lower()
    assert "education" in text, "Should contain 'education'"
    assert "experience" in text, "Should contain 'experience'"
    assert "computer science" in text, "Should contain body text"
    # Check that the large-font spans contain the headers
    header_spans = [s for s in result["spans"] if s["font_size"] > 20]
    assert len(header_spans) >= 2, "Should find at least 2 large-font spans"
    header_text = " ".join(s["text"] for s in header_spans).lower()
    assert "education" in header_text
    assert "experience" in header_text


@pytest.mark.skipif(not _HAS_PYMUPDF, reason=PYMUPDF_SKIP_REASON)
def test_pdf_layout_empty_fallback() -> None:
    """extract_pdf_layout() returns empty dict on invalid input."""
    from resume_parser import extract_pdf_layout

    result = extract_pdf_layout(b"not a valid PDF")
    assert result == {"text": "", "spans": [], "metadata": {}, "page_count": 0}


@pytest.mark.skipif(not _HAS_PYMUPDF, reason=PYMUPDF_SKIP_REASON)
def test_pdf_section_detection() -> None:
    """extract_text_by_sections() correctly identifies section headers vs content."""
    from resume_parser import extract_text_by_sections

    pdf_bytes = _make_test_pdf()
    sections = extract_text_by_sections(pdf_bytes)

    assert "full_text" in sections, "Should have 'full_text' key"
    # Headers should be detected as section keys
    # (they're normalized to lowercase with underscores)
    section_keys = set(sections.keys()) - {"full_text"}
    assert len(section_keys) > 0, f"Should have detected sections, got keys: {section_keys}"

    # At least one of 'education' or 'experience' should be detected
    has_education = "education" in section_keys
    has_experience = "experience" in section_keys
    assert has_education or has_experience, (
        f"Should have detected 'education' or 'experience' section, got: {section_keys}"
    )

    # Check that body text appears in the correct section content
    if has_education:
        edu_text = sections["education"].lower()
        assert "computer science" in edu_text or "bsc" in edu_text, (
            f"Education section should contain relevant text, got: {edu_text[:100]}"
        )


@pytest.mark.skipif(not _HAS_PYMUPDF, reason=PYMUPDF_SKIP_REASON)
def test_pdf_section_detection_empty() -> None:
    """extract_text_by_sections() returns full_text only on invalid input."""
    from resume_parser import extract_text_by_sections

    sections = extract_text_by_sections(b"invalid pdf data")
    assert "full_text" in sections
    assert len(sections) == 1, "Only 'full_text' key should be present for invalid input"


@pytest.mark.skipif(not _HAS_PYMUPDF, reason=PYMUPDF_SKIP_REASON)
def test_pdf_metadata() -> None:
    """get_pdf_metadata() extracts metadata correctly."""
    from resume_parser import get_pdf_metadata

    pdf_bytes = _make_test_pdf_with_metadata()
    meta = get_pdf_metadata(pdf_bytes)

    assert meta["title"] == "Test Resume"
    assert meta["author"] == "John Doe"
    assert "subject" in meta
    assert "creator" in meta
    assert "producer" in meta
    assert meta["pages"] == 1


@pytest.mark.skipif(not _HAS_PYMUPDF, reason=PYMUPDF_SKIP_REASON)
def test_pdf_metadata_empty_fallback() -> None:
    """get_pdf_metadata() returns empty dict on invalid input."""
    from resume_parser import get_pdf_metadata

    meta = get_pdf_metadata(b"not a valid PDF")
    assert meta == {}


def test_parse_resume_enhanced_with_layout_sections() -> None:
    """parse_resume_enhanced() respects layout_sections override."""
    from resume_parser import parse_resume_enhanced

    raw_text = "Some raw text that shouldn't be parsed for education"
    layout_sections = {
        "education": "MIT\nPhD in Computer Science\n2015-2020",
        "experience": "Google\nSenior Engineer\n2020-2024",
        "full_text": raw_text,
    }
    result = parse_resume_enhanced(raw_text, layout_sections)

    # Education should come from layout_sections, not from raw_text
    edu = result.get("education", [])
    assert len(edu) >= 2, f"Should have at least 2 education entries, got {edu}"
    edu_text = " ".join(edu).lower()
    assert "mit" in edu_text, f"Should contain 'mit' from layout sections, got: {edu_text}"
    assert "phd" in edu_text, f"Should contain 'phd' from layout sections, got: {edu_text}"

    # Experience should come from layout_sections
    exp = result.get("experience", [])
    exp_text = " ".join(exp).lower()
    assert "google" in exp_text, f"Should contain 'google' from layout sections, got: {exp_text}"


def test_career_chat_ttl_cleanup(client) -> None:
    """Stale sessions are cleaned up based on TTL."""
    import time as time_module
    from app import _CAREER_CHAT_TTL, _cleanup_stale_career_sessions
    from app import _CAREER_CHAT_SESSIONS, _CAREER_CHAT_LAST_ACTIVE

    # Create a session with a timestamp far in the past
    old_time = time_module.time() - _CAREER_CHAT_TTL - 60  # 60s past TTL
    sid = "test-ttl-session"
    try:
        _CAREER_CHAT_SESSIONS[sid] = [{"role": "user", "content": "test"}]
        _CAREER_CHAT_LAST_ACTIVE[sid] = old_time

        # Run the cleanup manually
        _cleanup_stale_career_sessions()

        # Session should be removed
        assert sid not in _CAREER_CHAT_SESSIONS
        assert sid not in _CAREER_CHAT_LAST_ACTIVE
    finally:
        # Ensure global state is cleaned up even if the test fails
        _CAREER_CHAT_SESSIONS.clear()
        _CAREER_CHAT_LAST_ACTIVE.clear()


# ── Career Chat Streaming SSE Tests ─────────────────────────────────


def test_career_chat_stream_rejects_empty_message(client) -> None:
    """POST /api/career-chat/stream with no message returns 400."""
    resp = client.post("/api/career-chat/stream", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "question" in data.get("error", "").lower()


def test_career_chat_stream_returns_sse(client) -> None:
    """POST /api/career-chat/stream returns SSE events with meta, token, done."""
    import json

    resp = client.post(
        "/api/career-chat/stream",
        json={"message": "What skills should I learn for data science?"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"

    body = resp.get_data(as_text=True)
    events = body.split("\n\n")

    # Should have at least 3 events: meta, token, done
    assert len(events) >= 3, f"Expected >=3 SSE events, got {len(events)}"

    event_types = []
    for event_str in events:
        if not event_str.strip():
            continue
        lines = event_str.strip().split("\n")
        for line in lines:
            if line.startswith("event: "):
                event_types.append(line[7:].strip())

    assert "meta" in event_types, f"Missing 'meta' event, got {event_types}"
    assert "token" in event_types, f"Missing 'token' event, got {event_types}"
    assert "done" in event_types, f"Missing 'done' event, got {event_types}"

    # Verify meta event order: meta should come first
    assert event_types[0] == "meta", f"Expected 'meta' as first event, got {event_types}"
    assert event_types[-1] == "done", f"Expected 'done' as last event, got {event_types}"


def test_career_chat_stream_meta_contains_session_id(client) -> None:
    """The meta SSE event includes a session_id."""
    import json

    resp = client.post(
        "/api/career-chat/stream",
        json={"message": "How do I prepare for interviews?"},
    )
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    events = body.split("\n\n")

    # Parse the meta event (first event)
    for event_str in events:
        if not event_str.strip():
            continue
        lines = event_str.strip().split("\n")
        event_type = ""
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:].strip()

        if event_type == "meta" and data_str:
            parsed = json.loads(data_str)
            assert "session_id" in parsed, "Meta event should contain session_id"
            assert len(parsed["session_id"]) > 0, "session_id should not be empty"
            break


def test_career_chat_stream_done_contains_answer(client) -> None:
    """The done SSE event includes the full answer text."""
    import json

    resp = client.post(
        "/api/career-chat/stream",
        json={"message": "What skills for AI career?"},
    )
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    events = body.split("\n\n")

    # Find the done event
    for event_str in events:
        if not event_str.strip():
            continue
        lines = event_str.strip().split("\n")
        event_type = ""
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:].strip()

        if event_type == "done" and data_str:
            parsed = json.loads(data_str)
            assert "answer" in parsed, "Done event should contain 'answer'"
            assert len(parsed["answer"]) > 20, f"Answer too short: {parsed['answer']}"
            assert "session_id" in parsed, "Done event should contain session_id"
            break


def test_career_chat_stream_fallback_topics(client) -> None:
    """Streaming endpoint returns relevant fallback answers for each topic."""
    import json

    topics_with_keywords = [
        ("What skills should I learn?", ["skill", "learn", "roadmap", "course"]),
        ("How can I improve my resume?", ["resume", "achievement", "keywords", "ATS"]),
        ("How should I prepare for interviews?", ["interview", "prepare", "STAR", "practice"]),
        ("How do I negotiate salary?", ["salary", "compensation", "negotiate", "Glassdoor"]),
        ("Help me plan my career", ["career", "skill", "role", "path"]),
    ]

    for topic, keywords in topics_with_keywords:
        resp = client.post(
            "/api/career-chat/stream",
            json={"message": topic},
        )
        assert resp.status_code == 200, f"Topic '{topic}' failed with {resp.status_code}"

        body = resp.get_data(as_text=True)
        events = body.split("\n\n")

        # Extract full answer from token events
        full_answer = ""
        for event_str in events:
            if not event_str.strip():
                continue
            lines = event_str.strip().split("\n")
            event_type = ""
            data_str = ""
            for line in lines:
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:].strip()

            if event_type == "token" and data_str:
                try:
                    parsed = json.loads(data_str)
                    full_answer += parsed.get("content", "")
                except json.JSONDecodeError:
                    pass

        assert len(full_answer) > 30, (
            f"Topic '{topic}' returned too-short answer ({len(full_answer)} chars)"
        )
        assert any(kw in full_answer.lower() for kw in keywords), (
            f"Topic '{topic}' answer missing expected keywords. "
            f"Keywords: {keywords}, Answer preview: {full_answer[:80]}"
        )


def test_career_chat_stream_interview_vs_career_path_distinct(client) -> None:
    """Regression for the streaming endpoint: interview and career-path
    questions must stream different, topic-specific fallback answers."""
    import json as _json

    def _stream_answer(message: str) -> str:
        resp = client.post(
            "/api/career-chat/stream", json={"message": message}
        )
        assert resp.status_code == 200, f"Message '{message}' failed"
        body = resp.get_data(as_text=True)
        events = body.split("\n\n")
        full = ""
        for event_str in events:
            if not event_str.strip():
                continue
            lines = event_str.strip().split("\n")
            event_type = ""
            data_str = ""
            for line in lines:
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:].strip()
            if event_type == "token" and data_str:
                try:
                    full += _json.loads(data_str).get("content", "")
                except _json.JSONDecodeError:
                    pass
        return full.lower()

    interview_answer = _stream_answer("Tips for job interviews?")
    career_answer = _stream_answer("Help me plan my career path")

    assert interview_answer != career_answer, (
        "Stream: interview and career-path answers must differ"
    )
    assert "interview" in interview_answer and "star" in interview_answer
    assert "career" in career_answer and "path" in career_answer


def test_career_chat_stream_session_continuity(client) -> None:
    """Using the same session_id maintains conversation history."""
    import json

    session_id = "test-stream-session-001"

    # Helper to extract answer from SSE response
    def _extract_answer(resp):
        body = resp.get_data(as_text=True)
        events = body.split("\n\n")
        answer = ""
        got_session = ""
        for event_str in events:
            if not event_str.strip():
                continue
            lines = event_str.strip().split("\n")
            event_type = ""
            data_str = ""
            for line in lines:
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:].strip()

            if event_type == "meta" and data_str:
                try:
                    parsed = json.loads(data_str)
                    got_session = parsed.get("session_id", "")
                except json.JSONDecodeError:
                    pass
            elif event_type == "token" and data_str:
                try:
                    parsed = json.loads(data_str)
                    answer += parsed.get("content", "")
                except json.JSONDecodeError:
                    pass
        return answer, got_session

    # First message
    resp1 = client.post(
        "/api/career-chat/stream",
        json={"message": "Tell me about Python", "session_id": session_id},
    )
    assert resp1.status_code == 200
    answer1, sid1 = _extract_answer(resp1)
    assert len(answer1) > 0, "First answer should not be empty"

    # Second message with same session
    resp2 = client.post(
        "/api/career-chat/stream",
        json={"message": "What about SQL?", "session_id": session_id},
    )
    assert resp2.status_code == 200
    answer2, sid2 = _extract_answer(resp2)
    assert len(answer2) > 0, "Second answer should not be empty"


def test_career_chat_stream_generates_new_session(client) -> None:
    """Without a session_id, the streaming API generates one."""
    import json

    resp = client.post(
        "/api/career-chat/stream",
        json={"message": "Help me with my career path"},
    )
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    events = body.split("\n\n")

    # Find session_id in meta event
    session_id = ""
    for event_str in events:
        if not event_str.strip():
            continue
        lines = event_str.strip().split("\n")
        event_type = ""
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:].strip()

        if event_type == "meta" and data_str:
            try:
                parsed = json.loads(data_str)
                session_id = parsed.get("session_id", "")
            except json.JSONDecodeError:
                pass
            break

    assert len(session_id) >= 32, f"Expected long session_id, got '{session_id}'"
    assert "-" in session_id, "Expected UUID format with dashes"


def test_career_chat_stream_with_resume_context(client) -> None:
    """Resume text can be sent as context to the streaming endpoint."""
    import json

    resp = client.post(
        "/api/career-chat/stream",
        json={
            "message": "What roles fit my profile?",
            "resume_text": "Python developer with 3 years of data science and machine learning experience",
        },
    )
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    events = body.split("\n\n")

    # Extract token content
    full_answer = ""
    for event_str in events:
        if not event_str.strip():
            continue
        lines = event_str.strip().split("\n")
        event_type = ""
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:].strip()

        if event_type == "token" and data_str:
            try:
                parsed = json.loads(data_str)
                full_answer += parsed.get("content", "")
            except json.JSONDecodeError:
                pass

    # Verify the full answer after all events are processed
    assert len(full_answer) > 0, "Answer should not be empty with resume context"
    # Should mention skills or roles relevant to the resume
    assert any(kw in full_answer.lower() for kw in ["python", "data", "skill"]), (
        f"Answer should reference resume content, got: {full_answer[:100]}"
    )


def test_career_chat_stream_ssle_event_format(client) -> None:
    """Each SSE event follows the correct format: event:<name>\ndata:<json>\n\n"""
    import json

    resp = client.post(
        "/api/career-chat/stream",
        json={"message": "What skills for AI?"},
    )
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    events = body.split("\n\n")
    valid_events = [e for e in events if e.strip()]

    for event_str in valid_events:
        lines = event_str.strip().split("\n")
        has_event_line = any(line.startswith("event: ") for line in lines)
        has_data_line = any(line.startswith("data: ") for line in lines)

        assert has_event_line, f"Event missing 'event:' line: {event_str[:60]}"
        assert has_data_line, f"Event missing 'data:' line: {event_str[:60]}"

        # Verify the data line contains valid JSON
        for line in lines:
            if line.startswith("data: "):
                data_content = line[6:].strip()
                parsed = json.loads(data_content)
                assert isinstance(parsed, dict), f"data should be valid JSON object, got {type(parsed)}"


def test_career_chat_stream_token_accumulates_correctly(client) -> None:
    """The tokens in the done event's answer match the concatenated token content."""
    import json

    resp = client.post(
        "/api/career-chat/stream",
        json={"message": "Give me career advice"},
    )
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    events = body.split("\n\n")

    # Reconstruct answer from tokens and check against done event
    reconstructed = ""
    done_answer = None

    for event_str in events:
        if not event_str.strip():
            continue
        lines = event_str.strip().split("\n")
        event_type = ""
        data_str = ""
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:].strip()

        if data_str:
            try:
                parsed = json.loads(data_str)
                if event_type == "token":
                    reconstructed += parsed.get("content", "")
                elif event_type == "done":
                    done_answer = parsed.get("answer", "")
            except json.JSONDecodeError:
                pass

    assert done_answer is not None, "Should have a 'done' event with answer"
    assert reconstructed == done_answer, (
        f"Reconstructed answer does not match done answer.\n"
        f"  Reconstructed ({len(reconstructed)}): {reconstructed[:60]}...\n"
        f"  Done answer ({len(done_answer)}): {done_answer[:60]}..."
    )


def test_career_chat_stream_rejects_bad_json(client) -> None:
    """Invalid JSON body returns 400."""
    resp = client.post(
        "/api/career-chat/stream",
        data="this is not json",
        content_type="application/json",
    )
    # Flask's get_json(silent=True) won't parse it, so message will be empty
    assert resp.status_code == 400, f"Expected 400 for bad JSON, got {resp.status_code}"
    data = resp.get_json()
    assert data["success"] is False
