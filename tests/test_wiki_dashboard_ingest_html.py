import unittest

from app.wiki.dashboard import dashboard_snapshot
from app.wiki.dashboard_html import DashboardRenderOptions, render_dashboard_html
from app.wiki.dashboard_ingest_hints import DuplicateSourceHint
from app.wiki.ledger import WikiLedger
from app.wiki.model_profiles import (
    DEFAULT_EXTRACTION_PROFILE_ID,
    GOOGLE_GEMINI35_FLASH_EXTRACTION,
    OPENAI_GPT55_EXTRACTION,
)
from tests.helpers import wiki_record, wiki_registry
from tests.html_helpers import parse_html


class WikiDashboardIngestHtmlTests(unittest.TestCase):
    def test_render_dashboard_html_includes_extraction_form_when_enabled(self):
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))

        html = render_dashboard_html(
            dashboard_snapshot(registry, WikiLedger.empty(), []),
            DashboardRenderOptions(
                extraction_enabled=True,
                extraction_model_spec=DEFAULT_EXTRACTION_PROFILE_ID,
            ),
        )
        page = parse_html(html)
        ingest = page.by_testid("ingest-section")
        upload_form = ingest.require(
            "form",
            {
                "method": "post",
                "action": "/upload",
                "enctype": "multipart/form-data",
            },
        )
        text_form = ingest.require("form", {"method": "post", "action": "/text-source"})

        upload_form.require("input", {"type": "file", "name": "source_file"})
        text_form.require("input", {"name": "text_title"})
        text_form.require("textarea", {"name": "source_text"})
        self.assertIn("Add Text", text_form.normalized_text())
        self.assertEqual(0, page.count("form", {"action": "/extract"}))
        self.assertNotIn("Local Path", html)
        self.assertEqual(0, ingest.count(attrs={"placeholder": "Source id (optional)"}))
        self.assertEqual(0, ingest.count(attrs={"name": "source_id"}))
        self.assertEqual(0, ingest.count(attrs={"name": "source_type"}))
        self.assertEqual(0, ingest.count(attrs={"name": "assign_wiki_id"}))
        self.assertEqual(
            1,
            ingest.count("select", {"id": "source-model-select", "name": "model_spec"}),
        )
        self.assertEqual(
            2,
            ingest.count("input", {"type": "hidden", "name": "model_spec"}),
        )
        self.assertIn("memexSyncModelSpec(form)", html)
        self.assertEqual(2, ingest.count("input", {"name": "allow_duplicate", "value": ""}))
        dialog = ingest.require("dialog", {"id": "duplicate-upload-dialog"})
        self.assertIn("Duplicate source", dialog.normalized_text())
        self.assertIn("Cancel", dialog.normalized_text())
        self.assertIn("Keep Duplicate", dialog.normalized_text())
        self.assertIn("MEMEX_DUPLICATE_SOURCES = {}", html)
        busy = page.require("div", {"id": "memex-busy-loader", "hidden": True})
        self.assertIn("Working", busy.normalized_text())
        self.assertIn("Uploading source", html)
        self.assertEqual(
            DEFAULT_EXTRACTION_PROFILE_ID,
            ingest.require("option", {"selected": True}).attrs["value"],
        )
        ingest.require("option", {"value": OPENAI_GPT55_EXTRACTION.profile_id})
        self.assertIn("OpenAI gpt-5.5", html)
        ingest.require("option", {"value": GOOGLE_GEMINI35_FLASH_EXTRACTION.profile_id})
        self.assertIn("Google gemini-3.5-flash", html)
        self.assertNotIn("(not wired)", html)

    def test_render_dashboard_html_includes_duplicate_detection_payload(self):
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))

        html = render_dashboard_html(
            dashboard_snapshot(registry, WikiLedger.empty(), []),
            DashboardRenderOptions(
                extraction_enabled=True,
                extraction_model_spec=DEFAULT_EXTRACTION_PROFILE_ID,
                duplicate_sources=(
                    DuplicateSourceHint(
                        "a" * 64,
                        "source-existing",
                        "Existing Source",
                    ),
                ),
            ),
        )

        self.assertIn("MEMEX_DUPLICATE_SOURCES", html)
        self.assertIn('"source_id": "source-existing"', html)
        self.assertIn('"title": "Existing Source"', html)


if __name__ == "__main__":
    unittest.main()
