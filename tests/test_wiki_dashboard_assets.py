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

    def test_mobile_header_card_rows_fit_inside_viewport(self):
        mobile_css = DASHBOARD_CSS[DASHBOARD_CSS.index("@media (max-width: 760px)") :]
        self.assertIn(
            ".topbar-side { justify-items: stretch; margin-top: 10px; max-width: 100%; }",
            mobile_css,
        )
        self.assertIn(".balances {", mobile_css)
        self.assertIn("min-width: 0;", mobile_css)
        self.assertIn(
            ".balance-chip { min-width: 88px; flex: 1 1 0; padding: 7px 10px; }",
            mobile_css,
        )
        self.assertIn(
            ".balance-chip span, .balance-chip strong { overflow-wrap: anywhere; }",
            mobile_css,
        )

    def test_rows_use_fluid_tracks_instead_of_intrinsic_action_columns(self):
        row_block = DASHBOARD_CSS[
            DASHBOARD_CSS.index(".wiki-row, .source-row {") : DASHBOARD_CSS.index(
                ".wiki-row:hover"
            )
        ]
        self.assertIn(
            "grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));",
            row_block,
        )
        self.assertNotIn("grid-template-columns: minmax(0, 1fr) auto;", row_block)
        self.assertIn(".source-actions {", DASHBOARD_CSS)
        self.assertIn(".source-actions form { min-width: 0; max-width: 100%; }", DASHBOARD_CSS)
        self.assertIn(".bubble-label { min-width: 0; overflow-wrap: anywhere; }", DASHBOARD_CSS)

    def test_filters_wrap_without_horizontal_scrolling(self):
        start = DASHBOARD_CSS.index(".filter-controls {")
        filter_block = DASHBOARD_CSS[start : DASHBOARD_CSS.index(".filters label", start)]
        self.assertIn("flex-wrap: wrap;", filter_block)
        self.assertNotIn("overflow-x", filter_block)

    def test_editor_action_buttons_have_extra_horizontal_spacing(self):
        self.assertIn("row-gap: 8px;", DASHBOARD_CSS)
        self.assertIn("column-gap: 14px;", DASHBOARD_CSS)
        self.assertLess(
            DASHBOARD_CSS.index("row-gap: 8px;"),
            DASHBOARD_CSS.index("column-gap: 14px;"),
        )


if __name__ == "__main__":
    unittest.main()
