"""Live save-job tracker. Requires Flask + --run-browser."""

from __future__ import annotations

import os

import pytest
import requests

from tests.axe_helper import analyze_page, assert_axe_installed, format_violations

BASE = os.environ.get("PRAYASH_BROWSER_BASE", "http://127.0.0.1:5000")
JD = (
    "Required: Python and SQL. Preferred: Tableau. Must have 3 years of experience. "
    "Bachelor degree preferred. Communication is required for stakeholder work."
)


def _assert_axe(results: dict) -> None:
    if results.get("violations"):
        pytest.fail(f"axe violations on {results.get('context')}\n{format_violations(results)}")


@pytest.mark.browser_live
def test_live_save_job_and_applications_list(pytestconfig) -> None:
    if not pytestconfig.getoption("--run-browser"):
        pytest.skip("Needs live Flask; run with pytest --run-browser")
    try:
        requests.get(f"{BASE}/healthz", timeout=5)
    except Exception:
        pytest.fail(f"Flask is not running at {BASE}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail("Playwright is not installed")
    assert_axe_installed()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60_000)
        page.goto(f"{BASE}/workspace/applications", wait_until="domcontentloaded")
        assert "/login" in page.url
        page.fill("#login-email", "student")
        page.fill("#login-password", "Student@123")
        page.click("button[type='submit']")
        page.wait_for_load_state("domcontentloaded")
        page.goto(f"{BASE}/workspace/applications", wait_until="domcontentloaded")
        if page.locator("[data-applications-list] li").count() == 0:
            assert "no saved jobs yet" in page.locator("[data-applications-empty]").inner_text().lower()
            empty_axe = analyze_page(page, include=["#saved-jobs"], context_label="applications-empty")
            _assert_axe(empty_axe)
        page.keyboard.press("Tab")
        page.goto(f"{BASE}/workspace", wait_until="domcontentloaded")
        page.goto(f"{BASE}/workspace/job-match", wait_until="domcontentloaded")
        page.fill("#job-title", "Analyst")
        page.fill("#job-company", "Example Co")
        page.fill("#job-description", JD)
        page.click("[data-job-match-form] button[type='submit']")
        page.wait_for_function(
            "() => (document.querySelector('[data-req-list] li') || {}).textContent",
            timeout=15_000,
        )
        page.wait_for_selector("[data-save-application]:not([hidden])")
        page.click("[data-save-application]")
        page.click("[data-save-application]")
        page.wait_for_function(
            "() => (document.querySelector('[data-save-application-status]') || {}).textContent",
            timeout=15_000,
        )
        notice = page.locator("[data-save-application-status]").inner_text().lower()
        assert "ats score or a prediction that you will be hired" in notice
        page.goto(f"{BASE}/workspace/applications", wait_until="domcontentloaded")
        page.wait_for_selector("[data-applications-list] li")
        assert "not an ats score" in page.locator(".lead").inner_text().lower()
        empty = analyze_page(page, include=["#saved-jobs"], context_label="applications-list")
        _assert_axe(empty)
        page.locator("select[id^='application-status-']").first.select_option("Applying")
        page.locator("input[id^='application-follow-']").first.fill("2020-01-02")
        page.locator("textarea[id^='application-notes-']").first.fill("Remind to attach a Python project example.")
        page.get_by_role("button", name="Save changes").first.click()
        page.get_by_role("button", name="Mark applied").first.click()
        page.wait_for_timeout(400)
        assert page.locator("select[id^='application-status-']").first.input_value() == "Applied"
        page.route("**/api/applications/**", lambda route: route.abort() if route.request.method == "PATCH" else route.continue_())
        page.get_by_role("button", name="Save changes").first.click()
        page.wait_for_selector("[data-applications-error]:not([hidden])")
        page.unroute("**/api/applications/**")
        page.set_viewport_size({"width": 390, "height": 844})
        mobile = analyze_page(page, include=["#saved-jobs"], context_label="applications-mobile")
        _assert_axe(mobile)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
        )
        assert not overflow
        expired = browser.new_context()
        expired_page = expired.new_page()
        expired_page.goto(f"{BASE}/workspace/applications", wait_until="domcontentloaded")
        assert "/login" in expired_page.url
        expired.close()
        browser.close()
