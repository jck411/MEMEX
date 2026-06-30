import unittest
from decimal import Decimal

from app.wiki.dashboard import SourceDashboardFilter, dashboard_snapshot
from app.wiki.dashboard_components_html import display_label
from app.wiki.dashboard_html import DashboardRenderOptions, render_dashboard_html
from app.wiki.ledger import ReviewDecision, WikiLedger
from app.wiki.model_profiles import DEFAULT_EXTRACTION_PROFILE_ID
from app.wiki.provider_balances import (
    ANTHROPIC_DASHBOARD_URL,
    GOOGLE_AI_STUDIO_BILLING_URL,
    OPENAI_BILLING_URL,
    OPENROUTER_LOGS_URL,
    ProviderBalance,
)
from app.wiki.wiki_scope import wiki_scope_signature
from tests.helpers import fact_record, source_record, wiki_record, wiki_registry
from tests.html_helpers import parse_html


class WikiDashboardHtmlTests(unittest.TestCase):
    def test_display_label_treats_stale_fact_decisions_as_needing_review(self):
        self.assertEqual("Needs review", display_label("stale accepted"))
        self.assertEqual("Needs review", display_label("stale rejected"))

    def test_render_dashboard_html_includes_filters_status_and_assignment_forms(self):
        registry = wiki_registry(
            wiki_record(
                "career",
                "Career",
                "career.md",
                description="Track durable employment history.",
            )
        )
        source = source_record(
            "source-1",
            fact_record("fact-1", "Alice joined Example Co."),
            summary="Alice joined Example Co.",
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")

        html = render_dashboard_html(
            dashboard_snapshot(registry, ledger, [source]),
            DashboardRenderOptions(source_filter=SourceDashboardFilter(search="profile")),
        )
        page = parse_html(html)
        page_text = page.normalized_text()
        filters = page.by_testid("source-filters")
        filter_form = filters.require("form", {"method": "get", "action": "/#source-search"})
        wiki_row = page.require(
            "article",
            {"data-testid": "wiki-row", "data-wiki-id": "career"},
        )
        source_row = page.require(
            "article",
            {"data-testid": "source-row", "data-source-id": "source-1"},
        )

        self.assertIn("Wiki Dashboard", page_text)
        self.assertIn("Search Sources", filters.normalized_text())
        filter_form.require(
            "input",
            {"type": "search", "name": "search", "value": "profile"},
        )
        filter_form.require("a", {"href": "/#source-search"})
        filter_form.require("button", {"type": "submit"})
        self.assertNotIn('data-auto-submit="1"', html)
        self.assertNotIn("requestSubmit", html)
        for name in ("unassigned", "needs_review", "needs_build"):
            filter_form.require("input", {"type": "checkbox", "name": name, "value": "1"})
        self.assertIn("Fact Review", page_text)
        self.assertIn("Wiki Build", page_text)
        self.assertIn("Career", wiki_row.normalized_text())
        self.assertIn("career.md", wiki_row.normalized_text())
        self.assertIn("1 source", wiki_row.normalized_text())
        self.assertIn("1 review", wiki_row.normalized_text())
        self.assertIn("0 accepted", wiki_row.normalized_text())
        self.assertIn("Needs review", wiki_row.normalized_text())
        wiki_row.require("a", {"href": "/wiki/career"})
        add_wiki_form = page.require("form", {"method": "post", "action": "/add-wiki"})
        add_wiki_form.require("input", {"name": "title"})
        description_form = wiki_row.require(
            "form",
            {"method": "post", "action": "/wiki-description"},
        )
        description_form.require("textarea", {"name": "description"})
        self.assertIn("Track durable employment history.", description_form.text())
        delete_wiki_form = wiki_row.require(
            "form",
            {"method": "post", "action": "/delete-wiki"},
        )
        delete_wiki_form.require("input", {"name": "wiki_id", "value": "career"})
        delete_wiki_form.require("button", {"aria-label": "Delete wiki"})
        assign_form = source_row.require("form", {"method": "post", "action": "/assign"})
        assign_form.require("input", {"name": "operation", "value": "unassign"})
        source_delete_form = source_row.require(
            "form",
            {
                "method": "post",
                "action": "/delete-source",
                "data-source-delete-form": "1",
            },
        )
        source_delete_form.require("input", {"name": "source_id", "value": "source-1"})
        source_delete_button = source_delete_form.require(
            "button",
            {"type": "submit", "class": "button button-danger delete-button"},
        )
        self.assertEqual("Delete source", source_delete_button.normalized_text())
        self.assertEqual(0, source_delete_form.count("button", {"aria-label": "Delete source"}))
        self.assertIn("memex:page-position", html)
        self.assertIn("rememberPagePosition(form", html)
        self.assertIn("restorePagePosition()", html)
        self.assertIn("adjacentAnchor(row, kind)", html)
        self.assertNotIn("confirm('Delete this source?')", html)
        self.assertNotIn("confirm('Delete this wiki?')", html)
        self.assertIn("Alice joined Example Co.", source_row.normalized_text())

    def test_render_dashboard_html_places_wikis_at_top_of_dashboard_sections(self):
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))
        source = source_record("source-1")

        html = render_dashboard_html(
            dashboard_snapshot(registry, WikiLedger.empty(), [source]),
            DashboardRenderOptions(
                extraction_enabled=True,
                extraction_model_spec=DEFAULT_EXTRACTION_PROFILE_ID,
            ),
        )
        page = parse_html(html)

        self.assertLess(
            page.by_testid("wikis-section").order,
            page.by_testid("ingest-section").order,
        )
        self.assertLess(
            page.by_testid("wikis-section").order,
            page.by_testid("source-filters").order,
        )
        self.assertLess(
            page.by_testid("source-filters").order,
            page.by_testid("sources-section").order,
        )

    def test_render_dashboard_html_build_form_uses_shared_busy_overlay(self):
        wiki = wiki_record("career", "Career", "career.md")
        registry = wiki_registry(wiki)
        source = source_record(
            "source-1",
            fact_record("fact-1", "Alice joined Example Co."),
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            ReviewDecision(
                ticked=True,
                fact_signature=source.facts[0].signature(),
                wiki_scope_signature=wiki_scope_signature(wiki),
                reason="Career history.",
            ),
        )

        html = render_dashboard_html(dashboard_snapshot(registry, ledger, [source]))
        page = parse_html(html)
        wikis = page.by_testid("wikis-section")
        build_form = wikis.require(
            "form",
            {
                "method": "post",
                "action": "/build",
                "class": "wiki-build-form",
            },
        )

        build_form.require("button", {"type": "submit"})
        page.require("div", {"id": "memex-busy-loader", "hidden": True})
        self.assertIn("memexSetFormBusy", html)
        self.assertIn("Building wiki", html)
        self.assertIn("wiki-build-form", html)

    def test_render_dashboard_html_includes_add_wiki_form_when_registry_is_empty(self):
        html = render_dashboard_html(
            dashboard_snapshot(wiki_registry(), WikiLedger.empty(), []),
        )
        page = parse_html(html)
        wikis = page.by_testid("wikis-section")
        add_wiki_form = wikis.require("form", {"method": "post", "action": "/add-wiki"})

        self.assertIn("Wikis", wikis.normalized_text())
        self.assertEqual(1, wikis.count("form", {"action": "/add-wiki"}))
        self.assertEqual(0, page.count("form", {"action": "/extract"}))
        self.assertLess(add_wiki_form.order, wikis.require("p").order)
        add_wiki_form.require(
            "input",
            {"name": "title", "placeholder": "Research", "aria-label": "Wiki name"},
        )
        add_wiki_form.require(
            "textarea",
            {
                "name": "description",
                "placeholder": "What facts belong in this wiki?",
                "aria-label": "Wiki description",
            },
        )
        self.assertEqual(0, wikis.count(attrs={"aria-label": "Wiki id"}))
        self.assertEqual(0, wikis.count(attrs={"aria-label": "Markdown path"}))
        self.assertIn("Add Wiki", wikis.normalized_text())
        self.assertIn("Cancel", wikis.normalized_text())
        self.assertIn(
            "MEMEX creates the internal id and Obsidian file automatically",
            wikis.normalized_text(),
        )
        self.assertIn("research.md", wikis.normalized_text())
        self.assertIn(
            "Scope instructions the LLM uses when reviewing facts for this wiki.",
            wikis.normalized_text(),
        )
        self.assertIn("Create Wiki", add_wiki_form.normalized_text())
        self.assertIn("No wikis yet.", wikis.normalized_text())

    def test_render_dashboard_html_includes_provider_balance_header(self):
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))

        html = render_dashboard_html(
            dashboard_snapshot(registry, WikiLedger.empty(), []),
            DashboardRenderOptions(
                provider_balances=(
                    ProviderBalance(
                        "openai",
                        "external",
                        "Balance",
                        url=OPENAI_BILLING_URL,
                    ),
                    ProviderBalance(
                        "anthropic",
                        "external",
                        "Balance",
                        url=ANTHROPIC_DASHBOARD_URL,
                    ),
                    ProviderBalance(
                        "google",
                        "external",
                        "Balance",
                        url=GOOGLE_AI_STUDIO_BILLING_URL,
                    ),
                    ProviderBalance(
                        "openrouter",
                        "available",
                        "$12.5000",
                        amount=Decimal("12.5"),
                        unit="usd",
                        detail="Balance: $12.5000; total=$20.0000; used=$7.5000",
                        url=OPENROUTER_LOGS_URL,
                    ),
                )
            ),
        )
        page = parse_html(html)

        self.assertIn("OpenAI", page.normalized_text())
        self.assertIn("Anthropic", page.normalized_text())
        self.assertIn("Google", page.normalized_text())
        self.assertIn("OpenRouter", page.normalized_text())
        for url in (
            OPENAI_BILLING_URL,
            ANTHROPIC_DASHBOARD_URL,
            GOOGLE_AI_STUDIO_BILLING_URL,
            OPENROUTER_LOGS_URL,
        ):
            page.require("a", {"href": url, "target": "_blank"})
        self.assertIn("$12.5000", page.normalized_text())
        balance_values = [
            node.normalized_text() for node in page.find_all("strong")
        ]
        self.assertEqual(3, balance_values.count("Balance"))

    def test_render_dashboard_html_treats_current_status_as_unlabeled_default(self):
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))
        source = source_record(
            "source-1",
            fact_record("fact-1", "Alice joined Example Co."),
        )

        html = render_dashboard_html(dashboard_snapshot(registry, WikiLedger.empty(), [source]))

        self.assertNotIn("<span>Current</span>", html)
        self.assertNotIn(">current</span>", html)
        self.assertNotIn("state-current", html)

    def test_render_dashboard_html_styles_error_and_success_toasts(self):
        snapshot = dashboard_snapshot(wiki_registry(), WikiLedger.empty(), [])

        error_html = render_dashboard_html(
            snapshot,
            DashboardRenderOptions(message="build failed", message_type="error"),
        )
        success_html = render_dashboard_html(
            snapshot,
            DashboardRenderOptions(message="successfully built career", message_type="success"),
        )
        error_page = parse_html(error_html)
        success_page = parse_html(success_html)

        error_toast = error_page.require("div", {"id": "toast"})
        success_toast = success_page.require("div", {"id": "toast"})
        self.assertEqual("toast toast-error", error_toast.attrs["class"])
        self.assertEqual("alert", error_toast.attrs["role"])
        self.assertEqual("assertive", error_toast.attrs["aria-live"])
        self.assertIn("build failed", error_toast.normalized_text())
        self.assertEqual("toast toast-success", success_toast.attrs["class"])
        self.assertEqual("status", success_toast.attrs["role"])
        self.assertIn("successfully built career", success_toast.normalized_text())

if __name__ == "__main__":
    unittest.main()
