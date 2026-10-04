"""Live Phase 2 navigation. Requires Flask + --run-browser."""

from __future__ import annotations

import os

import pytest
import requests

from tests.axe_helper import analyze_page, assert_axe_installed, format_violations

BASE = os.environ.get("PRAYASH_BROWSER_BASE", "http://127.0.0.1:5000")


def _assert_axe(results: dict) -> None:
    if results.get("violations"):
        pytest.fail(f"axe violations on {results.get('context')}\n{format_violations(results)}")


@pytest.mark.browser_live
def test_live_start_intents_nav_keyboard_mobile(pytestconfig) -> None:
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
        context = browser.new_context(service_workers="block")
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.goto(f"{BASE}/", wait_until="domcontentloaded")
        start = page.locator("#start-here")
        assert start.locator("a", has_text="I know my target role").count() == 1
        assert start.locator("a", has_text="I have a job description").count() == 1
        assert start.locator("a", has_text="I want to explore careers").count() == 1
        assert start.locator("a", has_text="I want to understand my resume").count() == 1
        primary = page.locator('nav[aria-label="Primary"]')
        assert primary.get_by_role("link", name="Methodology").count() == 0
        start.locator("a", has_text="I want to understand my resume").focus()
        page.keyboard.press("Tab")
        _assert_axe(analyze_page(page, include=["#start-here"], context_label="start-here-guest"))
        _assert_axe(analyze_page(page, include=['nav[aria-label="Primary"]'], context_label="primary-nav-guest"))
        page.set_viewport_size({"width": 390, "height": 844})
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
        )
        assert not overflow
        page.click("[data-mobile-menu]")
        assert page.locator("[data-mobile-menu]").get_attribute("aria-expanded") == "true"
        page.goto(f"{BASE}/workspace/job-match", wait_until="domcontentloaded")
        assert "/login" in page.url
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.fill("#login-email", "student")
        page.fill("#login-password", "Student@123")
        page.click("button[type='submit']")
        page.wait_for_load_state("domcontentloaded")
        page.goto(f"{BASE}/", wait_until="domcontentloaded")
        assert page.locator('nav[aria-label="Primary"]').get_by_role("link", name="Applications").count() == 1
        assert page.locator('nav[aria-label="Primary"]').get_by_role("link", name="Target jobs").count() == 1
        page.goto(f"{BASE}/workspace/job-match", wait_until="domcontentloaded")
        assert "/workspace/job-match" in page.url
        page.goto(f"{BASE}/workspace/applications", wait_until="domcontentloaded")
        assert "/workspace/applications" in page.url
        _assert_axe(analyze_page(page, include=['nav[aria-label="Primary"]'], context_label="primary-nav-auth"))
        context.close()
        browser.close()
