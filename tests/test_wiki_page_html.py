import unittest

from app.wiki.wiki_page_html import _render_markdown


class WikiPageHtmlTests(unittest.TestCase):
    def test_markdown_links_render_safe_internal_relative_paths(self):
        html = _render_markdown(
            "[Facts](career/facts) [Relative](foo/bar) "
            "[Source](/source/source-1) [External](https://example.com)"
        )

        self.assertIn('<a href="career/facts">Facts</a>', html)
        self.assertIn('<a href="foo/bar">Relative</a>', html)
        self.assertIn('<a href="/source/source-1">Source</a>', html)
        self.assertIn("[External](https://example.com)", html)

    def test_markdown_links_reject_relative_traversal(self):
        html = _render_markdown("[Escape](../secret)")

        self.assertIn("[Escape](../secret)", html)


if __name__ == "__main__":
    unittest.main()
