"""Real-browser checks for the offline HTML report."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect, sync_playwright

from rtl_lens.models.analysis import ModuleGraph, TrendSummary
from rtl_lens.models.report import ScanReport
from rtl_lens.renderers.html_report import write_html_report

FIXTURE = Path(__file__).parents[1] / "fixtures" / "reports" / "partial-report.json"
REPRESENTATIVE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "reports" / "representative.json"


def test_html_relationship_search_is_locale_independent(tmp_path: Path) -> None:
    report = ScanReport.model_validate_json(REPRESENTATIVE_FIXTURE.read_text(encoding="utf-8"))
    report = report.model_copy(
        update={
            "module_graph": ModuleGraph(
                nodes=("ICore", "top"),
                edges=(("top", "ICore"),),
            )
        }
    )
    destination = tmp_path / "report.html"
    write_html_report(report, destination)

    with sync_playwright() as playwright:
        executable_path = os.environ.get("RTL_LENS_TEST_CHROMIUM")
        browser = playwright.chromium.launch(executable_path=executable_path)
        context = browser.new_context(locale="tr-TR")
        page = context.new_page()
        page.add_init_script(
            """
            String.prototype.toLocaleLowerCase = function () {
              return String(this).replaceAll("I", "ı").toLowerCase();
            };
            """
        )
        page.goto(destination.as_uri())

        page.get_by_label("Search module relationships").fill("icore")

        expect(page.locator("[data-testid='relationship-row']:visible")).to_have_count(1)
        expect(page.get_by_test_id("relationship-visible-count")).to_have_text(
            "1 relationship visible"
        )
        context.close()
        browser.close()


def test_html_incomplete_comparison_withholds_resolution_claims(tmp_path: Path) -> None:
    report = ScanReport.model_validate_json(REPRESENTATIVE_FIXTURE.read_text(encoding="utf-8"))
    report = report.model_copy(
        update={
            "trends": report.trends.model_copy(
                update={"resolved": (), "comparison_complete": False}
            )
        }
    )
    destination = tmp_path / "report.html"
    write_html_report(report, destination)

    with sync_playwright() as playwright:
        executable_path = os.environ.get("RTL_LENS_TEST_CHROMIUM")
        browser = playwright.chromium.launch(executable_path=executable_path)
        page = browser.new_page()
        page.goto(destination.as_uri())

        expect(page.get_by_test_id("baseline-trends")).to_contain_text(
            "Comparison unavailable or incomplete"
        )
        expect(page.get_by_test_id("baseline-trends")).to_contain_text("Resolution unavailable")
        expect(page.get_by_test_id("summary")).to_contain_text("Resolution unavailable")
        browser.close()


def test_html_relationship_search_is_offline_accessible_and_responsive(tmp_path: Path) -> None:
    report = ScanReport.model_validate_json(REPRESENTATIVE_FIXTURE.read_text(encoding="utf-8"))
    destination = tmp_path / "report.html"
    write_html_report(report, destination, graph_display_limit=3)
    requests: list[str] = []

    with sync_playwright() as playwright:
        executable_path = os.environ.get("RTL_LENS_TEST_CHROMIUM")
        browser = playwright.chromium.launch(executable_path=executable_path)
        page: Page = browser.new_page(viewport={"width": 390, "height": 844})
        page.on("request", lambda request: requests.append(request.url))
        page.goto(destination.as_uri())

        search = page.get_by_label("Search module relationships")
        rows = page.locator("[data-testid='relationship-row']:visible")
        count = page.get_by_test_id("relationship-visible-count")
        expect(search).to_be_visible()
        expect(rows).to_have_count(3)
        expect(count).to_have_text("3 relationships visible")
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement?.id === 'relationship-search'")
        assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle !== 'none'")

        search.fill("top")
        expect(rows).to_have_count(2)
        expect(count).to_have_text("2 relationships visible")
        search.fill("alu")
        expect(rows).to_have_count(2)
        search.fill('<script id="graph-script-owned">')
        expect(rows).to_have_count(1)
        expect(count).to_have_text("1 relationship visible")
        search.fill("")
        expect(page.get_by_test_id("baseline-trends")).to_contain_text("Baseline configured")
        expect(page.get_by_test_id("module-relationships")).to_contain_text("UNRESOLVED")
        expect(page.get_by_test_id("module-relationships")).to_contain_text(
            "Displaying 3 of 3 relationships"
        )
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator("#warning-owned, #graph-script-owned, #graph-owned").count() == 0
        assert page.evaluate("typeof window.__graphOwned === 'undefined'")

        no_script_context = browser.new_context(
            java_script_enabled=False,
            viewport={"width": 390, "height": 844},
        )
        no_script_page = no_script_context.new_page()
        no_script_page.on("request", lambda request: requests.append(request.url))
        no_script_page.goto(destination.as_uri())
        expect(no_script_page.locator("[data-testid='relationship-row']:visible")).to_have_count(3)
        expect(no_script_page.get_by_test_id("baseline-trends")).to_contain_text("2 NEW")
        expect(no_script_page.get_by_test_id("module-relationships")).to_contain_text("UNRESOLVED")
        no_script_context.close()
        browser.close()

    assert requests == [destination.as_uri(), destination.as_uri()]


def test_html_report_filters_offline_with_keyboard_at_narrow_width(tmp_path: Path) -> None:
    report = ScanReport.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    report = report.model_copy(
        update={
            "trends": TrendSummary(
                new=tuple(
                    finding.fingerprint
                    for finding in report.findings
                    if finding.baseline_state.value == "new"
                ),
                unchanged=tuple(
                    finding.fingerprint
                    for finding in report.findings
                    if finding.baseline_state.value == "existing"
                ),
                baseline_configuration_known=True,
                baseline_configured=True,
                comparison_complete=False,
            )
        }
    )
    destination = tmp_path / "report.html"
    write_html_report(report, destination)
    requests: list[str] = []

    with sync_playwright() as playwright:
        executable_path = os.environ.get("RTL_LENS_TEST_CHROMIUM")
        browser = playwright.chromium.launch(executable_path=executable_path)
        page: Page = browser.new_page(viewport={"width": 390, "height": 844})
        page.on("request", lambda request: requests.append(request.url))
        page.goto(destination.as_uri())

        expect(page.get_by_role("main")).to_be_visible()
        expect(page.get_by_test_id("visible-count")).to_have_text("3 findings visible")
        page.get_by_label("Severity").select_option("warning")
        expect(page.locator("[data-testid='finding-row']:visible")).to_have_count(1)
        expect(page.get_by_test_id("visible-count")).to_have_text("1 finding visible")
        page.get_by_label("Severity").select_option("all")
        page.get_by_label("Comparison", exact=True).select_option(label="Current / Matched")
        expect(page.locator("[data-testid='finding-row']:visible")).to_have_count(1)
        expect(page.locator("#baseline-filter option")).to_have_count(3)
        assert page.locator("#baseline-filter option").all_text_contents() == [
            "All comparison states",
            "Current / Unmatched",
            "Current / Matched",
        ]
        assert page.locator(".finding-meta span:nth-child(2)").all_text_contents() == [
            "CURRENT / UNMATCHED",
            "CURRENT / MATCHED",
            "CURRENT / UNMATCHED",
        ]
        expect(page.get_by_test_id("summary")).to_contain_text("Resolution unavailable")
        page.get_by_label("Comparison", exact=True).select_option("all")
        page.get_by_label("Engine", exact=True).select_option(label="verilator")
        expect(page.locator("[data-testid='finding-row']:visible")).to_have_count(1)

        page.get_by_label("Engine", exact=True).select_option(label="all")
        expect(page.locator("[data-testid='finding-row']:visible")).to_have_count(1)
        expect(page.locator("[data-testid='finding-row']:visible")).to_contain_text(
            "Unknown <em>diagnostic</em>"
        )
        hostile_engine = 'hostile"/><script id="engine-owned">window.__engineOwned=1</script>'
        page.get_by_label("Engine", exact=True).select_option(label=hostile_engine)
        expect(page.locator("[data-testid='finding-row']:visible")).to_have_count(1)
        expect(page.locator("[data-testid='finding-row']:visible")).to_contain_text(
            "Informational note"
        )
        expect(page.locator("#engine-owned")).to_have_count(0)
        assert page.evaluate("typeof window.__engineOwned === 'undefined'")

        page.get_by_label("Engine", exact=True).select_option(index=0)
        page.locator("body").press("Tab")
        assert page.evaluate(
            """() => {
                const active = document.activeElement;
                if (!(active instanceof HTMLElement)) return false;
                const style = getComputedStyle(active);
                return active.matches('a, button, select, input, textarea') &&
                    active.getBoundingClientRect().width > 0 &&
                    style.outlineStyle !== 'none';
            }"""
        )
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        expect(page.get_by_label("Severity")).to_be_visible()
        expect(page.locator("[data-testid='finding-row']:visible").first).to_be_visible()

        assert page.locator("#owned, #failure-owned, #version-owned").count() == 0
        assert page.evaluate(
            "typeof window.__owned === 'undefined' && "
            "typeof window.__failureOwned === 'undefined' && "
            "typeof window.__attrOwned === 'undefined'"
        )
        browser.close()

    assert requests == [destination.as_uri()]


@pytest.mark.parametrize(
    ("visible_text", "finding_title", "select_by_label"),
    [
        ("x\ny", "Assignment <strong>width</strong> mismatch", True),
        ("nul", "Unknown <em>diagnostic</em>", False),
    ],
)
def test_html_report_filters_engine_names_normalized_by_html(
    visible_text: str,
    finding_title: str,
    select_by_label: bool,
    tmp_path: Path,
) -> None:
    report = ScanReport.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    destination = tmp_path / "report.html"
    write_html_report(report, destination)

    with sync_playwright() as playwright:
        executable_path = os.environ.get("RTL_LENS_TEST_CHROMIUM")
        browser = playwright.chromium.launch(executable_path=executable_path)
        page: Page = browser.new_page()
        page.goto(destination.as_uri())

        option = page.locator("#engine-filter option").filter(has_text=visible_text)
        expect(option).to_have_count(1)
        engine_filter = page.get_by_label("Engine", exact=True)
        if select_by_label:
            expect(option).to_have_text(visible_text)
            engine_filter.select_option(label=visible_text)
        else:
            option_text = option.text_content()
            assert option_text is not None
            assert option_text.startswith("nul") and option_text.endswith("engine")
            token = option.get_attribute("value")
            assert token is not None
            engine_filter.select_option(token)
            expect(engine_filter).to_have_value(token)
            expect(engine_filter.locator("option:checked")).to_have_text(option_text)
        expect(page.locator("[data-testid='finding-row']:visible")).to_have_count(1)
        expect(page.locator("[data-testid='finding-row']:visible")).to_contain_text(finding_title)
        expect(page.locator("#engine-owned")).to_have_count(0)
        assert page.evaluate(
            "typeof window.__engineOwned === 'undefined' && typeof window.__owned === 'undefined'"
        )
        browser.close()
