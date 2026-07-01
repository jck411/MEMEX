import unittest

from app.wiki.dashboard import dashboard_snapshot
from app.wiki.dashboard_html import DashboardRenderOptions, render_dashboard_html
from app.wiki.ledger import ReviewDecision, WikiLedger
from app.wiki.source_detail import source_detail_view
from app.wiki.source_detail_html import render_source_detail_html
from app.wiki.source_fix import SOURCE_FIX_MODEL
from app.wiki.wiki_scope import wiki_scope_signature
from tests.helpers import fact_record, source_record, wiki_record, wiki_registry
from tests.html_helpers import parse_html


class WikiSourceDetailHtmlTests(unittest.TestCase):
    def test_source_rows_link_to_detail_with_automatic_decision_save(self):
        registry = wiki_registry(
            wiki_record("career", "Career", "career.md"),
            wiki_record("tax", "Tax", "tax.md"),
        )
        source = source_record(
            "source-1",
            fact_record(
                "fact-1",
                "Alice joined Example Co. in 2024.",
                provenance={
                    "evidence": [
                        {
                            "id": "ev-joined",
                            "quote": "Alice joined Example Co. in 2024.",
                            "source_channel": "pdf_text",
                            "page": 2,
                            "locator": "paragraph 4",
                        }
                    ],
                },
            ),
            summary="Alice profile summary.",
            document_date="2024-02-01",
            source_type="profile",
            extraction_issues=("Review employment date.",),
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        ledger.assign_source("tax", "source-1")
        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            ReviewDecision(
                ticked=True,
                fact_signature=source.facts[0].signature(),
                wiki_scope_signature=wiki_scope_signature(registry.wikis["career"]),
                reason="Employment history belongs in Career.",
            ),
        )
        snapshot = dashboard_snapshot(registry, ledger, [source])

        html = render_dashboard_html(snapshot)
        detail_html = render_source_detail_html(
            snapshot,
            source_detail_view(registry, ledger, [source], "source-1"),
        )
        ai_detail_html = render_source_detail_html(
            snapshot,
            source_detail_view(registry, ledger, [source], "source-1"),
            DashboardRenderOptions(source_llm_review_enabled=True),
        )
        fix_detail_html = render_source_detail_html(
            snapshot,
            source_detail_view(registry, ledger, [source], "source-1"),
            DashboardRenderOptions(source_fix_enabled=True),
        )
        dashboard_page = parse_html(html)
        detail_page = parse_html(detail_html)
        ai_detail_page = parse_html(ai_detail_html)
        fix_detail_page = parse_html(fix_detail_html)
        hero = detail_page.by_testid("source-detail-hero")
        repair = detail_page.by_testid("source-repair")
        issues = detail_page.by_testid("source-issues")
        facts = detail_page.by_testid("source-facts")

        dashboard_page.require("a", {"href": "/source/source-1"})
        dashboard_page.require("form", {"method": "post", "action": "/delete-source"})
        detail_page.require("a", {"href": "/", "aria-label": "MEMEX — dashboard"})
        back_link = detail_page.require("a", {"href": "/", "aria-label": "Back"})
        back_icon = back_link.require("svg", {"class": "button-icon-svg back-icon-svg"})
        back_path = back_icon.require("path")
        self.assertEqual("0 0 16 16", back_icon.attrs["viewbox"])
        self.assertEqual("M5 8l6-5v10z", back_path.attrs["d"])
        self.assertEqual("currentColor", back_path.attrs["fill"])
        self.assertNotIn("stroke", back_path.attrs)
        self.assertNotIn("Back to source list", detail_page.normalized_text())
        self.assertIn("source-1 · 1 fact · 1 issue", hero.normalized_text())
        self.assertIn("Profile", hero.normalized_text())
        self.assertNotIn("Alice profile summary.", hero.normalized_text())
        self.assertNotIn("2024-02-01", hero.normalized_text())
        self.assertNotIn("Review Delta", detail_page.normalized_text())
        self.assertIn("Alice joined Example Co. in 2024.", facts.normalized_text())
        self.assertIn("ev-joined", facts.normalized_text())
        self.assertIn("Review employment date.", issues.normalized_text())
        facts.require("article", {"class": "fact-row", "data-fact-id": "fact-1"})
        issues.require("article", {"class": "issue-row", "data-issue-index": "0"})
        facts.require("textarea", {"name": "fact_text", "aria-label": "Fact text"})
        facts.require("button", {"aria-label": "Save fact"})
        facts.require("button", {"aria-label": "Delete fact"})
        issues.require("textarea", {"name": "issue_text", "aria-label": "Issue text"})
        issues.require("button", {"aria-label": "Save issue"})
        issues.require("button", {"aria-label": "Remove issue"})
        self.assertEqual(0, detail_page.count(attrs={"aria-label": "Edit fact"}))
        self.assertEqual(0, detail_page.count(attrs={"aria-label": "Edit issue"}))
        self.assertGreater(
            detail_page.count("input", {"name": "partial_repair", "value": "1"}),
            0,
        )
        self.assertNotIn("Repair Extraction", detail_page.normalized_text())
        self.assertNotIn("Repair Source", detail_page.normalized_text())
        self.assertNotIn("Edit Source Info", detail_page.normalized_text())
        repair.require("input", {"name": "title", "aria-label": "Title", "value": "Profile"})
        repair.require("textarea", {"name": "summary", "aria-label": "Summary"})
        repair.require(
            "input",
            {
                "name": "document_date",
                "aria-label": "Document date",
                "value": "2024-02-01",
            },
        )
        repair.require(
            "input",
            {"name": "source_type", "aria-label": "Source type", "value": "profile"},
        )
        self.assertIn("Alice profile summary.", repair.normalized_text())
        repair.require("button", {"aria-label": "Save summary"})
        repair.require("button", {"aria-label": "Clear summary"})
        repair.require("button", {"aria-label": "Clear document date"})
        repair.require("button", {"aria-label": "Clear source type"})
        self.assertNotIn("×", repair.text())
        self.assertIn("Add Fact", facts.normalized_text())
        decision_form = facts.require(
            "form",
            {
                "method": "post",
                "action": "/source-decisions",
                "id": "source-decisions-form",
            },
        )
        decision_form.require("input", {"name": "return_to", "value": "/source/source-1"})
        facts.require(
            "input",
            {
                "type": "checkbox",
                "name": "accepted_decision",
                "form": "source-decisions-form",
                "data-decision-key": '["fact-1","career"]',
                "data-wiki-id": "career",
            },
        )
        facts.require("input", {"data-wiki-id": "tax"})
        for wiki_id in ("career", "tax"):
            facts.require(
                "button",
                {"data-decision-wiki": wiki_id, "data-decision-checked": "true"},
            )
            facts.require(
                "button",
                {"data-decision-wiki": wiki_id, "data-decision-checked": "false"},
            )
        self.assertIn('name="changed_decision"', detail_html)
        self.assertNotIn('name="decision"', detail_html)
        self.assertIn("Employment history belongs in Career.", facts.normalized_text())
        self.assertEqual(
            2,
            len(
                [
                    button
                    for button in facts.find_all("button", {"data-decision-checked": "true"})
                    if button.normalized_text() == "Select all"
                ]
            ),
        )
        self.assertEqual(
            2,
            len(
                [
                    button
                    for button in facts.find_all("button", {"data-decision-checked": "false"})
                    if button.normalized_text() == "Clear all"
                ]
            ),
        )
        self.assertNotIn("Save Decisions", facts.normalized_text())
        self.assertEqual(0, facts.count("button", {"form": "source-decisions-form"}))
        self.assertIn("submitDecisionForm", detail_html)
        self.assertIn("markWikiDecisionsDirty", detail_html)
        self.assertIn("requestSubmit", detail_html)
        self.assertIn("Saving decisions", detail_html)
        self.assertIn("memex:page-position", detail_html)
        self.assertIn("rememberPagePosition(form", detail_html)
        self.assertIn("restorePagePosition()", detail_html)
        self.assertEqual(0, detail_page.count(attrs={"data-testid": "source-actions"}))
        self.assertEqual(0, detail_page.count("form", {"action": "/delete-source"}))
        self.assertNotIn("Source Actions", detail_page.normalized_text())
        self.assertNotIn("Delete Source", detail_page.normalized_text())
        self.assertNotIn("confirm('Delete this source?')", detail_html)
        self.assertIn("Needs review", facts.normalized_text())
        self.assertEqual(0, detail_page.count("dialog"))
        self.assertEqual(0, detail_page.count("form", {"action": "/review"}))
        self.assertEqual(0, detail_page.count("form", {"action": "/source-llm-review"}))
        self.assertEqual(0, detail_page.count("form", {"action": "/fact-decisions"}))
        ai_facts = ai_detail_page.by_testid("source-facts")
        ai_facts.require("form", {"method": "post", "action": "/source-llm-review"})
        ai_facts.require("form", {"data-pending-count": "0"}).require(
            "input",
            {"name": "review_all", "value": "1"},
        )
        ai_facts.require("form", {"data-pending-count": "1"}).require(
            "input",
            {"name": "review_all", "value": "0"},
        )
        self.assertNotIn("No changes since the last review", ai_detail_html)
        self.assertNotIn('name="acknowledge_cost"', ai_detail_html)
        self.assertNotIn("OpenRouter cost", ai_detail_html)
        self.assertIn("LLM Review", ai_facts.normalized_text())
        self.assertIn("LLM Review All", ai_facts.normalized_text())
        ai_detail_page.require("div", {"id": "memex-busy-loader"})
        self.assertIn("Reviewing facts", ai_detail_html)
        fix_repair = fix_detail_page.by_testid("source-repair")
        fix_form = fix_repair.require("form", {"method": "post", "action": "/source-fix"})
        self.assertIn(f"Model {SOURCE_FIX_MODEL}", fix_form.normalized_text())
        self.assertIn("Fixing source", fix_detail_html)
        instruction = fix_form.require("textarea", {"name": "instruction"})
        self.assertIn("Change all dates to YYYY-MM-DD format", instruction.attrs["placeholder"])
        self.assertLess(fix_form.require("h3").order, instruction.order)
        fix_button = fix_form.require("button", {"type": "submit"})
        self.assertLess(instruction.order, fix_button.order)
        self.assertNotIn("Re-extract With Instructions", fix_detail_page.normalized_text())
        self.assertEqual(0, fix_detail_page.count("form", {"action": "/source-reextract"}))


if __name__ == "__main__":
    unittest.main()
