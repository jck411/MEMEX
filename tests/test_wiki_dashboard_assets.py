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

    def test_header_back_link_style_is_owned_by_base_css(self):
        self.assertEqual(1, DASHBOARD_CSS.count(".back-link {"))
        self.assertEqual(1, DASHBOARD_CSS.count(".button-icon-svg {"))
        self.assertIn(".back-link + .wordmark {", DASHBOARD_CSS)
        back_link_block = DASHBOARD_CSS[
            DASHBOARD_CSS.index(".back-link {") : DASHBOARD_CSS.index(".back-link:hover")
        ]
        self.assertIn("color: var(--accent);", back_link_block)
        self.assertIn(".back-link:hover, .back-link:focus-visible {", DASHBOARD_CSS)
        self.assertIn("min-height: 32px;", DASHBOARD_CSS)
        self.assertIn("line-height: 1;", DASHBOARD_CSS)
        self.assertLess(
            DASHBOARD_CSS.index(".button-icon-svg {"),
            DASHBOARD_CSS.index(".back-icon-svg {"),
        )

    def test_editor_action_buttons_have_extra_horizontal_spacing(self):
        self.assertIn("row-gap: 8px;", DASHBOARD_CSS)
        self.assertIn("column-gap: 14px;", DASHBOARD_CSS)
        self.assertLess(
            DASHBOARD_CSS.index("row-gap: 8px;"),
            DASHBOARD_CSS.index("column-gap: 14px;"),
        )


if __name__ == "__main__":
    unittest.main()
