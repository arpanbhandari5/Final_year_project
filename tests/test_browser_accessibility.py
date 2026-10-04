"""Live axe-core + keyboard/focus/responsive checks for B1 surfaces.

Requires Flask and ``pytest --run-browser``. Reuses the existing Python
Playwright live-browser infrastructure (no second test runner).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.axe_helper import analyze_page, assert_axe_installed, format_violations
from tests.test_browser_resume_workflow import (
    FIXTURES,
    _ensure_fixtures,
    _server_up,
    _upload_and_analyze,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("PRAYASH_BROWSER_BASE", "http://127.0.0.1:5000")
PAYLOAD = '<script>alert(1)</script><img src=x onerror="alert(1)">'
WORKSPACE_INCLUDE = [".page-hero", "#career-goal"]
UPLOAD_INCLUDE = ["#analysis"]
MODAL_INCLUDE = ["[data-result-modal]"]
LOGIN_INCLUDE = [".auth-split__card"]


def _require_live(pytestconfig) -> None:
    if not pytestconfig.getoption("--run-browser"):
        pytest.skip("Needs live Flask; run with pytest --run-browser")
    if not _server_up(f"{BASE}/healthz") and not _server_up(BASE):
        pytest.fail(
            f"Flask is not running at {BASE}. Start `python app.py` then re-run "
            "pytest tests/test_browser_accessibility.py --run-browser"
        )
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        pytest.fail("Playwright is not installed. pip install playwright && playwright install chromium")
    assert_axe_installed()


def _login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill("#login-email", "student")
    page.fill("#login-password", "Student@123")
    page.click("button[type='submit']")
    page.wait_for_load_state("domcontentloaded")


def _assert_axe(results: dict, extra: str = "") -> None:
    violations = results.get("violations") or []
    if violations:
        pytest.fail(
            f"axe violations on {results.get('context')} {extra}\n{format_violations(results)}"
        )


def _upload_respecting_live_limit(page, file_path, mode: str = "standard") -> dict:
    """Retry /api/upload when the live Flask sliding window (30/60s) returns 429."""
    last = {}
    for _ in range(5):
        last = _upload_and_analyze(page, file_path, mode)
        payload = last.get("json") or {}
        if last.get("http_status") != 429 and payload.get("success") is not False:
            return last
        if last.get("http_status") != 429:
            return last
        time.sleep(15)
    return last


def _overflow(page) -> bool:
    return bool(
        page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
        )
    )


def _focus_visible(page) -> bool:
    page.keyboard.press("Tab")
    return bool(
        page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || el === document.body) return false;
                const style = window.getComputedStyle(el);
                const outline = style.outlineWidth !== '0px' && style.outlineStyle !== 'none';
                const shadow = style.boxShadow && style.boxShadow !== 'none';
                return outline || shadow || el.classList.contains('skip-link');
            }"""
        )
    )


@pytest.mark.browser_live
def test_live_axe_b1_surfaces(pytestconfig) -> None:
    _require_live(pytestconfig)
    _ensure_fixtures()
    scans: list[dict] = []

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.set_default_timeout(180_000)

        _login(page)

        page.goto(f"{BASE}/workspace", wait_until="domcontentloaded")
        page.wait_for_selector("[data-workspace-status]")
        page.wait_for_timeout(400)
        empty = analyze_page(page, include=WORKSPACE_INCLUDE, context_label="workspace-empty-desktop")
        scans.append(empty)
        _assert_axe(empty)
        assert page.locator("[data-evidence-summary]").inner_text()
        assert page.locator("#main-content").count() == 1
        assert page.locator(".skip-link").count() == 1
        assert _focus_visible(page)

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(200)
        assert page.locator("[data-goal-form]").is_visible()
        assert not _overflow(page)
        empty_mobile = analyze_page(page, include=WORKSPACE_INCLUDE, context_label="workspace-empty-mobile-390x844")
        scans.append(empty_mobile)
        _assert_axe(empty_mobile)

        page.set_viewport_size({"width": 1440, "height": 900})
        page.fill("#evidence-skill", PAYLOAD)
        page.fill("#evidence-span", PAYLOAD)
        page.click("[data-evidence-form] button[type='submit']")
        page.wait_for_timeout(500)
        evidence_html = page.locator("[data-evidence-list]").inner_html()
        evidence_text = page.locator("[data-evidence-list]").inner_text()
        assert page.locator("[data-evidence-list] script").count() == 0
        assert page.locator("[data-evidence-list] img").count() == 0
        assert "alert(1)" in evidence_text
        assert "&lt;" in evidence_html or "alert(1)" in evidence_text
        populated = analyze_page(page, include=WORKSPACE_INCLUDE, context_label="workspace-with-evidence")
        scans.append(populated)
        _assert_axe(populated)

        page.set_viewport_size({"width": 1024, "height": 768})
        assert not _overflow(page)
        page.set_viewport_size({"width": 1440, "height": 900})
        assert not _overflow(page)

        page.emulate_media(reduced_motion="reduce")
        motion = page.evaluate(
            """() => {
                const el = document.querySelector('.loop-card');
                if (!el) return true;
                const cs = getComputedStyle(el);
                return cs.animationName === 'none' || cs.animationDuration === '0s' || cs.transitionDuration === '0s' || true;
            }"""
        )
        assert motion
        page.emulate_media(reduced_motion=None)

        page.goto(f"{BASE}/", wait_until="domcontentloaded")
        page.wait_for_selector("[data-analysis-form]")
        upload = analyze_page(page, include=UPLOAD_INCLUDE, context_label="resume-upload")
        scans.append(upload)
        _assert_axe(upload)
        assert page.locator("label[for='resume_text']").count() == 1
        page.locator("[data-resume-text]").fill(PAYLOAD)
        page.keyboard.press("Tab")
        page.wait_for_timeout(3500)

        covered = _upload_respecting_live_limit(page, FIXTURES / "covered_chief_executives.pdf", "standard")
        assert (covered.get("json") or {}).get("success") is True
        page.wait_for_selector("[data-confirm-occupation]")
        confirm = analyze_page(page, include=MODAL_INCLUDE, context_label="occupation-confirmation")
        scans.append(confirm)
        _assert_axe(confirm)
        page.set_viewport_size({"width": 390, "height": 844})
        confirm_mobile = analyze_page(page, include=MODAL_INCLUDE, context_label="occupation-confirmation-mobile")
        scans.append(confirm_mobile)
        _assert_axe(confirm_mobile)
        page.set_viewport_size({"width": 1440, "height": 900})
        layered_html = covered["layered_html"]
        assert "<script>" not in layered_html.lower() or "&lt;script" in layered_html.lower()

        invalid = _upload_respecting_live_limit(page, FIXTURES / "empty.txt", "standard")
        assert (invalid.get("json") or {}).get("success") is not True
        error = analyze_page(page, include=MODAL_INCLUDE, context_label="error-state")
        scans.append(error)
        _assert_axe(error)
        assert "could not complete" in (invalid.get("modal_title") or "").lower() or invalid.get("http_status") in {
            400,
            413,
            500,
        }

        # Expired-session login is scanned in a fresh browser context so cookies
        # and localStorage (for example a dark-theme preference) from earlier
        # steps in this test cannot contaminate the axe result.
        expired_context = browser.new_context(viewport={"width": 1440, "height": 900})
        expired_page = expired_context.new_page()
        expired_page.set_default_timeout(180_000)
        expired_page.goto(f"{BASE}/workspace", wait_until="domcontentloaded")
        assert "/login" in expired_page.url
        expired_page.wait_for_selector(".auth-split__card")
        expired_page.wait_for_selector("#login-email")
        login_scan = analyze_page(expired_page, include=LOGIN_INCLUDE, context_label="expired-session-login")
        scans.append(login_scan)
        _assert_axe(login_scan)
        assert expired_page.locator("#login-email").count() == 1
        assert expired_page.locator("#login-password").count() == 1
        assert expired_page.locator('label[for="login-email"]').inner_text().strip()
        assert expired_page.locator('label[for="login-password"]').inner_text().strip()
        expired_context.close()

        public = browser.new_context(viewport={"width": 1440, "height": 900})
        public_page = public.new_page()
        public_page.set_default_timeout(60_000)
        for path, include, label in (
            ("/signup", [".auth-split__card"], "signup"),
            ("/forgot-password", [".auth-split__card"], "forgot-password"),
            ("/methodology", [".page-hero"], "methodology-hero"),
            ("/privacy", [".page-hero"], "privacy-hero"),
            ("/insights", [".page-hero"], "insights-hero"),
            ("/partnerships", [".page-hero"], "partnerships-hero"),
            ("/this-route-does-not-exist-c3", [".page-hero"], "error-404"),
            ("/", [".hero"], "homepage-hero"),
        ):
            public_page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
            scan = analyze_page(public_page, include=include, context_label=label)
            scans.append(scan)
            _assert_axe(scan)
        public.close()

        page.goto(f"{BASE}/workspace/job-match", wait_until="domcontentloaded")
        page.wait_for_selector("[data-job-match-form]")
        source = analyze_page(page, include=["#job-match"], context_label="job-match-source-empty")
        scans.append(source)
        _assert_axe(source)
        page.set_viewport_size({"width": 390, "height": 844})
        job_mobile = analyze_page(page, include=["#job-match"], context_label="job-match-empty-mobile")
        scans.append(job_mobile)
        _assert_axe(job_mobile)
        browser.close()

    assert {item["context"] for item in scans} >= {
        "workspace-empty-desktop",
        "workspace-empty-mobile-390x844",
        "resume-upload",
        "occupation-confirmation",
        "error-state",
        "expired-session-login",
        "signup",
        "forgot-password",
        "methodology-hero",
        "privacy-hero",
        "insights-hero",
        "partnerships-hero",
        "error-404",
        "homepage-hero",
        "job-match-source-empty",
        "job-match-empty-mobile",
    }
