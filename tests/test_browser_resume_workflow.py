"""Live Flask + Playwright resume workflow. CSRF stays enabled.

Run explicitly:

    pytest -q tests/test_browser_resume_workflow.py --run-browser -rs

Fails (does not skip) when --run-browser is set and the server is down.
Without --run-browser the test is skipped so the default suite still passes.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pandas as pd
import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "resumes"
BENCHMARK = (
    ROOT
    / "experiments"
    / "task_exposure"
    / "data"
    / "public_benchmark"
    / "public_gpts_are_gpts_benchmark.csv"
)
PRODUCT_800 = ROOT / "project_data" / "occupation_selection" / "occupation_master_800.csv"
WEAK_FILES = (
    ROOT / "project_data" / "task_exposure_labels" / "task_exposure_training.csv",
    ROOT / "project_data" / "task_exposure_labels" / "final_validated_task_training_table.csv",
)
PROHIBITED = (
    "you will lose your job",
    "chance of losing your job",
    "probability of job loss is",
    "62% chance",
)
BASE = os.environ.get("PRAYASH_BROWSER_BASE", "http://127.0.0.1:5000")
COVERED_CODE = "11-1011.00"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _server_up(url: str) -> bool:
    try:
        response = requests.get(url, timeout=3)
        return response.status_code < 500
    except requests.RequestException:
        return False


def _ollama_up() -> bool:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        response = requests.get(f"{host.rstrip('/')}/api/tags", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def _expected_distribution(code: str) -> dict[str, float]:
    frame = pd.read_csv(BENCHMARK, dtype=str, usecols=["occupation_code", "human_labels"])
    labels = (
        frame.loc[frame["occupation_code"] == code, "human_labels"]
        .str.strip()
        .str.upper()
        .tolist()
    )
    labelled = [item for item in labels if item in {"E0", "E1", "E2"}]
    n = len(labelled)
    return {cls: labelled.count(cls) / n for cls in ("E0", "E1", "E2")} | {"n": n}


def _in_product_800(code: str) -> bool:
    frame = pd.read_csv(PRODUCT_800, dtype=str, usecols=["occupation_code"])
    return code in set(frame["occupation_code"].str.strip())


def _ensure_fixtures() -> None:
    pdf = FIXTURES / "covered_chief_executives.pdf"
    if not pdf.is_file():
        from tests.fixtures.resumes.generate_browser_fixtures import main

        main()
    assert pdf.is_file()


def _ensure_oversized(path: Path) -> Path:
    size = 8 * 1024 * 1024 + 2048
    if not path.is_file() or path.stat().st_size <= 8 * 1024 * 1024:
        path.write_bytes(b"0" * size)
    return path


def _upload_and_analyze(page, file_path: Path, mode: str = "standard") -> dict:
    page.goto(f"{BASE}/", wait_until="domcontentloaded")
    page.wait_for_selector("[data-analysis-form]")
    page.locator("[data-resume-text]").fill("")
    form = page.locator("[data-analysis-form]")
    form.locator(f'[data-mode="{mode}"]').click()
    form.locator("[data-file-input]").set_input_files(str(file_path))
    with page.expect_response(
        lambda response: "/api/upload" in response.url and response.request.method == "POST",
        timeout=90_000,
    ) as pending:
        page.click("[data-assess-button]")
    response = pending.value
    payload = None
    text = ""
    try:
        payload = response.json()
    except Exception:
        text = response.text()[:2000]
    page.wait_for_function(
        """() => {
            const modal = document.querySelector('[data-result-modal]');
            const layered = document.querySelector('[data-layered-list]');
            const title = document.querySelector('[data-modal-title]');
            const open = modal && !modal.classList.contains('hidden');
            const t = (title && title.textContent) || '';
            const done = t && !/Analyzing|Processing/i.test(t);
            const failed = /Could not complete/i.test(t);
            const layeredReady = layered && (layered.textContent || '').length > 20;
            return open && done && (failed || layeredReady);
        }""",
        timeout=90_000,
    )
    time.sleep(0.3)
    body = page.locator("body").inner_text()
    layered = page.locator("[data-layered-list]").inner_text()
    narrative = page.locator("[data-narrative]").inner_text()
    html = page.locator("[data-layered-list]").inner_html()
    return {
        "json": payload,
        "http_status": response.status,
        "http_text": text,
        "body": body,
        "layered": layered,
        "narrative": narrative,
        "layered_html": html,
        "modal_title": page.locator("[data-modal-title]").inner_text(),
    }


def _confirm_occupation(page) -> dict:
    button = page.locator("[data-confirm-occupation]")
    if button.count() == 0:
        return {"json": None, "layered": page.locator("[data-layered-list]").inner_text()}
    with page.expect_response(
        lambda response: "/api/confirm-occupation" in response.url and response.request.method == "POST",
        timeout=90_000,
    ) as pending:
        button.first.click()
    response = pending.value
    payload = None
    try:
        payload = response.json()
    except Exception:
        payload = None
    page.wait_for_function(
        """() => {
            const layered = document.querySelector('[data-layered-list]');
            const text = (layered && layered.textContent) || '';
            return /Confirmed occupation|Verified benchmark occupation/i.test(text);
        }""",
        timeout=90_000,
    )
    return {
        "json": payload,
        "http_status": response.status,
        "layered": page.locator("[data-layered-list]").inner_text(),
        "layered_html": page.locator("[data-layered-list]").inner_html(),
        "narrative": page.locator("[data-narrative]").inner_text(),
        "body": page.locator("body").inner_text(),
    }


@pytest.mark.browser_live
def test_live_browser_resume_workflow(pytestconfig, tmp_path) -> None:
    if not pytestconfig.getoption("--run-browser"):
        pytest.skip("Needs live Flask; run with pytest --run-browser")

    if not _server_up(f"{BASE}/healthz") and not _server_up(BASE):
        pytest.fail(
            f"Flask is not running at {BASE}. Start `python app.py` then re-run "
            "pytest tests/test_browser_resume_workflow.py --run-browser"
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail("Playwright is not installed. pip install playwright && playwright install chromium")

    csrf_probe = requests.get(f"{BASE}/api/csrf-token", timeout=10)
    assert csrf_probe.status_code == 200
    token = csrf_probe.json()["csrf_token"]
    unauth = requests.post(
        f"{BASE}/api/upload",
        json={"resume_text": "Chief Executives " + ("experience " * 20), "mode": "standard"},
        timeout=30,
    )
    assert unauth.status_code == 400, f"CSRF should reject POST without token, got {unauth.status_code}"

    hashes_before = {str(path): _sha256(path) for path in WEAK_FILES if path.is_file()}
    assert hashes_before, "248-row archived files must still exist"

    _ensure_fixtures()
    expected_chief = _expected_distribution(COVERED_CODE)
    results: dict[str, str] = {}
    ollama_available = _ollama_up()

    oversized = _ensure_oversized(tmp_path / "oversized.pdf")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(180_000)

        covered_pdf = _upload_and_analyze(page, FIXTURES / "covered_chief_executives.pdf", "standard")
        payload = covered_pdf["json"] or {}
        te = payload.get("contextual_task_exposure") or payload.get("task_exposure") or {}
        match = payload.get("matched_occupation") or payload.get("occupation_match") or {}
        hist = payload.get("historical_occupation_reference") or {}
        assert payload.get("success") is True
        assert te.get("status") != "verified"
        assert te.get("distribution") is None
        assert match.get("status") == "candidate"
        assert "suggested occupation" in covered_pdf["layered"].lower() or "candidate" in covered_pdf["layered"].lower()
        confirmed = _confirm_occupation(page)
        payload = {**payload, **(confirmed.get("json") or {})}
        te = payload.get("contextual_task_exposure") or payload.get("task_exposure") or {}
        match = payload.get("matched_occupation") or payload.get("occupation_match") or {}
        matched_code = te.get("occupation_code") or match.get("verified_occupation_code")
        assert te.get("status") == "verified"
        assert match.get("status") == "confirmed"
        assert match.get("confirmation_method") == "candidate_confirmation"
        assert match.get("source") == "server_issued_candidate"
        assert match.get("match_method") in {"exact_code", "approved_crosswalk"}
        assert matched_code
        assert _in_product_800(str(matched_code)), f"{matched_code} is not in the 800 product subset"
        assert te.get("in_product_800") is True
        expected = _expected_distribution(str(matched_code))
        dist = te.get("distribution") or {}
        for cls in ("E0", "E1", "E2"):
            assert abs(float(dist[cls]) - float(expected[cls])) < 1e-9
        assert abs(sum(float(dist[k]) for k in ("E0", "E1", "E2")) - 1.0) < 1e-9
        counts = te.get("occupation_wide_counts") or {}
        assert sum(int(counts.get(k, 0)) for k in ("E0", "E1", "E2")) == int(
            te.get("labelled_task_count") or expected["n"]
        )
        assert hist.get("score") is not None
        assert "not a validated personal probability" in (hist.get("interpretation") or "").lower()
        combined = (covered_pdf["body"] + confirmed["layered"]).lower()
        assert "historical occupation reference" in combined
        for phrase in PROHIBITED:
            assert phrase not in combined
        results["pdf_covered"] = "PASS"
        results["match_method"] = match.get("match_method")
        results["matched_code"] = str(matched_code)
        results["historical"] = "PASS"
        results["e012"] = "PASS"
        results["denominator"] = "PASS"
        results["product_800"] = "PASS"
        results["candidate_confirm"] = "PASS"

        select_upload = _upload_and_analyze(page, FIXTURES / "covered_chief_executives.pdf", "standard")
        select_payload = select_upload["json"] or {}
        assert select_payload.get("analysis_id")
        page.locator("[data-choose-occupation]").first.click()
        page.wait_for_selector("[data-occupation-select]")
        page.select_option("[data-occupation-select]", "15-1252.00")
        with page.expect_response(
            lambda response: "/api/select-occupation" in response.url and response.request.method == "POST",
            timeout=90_000,
        ) as pending_select:
            page.locator("[data-apply-occupation]").click()
        select_resp = pending_select.value
        select_json = select_resp.json()
        assert select_resp.status == 200
        assert select_json.get("success") is True
        select_match = select_json.get("occupation_match") or {}
        assert select_match.get("confirmation_method") == "user_selected_occupation"
        assert select_match.get("source") == "user_selection"
        assert select_match.get("verified_occupation_code") == "15-1252.00"
        assert (select_json.get("task_exposure") or {}).get("status") == "verified"
        results["manual_select"] = "PASS"

        reject_upload = _upload_and_analyze(page, FIXTURES / "covered_chief_executives.pdf", "standard")
        reject_ids = reject_upload["json"] or {}
        codes_800 = set(pd.read_csv(PRODUCT_800, dtype=str)["occupation_code"].astype(str).str.strip())
        bench = pd.read_csv(BENCHMARK, dtype=str)
        only_923 = sorted(
            code
            for code in bench["occupation_code"].astype(str).str.strip().unique()
            if code not in codes_800 and code
        )
        assert only_923
        csrf_token = page.locator('meta[name="csrf-token"]').get_attribute("content")
        forged = page.evaluate(
            """async ({analysisId, candidateId, code, csrf}) => {
                const missing = await fetch('/api/confirm-occupation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({analysis_id: analysisId, candidate_id: candidateId, action: 'confirm_candidate'})
                });
                const only923 = await fetch('/api/select-occupation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
                    body: JSON.stringify({
                        analysis_id: analysisId,
                        selected_code: code,
                        action: 'select_occupation',
                        in_product_800: true
                    })
                });
                const garbage = await fetch('/api/select-occupation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
                    body: JSON.stringify({analysis_id: analysisId, selected_code: 'not-a-soc', action: 'select_occupation'})
                });
                const wrongId = await fetch('/api/confirm-occupation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
                    body: JSON.stringify({analysis_id: analysisId, candidate_id: 'wrong', action: 'confirm_candidate'})
                });
                const forgedCandidate = await fetch('/api/confirm-occupation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
                    body: JSON.stringify({
                        analysis_id: analysisId,
                        candidate_id: candidateId,
                        action: 'confirm_candidate',
                        verified_occupation_code: '15-1252.00',
                        confirmation_method: 'resume_verified_occupation'
                    })
                });
                return {
                    missing: {status: missing.status, body: await missing.json().catch(() => ({}))},
                    forged: {status: forgedCandidate.status, body: await forgedCandidate.json().catch(() => ({}))},
                    only923: {status: only923.status, body: await only923.json().catch(() => ({}))},
                    garbage: {status: garbage.status, body: await garbage.json().catch(() => ({}))},
                    wrongId: {status: wrongId.status, body: await wrongId.json().catch(() => ({}))},
                };
            }""",
            {
                "analysisId": reject_ids.get("analysis_id"),
                "candidateId": reject_ids.get("candidate_id"),
                "code": only_923[0],
                "csrf": csrf_token,
            },
        )
        missing_text = str(forged["missing"]).lower()
        assert forged["missing"]["status"] == 400
        assert forged["missing"]["body"].get("success") is not True
        assert "csrf" in missing_text or forged["missing"]["body"].get("success") is not True
        assert forged["only923"]["status"] == 400
        assert forged["only923"]["body"].get("error_code") == "occupation_outside_product_scope"
        assert forged["garbage"]["status"] == 400
        assert forged["wrongId"]["status"] in {400, 403}
        if forged["forged"]["status"] == 200:
            forged_code = (forged["forged"]["body"].get("occupation_match") or {}).get("verified_occupation_code")
            stored_code = (reject_ids.get("occupation_match") or {}).get("candidate_code")
            assert forged_code == stored_code
            assert (forged["forged"]["body"].get("occupation_match") or {}).get("confirmation_method") == "candidate_confirmation"
        results["reject_923_only"] = "PASS"
        results["reject_forged_candidate"] = "PASS"
        results["reject_missing_csrf"] = "PASS"
        results["reject_wrong_candidate"] = "PASS"

        covered_docx = _upload_and_analyze(page, FIXTURES / "covered_chief_executives.docx", "standard")
        assert (covered_docx["json"] or {}).get("success") is True
        assert ((covered_docx["json"] or {}).get("contextual_task_exposure") or {}).get("status") != "verified"
        results["docx_covered"] = "PASS"

        unresolved = _upload_and_analyze(page, FIXTURES / "unresolved_galactic_cartographer.pdf", "standard")
        ute = (unresolved["json"] or {}).get("contextual_task_exposure") or {}
        assert unresolved["json"].get("success") is True
        assert ute.get("status") != "verified"
        assert ute.get("distribution") is None
        results["unresolved"] = "PASS"

        invalid = _upload_and_analyze(page, FIXTURES / "empty.txt", "standard")
        if (invalid["json"] or {}).get("success") is True:
            pytest.fail("empty upload must not succeed")
        assert invalid.get("http_status") in {400, 413, 500} or "could not complete" in invalid["modal_title"].lower()
        results["invalid"] = "PASS"

        page.goto(f"{BASE}/", wait_until="domcontentloaded")
        page.locator("[data-resume-text]").fill("")
        page.set_input_files("[data-file-input]", str(oversized))
        with page.expect_response(
            lambda response: "/api/upload" in response.url and response.request.method == "POST",
            timeout=60_000,
        ) as pending:
            page.click("[data-assess-button]")
        oversized_resp = pending.value
        oversized_json = None
        try:
            oversized_json = oversized_resp.json()
        except Exception:
            pass
        oversized_text = (page.locator("body").inner_text() + str(oversized_json) + oversized_resp.text()[:500]).lower()
        assert oversized_resp.status in {413, 400} or "too large" in oversized_text or "could not complete" in oversized_text
        if oversized_json and oversized_json.get("success") is True:
            pytest.fail("Oversized upload must not return a successful analysis")
        results["oversized"] = "PASS"

        injected = _upload_and_analyze(page, FIXTURES / "prompt_injection_chief_executives.pdf", "standard")
        inj = injected["json"] or {}
        inj_te = inj.get("contextual_task_exposure") or {}
        assert inj.get("success") is True
        assert inj_te.get("status") != "verified"
        inj_text = (injected["layered"] + injected["narrative"]).lower()
        assert "probability of job loss is" not in inj_text
        assert "<img" not in injected["layered_html"].lower()
        inj_confirmed = _confirm_occupation(page)
        inj_merged = {**inj, **(inj_confirmed.get("json") or {})}
        inj_te = inj_merged.get("contextual_task_exposure") or {}
        if inj_te.get("status") == "verified":
            inj_code = str(inj_te.get("occupation_code") or "")
            inj_expected = _expected_distribution(inj_code) if inj_code else expected_chief
            for cls in ("E0", "E1", "E2"):
                assert abs(float(inj_te["distribution"][cls]) - float(inj_expected[cls])) < 1e-9
        inj_after = (inj_confirmed.get("layered") or "") + (inj_confirmed.get("narrative") or "")
        assert "probability of job loss is" not in inj_after.lower()
        results["prompt_injection"] = "PASS"
        results["safe_rendering"] = "PASS"

        disabled = _upload_and_analyze(page, FIXTURES / "covered_chief_executives.pdf", "standard")
        ollama = (disabled["json"] or {}).get("ollama") or {}
        assert ollama.get("enabled") is False
        assert (disabled["json"] or {}).get("success") is True
        results["ollama_disabled"] = "PASS"

        advanced = _upload_and_analyze(page, FIXTURES / "prompt_injection_chief_executives.pdf", "advanced")
        adv = advanced["json"] or {}
        adv_te = adv.get("contextual_task_exposure") or {}
        if adv_te.get("status") == "verified":
            adv_expected = _expected_distribution(str(adv_te.get("occupation_code")))
            for cls in ("E0", "E1", "E2"):
                assert abs(float(adv_te["distribution"][cls]) - float(adv_expected[cls])) < 1e-9
        adv_ollama = adv.get("ollama") or {}
        narrative = (advanced["narrative"] or "").lower()
        assert "you will lose your job" not in narrative
        assert "99%" not in narrative or "e1" not in narrative
        if ollama_available:
            if adv_ollama.get("available"):
                results["ollama_enabled"] = "PASS"
                results["ollama_unavailable"] = "BLOCKED"
            else:
                results["ollama_enabled"] = "FAIL"
                results["ollama_unavailable"] = "PASS" if "structured analysis is still available" in (adv_ollama.get("message") or "").lower() else "FAIL"
        else:
            results["ollama_enabled"] = "BLOCKED"
            msg = (adv_ollama.get("message") or advanced["narrative"] or "").lower()
            assert adv.get("success") is True
            assert adv_te.get("status") != "verified" or adv_te.get("source_type") == "published_benchmark_lookup"
            results["ollama_unavailable"] = "PASS" if "structured analysis is still available" in msg or adv_ollama.get("available") is False else "FAIL"

        browser.close()

    hashes_after = {str(path): _sha256(path) for path in WEAK_FILES if path.is_file()}
    assert hashes_before == hashes_after
    results["weak_supervision_integrity"] = "PASS"
    results["csrf"] = "PASS"
    results["server"] = BASE
    results["ollama_probe"] = "available" if ollama_available else "unavailable"

    print("\nPDF covered occupation:", results["pdf_covered"])
    print("DOCX covered occupation:", results["docx_covered"])
    print("Unresolved occupation:", results["unresolved"])
    print("Invalid upload:", results["invalid"])
    print("Oversized upload:", results["oversized"])
    print("Prompt injection:", results["prompt_injection"])
    print("Ollama disabled:", results["ollama_disabled"])
    print("Ollama enabled:", results["ollama_enabled"])
    print("Ollama unavailable fallback:", results["ollama_unavailable"])
    print("Match method:", results["match_method"])
    print("Candidate confirm:", results.get("candidate_confirm"))
    print("Manual select:", results.get("manual_select"))
    print("923-only reject:", results.get("reject_923_only"))

    out = ROOT / "docs" / "BROWSER_VERIFICATION_RESULTS.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
