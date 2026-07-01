import unittest

from app.wiki.dashboard_styles import CSS_ASSET_NAMES, DASHBOARD_CSS, load_dashboard_css


class WikiDashboardAssetTests(unittest.TestCase):
    def test_dashboard_css_loads_named_assets(self):
        self.assertEqual(
            (
                "base.css",
                "ingest.css",
                "home.css",
                "source-detail.css",
                "responsive.css",
                "wiki-page.css",
            ),
            CSS_ASSET_NAMES,
        )
        self.assertEqual(DASHBOARD_CSS, load_dashboard_css())
        for marker in (
            ":root",
            ".ingest-heading",
            ".wiki-create",
            ".detail-heading",
            "@media (max-width: 760px)",
            ".wiki-document",
        ):
            self.assertIn(marker, DASHBOARD_CSS)

    def test_ingest_buttons_size_to_content_until_mobile(self):
        self.assertIn(".extract-form .button { justify-self: start; }", DASHBOARD_CSS)
        self.assertIn(".extract-form .button { width: 100%; }", DASHBOARD_CSS)
        self.assertLess(
            DASHBOARD_CSS.index(".extract-form .button { justify-self: start; }"),
            DASHBOARD_CSS.index("@media (max-width: 760px)"),
        )

    def test_header_brand_alignment_uses_shared_icon_geometry(self):
        self.assertEqual(1, DASHBOARD_CSS.count(".back-link {"))
        self.assertEqual(1, DASHBOARD_CSS.count(".button-icon-svg {"))
        self.assertNotIn(".back-link + .wordmark {", DASHBOARD_CSS)
        self.assertNotIn(".back-icon-svg {", DASHBOARD_CSS)
        topbar_block = DASHBOARD_CSS[
            DASHBOARD_CSS.index(".topbar {") : DASHBOARD_CSS.index(".topbar-side")
        ]
        self.assertIn("align-items: flex-start;", topbar_block)
        brand_block = DASHBOARD_CSS[
            DASHBOARD_CSS.index(".topbar-brand {") : DASHBOARD_CSS.index(".wordmark")
        ]
        self.assertIn("display: inline-flex;", brand_block)
        self.assertIn("gap: 4px;", brand_block)
        back_link_block = DASHBOARD_CSS[
            DASHBOARD_CSS.index(".back-link {") : DASHBOARD_CSS.index(".back-link:hover")
        ]
        self.assertIn("color: var(--accent);", back_link_block)
        self.assertIn(".back-link:hover, .back-link:focus-visible {", DASHBOARD_CSS)
        self.assertIn("min-height: 32px;", DASHBOARD_CSS)
        self.assertIn("line-height: 1;", DASHBOARD_CSS)

    def test_editor_action_buttons_have_extra_horizontal_spacing(self):
        self.assertIn("row-gap: 8px;", DASHBOARD_CSS)
        self.assertIn("column-gap: 14px;", DASHBOARD_CSS)
        self.assertLess(
            DASHBOARD_CSS.index("row-gap: 8px;"),
            DASHBOARD_CSS.index("column-gap: 14px;"),
        )


if __name__ == "__main__":
    unittest.main()
