"""Run axe-core against a Python Playwright page.

Live browser tests use ``playwright.sync_api``, not ``@playwright/test``.
``@axe-core/playwright`` AxeBuilder wraps the same ``axe-core`` engine
(``node_modules/axe-core/axe.min.js``). This helper injects that engine and
calls ``axe.run``, which is the repository-appropriate equivalent of:

    import AxeBuilder from "@axe-core/playwright";
    await new AxeBuilder({ page }).analyze();

Do not globally disable rules. Callers may pass a narrow CSS exclude list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AXE_PACKAGE = ROOT / "node_modules" / "@axe-core" / "playwright" / "package.json"
AXE_SOURCE = ROOT / "node_modules" / "axe-core" / "axe.min.js"


def assert_axe_installed() -> None:
    if not AXE_PACKAGE.is_file():
        raise AssertionError("@axe-core/playwright is missing from node_modules; do not reinstall unless the package is absent")
    if not AXE_SOURCE.is_file():
        raise AssertionError("axe-core axe.min.js is missing (dependency of @axe-core/playwright)")


def analyze_page(
    page,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    context_label: str = "",
) -> dict[str, Any]:
    """Return axe results. Include/exclude are CSS selectors (narrow, never global rule disables)."""
    assert_axe_installed()
    nonce = page.evaluate(
        """() => {
            const tagged = document.querySelector('script[nonce]');
            return (tagged && (tagged.nonce || tagged.getAttribute('nonce'))) || '';
        }"""
    )
    source = AXE_SOURCE.read_text(encoding="utf-8")
    page.evaluate(
        """({ source, nonce }) => {
            if (window.axe) return;
            const script = document.createElement('script');
            if (nonce) script.setAttribute('nonce', nonce);
            script.textContent = source;
            document.documentElement.appendChild(script);
        }""",
        {"source": source, "nonce": nonce or ""},
    )
    payload = page.evaluate(
        """async ({ includeSelectors, excludeSelectors }) => {
            const options = { reporter: "v2" };
            const hasInclude = includeSelectors && includeSelectors.length;
            const hasExclude = excludeSelectors && excludeSelectors.length;
            let results;
            if (hasInclude || hasExclude) {
                const context = {};
                if (hasInclude) context.include = includeSelectors.map((sel) => [sel]);
                if (hasExclude) context.exclude = excludeSelectors.map((sel) => [sel]);
                results = await axe.run(context, options);
            } else {
                results = await axe.run(options);
            }
            return {
                violations: results.violations.map((v) => ({
                    id: v.id,
                    impact: v.impact,
                    description: v.description,
                    help: v.help,
                    helpUrl: v.helpUrl,
                    nodes: v.nodes.map((n) => ({
                        html: (n.html || "").slice(0, 240),
                        target: n.target,
                        failureSummary: (n.failureSummary || "").slice(0, 400),
                    })),
                })),
                passes: (results.passes || []).length,
                inapplicable: (results.inapplicable || []).map((r) => r.id),
                incomplete: (results.incomplete || []).map((r) => ({
                    id: r.id,
                    nodes: (r.nodes || []).length,
                })),
            };
        }""",
        {"includeSelectors": include or [], "excludeSelectors": exclude or []},
    )
    payload["context"] = context_label
    payload["include"] = include or []
    payload["exclude"] = exclude or []
    return payload


def format_violations(results: dict[str, Any]) -> str:
    rows = []
    for item in results.get("violations") or []:
        targets = [", ".join(str(t) for t in (node.get("target") or [])) for node in item.get("nodes") or []]
        rows.append(f"{item.get('id')} ({item.get('impact')}): {item.get('help')}; targets={targets}")
    return "\n".join(rows)


def write_report(path: Path, scans: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(scans, indent=2), encoding="utf-8")
