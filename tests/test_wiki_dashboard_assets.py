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


if __name__ == "__main__":
    unittest.main()
