"""Live workspace intent/evidence/next-action loop. Requires Flask + --run-browser."""

from __future__ import annotations

import os

import pytest
import requests

BASE = os.environ.get("PRAYASH_BROWSER_BASE", "http://127.0.0.1:5000")


@pytest.mark.browser_live
def test_live_workspace_goal_evidence_action(pytestconfig) -> None:
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

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60_000)
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.fill("#login-email", "student")
        page.fill("#login-password", "Student@123")
        page.click("button[type='submit']")
        page.wait_for_load_state("domcontentloaded")
        page.goto(f"{BASE}/workspace", wait_until="domcontentloaded")
        page.wait_for_selector("#goal-occupation option[value='15-1252.00']", state="attached")
        page.select_option("#goal-occupation", "15-1252.00")
        page.select_option("#goal-immediate", "Learn missing skills")
        page.fill("#goal-time", "5")
        page.click("[data-goal-form] button[type='submit']")
        page.wait_for_function("() => document.querySelector('[data-goal-summary]') && !document.querySelector('[data-goal-summary]').hidden")
        page.fill("#evidence-skill", "Python")
        page.fill("#evidence-span", "Built Python scripts for data processing")
        page.click("[data-evidence-form] button[type='submit']")
        page.wait_for_function("() => (document.querySelector('[data-action-title]') || {}).textContent")
        title = page.locator("[data-action-title]").inner_text()
        assert title
        page.click("[data-complete-action]")
        page.wait_for_function("() => /completed|Status/i.test(document.querySelector('[data-action-status]')?.textContent || '')")
        page.wait_for_selector(".skip-link", state="attached")
        assert page.locator("#main-content").count() == 1
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.locator("[data-goal-form]").is_visible()
        page.keyboard.press("Tab")
        browser.close()
