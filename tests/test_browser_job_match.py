"""Live Target Job Match workflow. Requires Flask + --run-browser."""

from __future__ import annotations

import os

import pytest
import requests

from tests.axe_helper import analyze_page, assert_axe_installed, format_violations

BASE = os.environ.get("PRAYASH_BROWSER_BASE", "http://127.0.0.1:5000")
JOB_INCLUDE = ["#job-match"]
JD = (
    "Required: Python and SQL. Preferred: Tableau. Must have 3 years of experience. "
    "Bachelor degree preferred. Communication is required for stakeholder work."
)
PAYLOAD = '<script>alert(1)</script> Required: Python dashboards. Preferred: Excel reporting. ' + ("analysis " * 10)


def _assert_axe(results: dict) -> None:
    if results.get("violations"):
        pytest.fail(f"axe violations on {results.get('context')}\n{format_violations(results)}")


@pytest.mark.browser_live
def test_live_target_job_match(pytestconfig) -> None:
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
        page.goto(f"{BASE}/workspace/job-match", wait_until="domcontentloaded")
        assert "/login" in page.url

        page.fill("#login-email", "student")
        page.fill("#login-password", "Student@123")
        page.click("button[type='submit']")
        page.wait_for_load_state("domcontentloaded")
        page.goto(f"{BASE}/workspace", wait_until="domcontentloaded")
        page.goto(f"{BASE}/workspace/job-match", wait_until="domcontentloaded")
        page.wait_for_selector("[data-job-match-form]")
        source_copy = page.locator("[data-evidence-source-display]").inner_text()
        assert "This analysis used the following evidence source:" in source_copy
        assert "Current evidence profile" in page.locator("[data-evidence-source-value]").inner_text()
        assert "not a fresh reparse" in page.locator("#job-match").inner_text().lower()
        assert "choose which saved evidence" in page.locator("#job-match").inner_text().lower()
        assert page.locator("label[for='job-description']").count() == 1
        assert page.locator("label[for='resume-version']").count() == 1
        empty = analyze_page(page, include=JOB_INCLUDE, context_label="job-match-empty")
        _assert_axe(empty)
        page.set_viewport_size({"width": 390, "height": 844})
        mobile = analyze_page(page, include=JOB_INCLUDE, context_label="job-match-mobile")
        _assert_axe(mobile)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
        )
        assert not overflow
        page.set_viewport_size({"width": 1440, "height": 900})
        page.click("[data-job-match-form] button[type='submit']")
        page.wait_for_timeout(200)
        page.fill("#job-description", "too short")
        page.click("[data-job-match-form] button[type='submit']")
        page.wait_for_timeout(400)
        error_shown = page.locator("[data-job-error]").is_visible() or not page.locator("#job-description").evaluate(
            "el => el.validity.valid"
        )
        assert error_shown
        error = analyze_page(page, include=JOB_INCLUDE, context_label="job-match-error")
        _assert_axe(error)

        token = page.locator('meta[name="csrf-token"]').get_attribute("content")
        created = page.evaluate(
            """async ({token}) => {
              const res = await fetch('/api/resume-versions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
                body: JSON.stringify({name: 'Browser version', content_text: 'Python and PostgreSQL reporting projects with measurable outcomes.'})
              });
              let body = null;
              try { body = await res.json(); } catch (e) { body = await res.text(); }
              return {status: res.status, body};
            }""",
            {"token": token},
        )
        assert created["status"] in (200, 201), created
        assert isinstance(created["body"], dict) and created["body"].get("success") is True, created
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "() => [...document.querySelectorAll('#resume-version option')].some(o => (o.textContent || '').includes('Browser version'))",
            timeout=15_000,
        )
        page.check("input[name='evidence_source'][value='resume_version']")
        version_id = page.evaluate(
            """() => {
              const opt = [...document.querySelectorAll('#resume-version option')].find(
                (item) => (item.textContent || '').includes('Browser version')
              );
              return opt ? opt.value : '';
            }"""
        )
        assert version_id
        page.locator("#resume-version").select_option(value=version_id)
        page.fill("#job-title", "Analyst")
        page.fill("#job-company", "Example Co")
        page.fill("#job-location", "Remote")
        page.fill("#job-description", JD)
        page.click("[data-job-match-form] button[type='submit']")
        page.wait_for_function(
            "() => (document.querySelector('[data-req-list] li') || {}).textContent",
            timeout=15_000,
        )
        assert "This analysis used the following evidence source:" in page.locator("[data-evidence-source-display]").inner_text()
        assert "Browser version" in page.locator("[data-evidence-source-value]").inner_text()
        results = analyze_page(page, include=JOB_INCLUDE, context_label="job-match-results")
        _assert_axe(results)
        assert page.locator("[data-req-list] li").count() > 0
        marks = page.locator("[data-req-list] .tjm-status-mark").all_inner_texts()
        assert marks
        assert any(mark.strip() in {"M", "P", "N", "R"} for mark in marks)
        incomplete = page.locator("[data-incomplete-list]").inner_text().lower()
        if "not evidenced" in incomplete:
            assert "you don't have" not in incomplete
            assert "not evidenced in the selected source" in incomplete or "does not provide sufficient evidence" in incomplete
        action_body = page.locator("[data-job-action-body]").inner_text().lower()
        assert "hired" not in action_body
        assert "if you have" in action_body or "review" in action_body or "current" in action_body
        gap = page.locator("[data-job-gap]")
        if gap.count() and not gap.is_hidden():
            assert gap.inner_text().strip()
        if page.locator("[data-evidence-map] details summary").count():
            page.locator("[data-evidence-map] details summary").first.click()
            expanded = analyze_page(page, include=JOB_INCLUDE, context_label="job-match-evidence")
            _assert_axe(expanded)
        assert "evidence coverage" in page.locator(".lead").inner_text().lower()
        assert "job-loss" in page.locator(".lead").inner_text().lower()
        assert "not currently supported" in page.locator(".small-note").first.inner_text().lower()

        page.fill("#job-description", PAYLOAD)
        page.click("[data-job-match-form] button[type='submit']")
        page.wait_for_timeout(800)
        html = page.locator("[data-req-list]").inner_html()
        assert page.locator("[data-req-list] script").count() == 0
        assert page.locator("[data-req-list] img").count() == 0
        assert "alert(1)" not in html or "&lt;" in html or "python" in html.lower()

        page.fill("#job-description", "The team enjoys hiking and coffee together every Friday afternoon in the park nearby, with no technical stack listed anywhere here.")
        page.click("[data-job-match-form] button[type='submit']")
        page.wait_for_timeout(800)
        note = page.locator("[data-job-empty]").inner_text().lower()
        assert "no supported requirements" in note or page.locator("[data-req-list] li").count() == 0

        page.click("[data-delete-match]")
        page.wait_for_selector("[data-delete-dialog]:not([hidden])")
        delete_axe = analyze_page(page, include=["[data-delete-dialog]"], context_label="job-match-delete")
        _assert_axe(delete_axe)
        page.keyboard.press("Escape")
        page.wait_for_function("() => document.querySelector('[data-delete-dialog]').hidden === true")
        assert page.evaluate("() => document.activeElement && document.activeElement.matches('[data-delete-match]')")
        page.click("[data-delete-match]")
        page.wait_for_selector("[data-delete-dialog]:not([hidden])")
        page.click("[data-cancel-delete]")
        page.emulate_media(reduced_motion="reduce")
        page.keyboard.press("Tab")
        browser.close()
