import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

from app.wiki.dashboard_server import create_dashboard_handler, create_dashboard_server
from app.wiki.vault import write_wiki_page
from tests.dashboard_server_helpers import DashboardServerTestCase
from tests.helpers import wiki_workspace
from tests.html_helpers import parse_html


class WikiDashboardServerTests(DashboardServerTestCase):
    def test_dashboard_server_suppresses_client_disconnect_tracebacks(self):
        handler_class = create_dashboard_handler(object())
        handler = handler_class.__new__(handler_class)
        handler.close_connection = False

        with patch.object(
            BaseHTTPRequestHandler,
            "handle_one_request",
            side_effect=BrokenPipeError,
        ):
            handler.handle_one_request()

        self.assertTrue(handler.close_connection)

    def test_dashboard_server_renders_built_wiki_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            wiki = workspace.add_wiki("career", "Career", "career.md")
            write_wiki_page(
                workspace.vault_root,
                wiki,
                "\n".join(
                    (
                        "# Career",
                        "",
                        "<!-- MEMEX:SYNTHESIS:START -->",
                        "## Wiki Brief",
                        "",
                        "Alice joined Example Co. [(S1:f1)](#memex-fact-s1-f1)",
                        "<!-- MEMEX:SYNTHESIS:END -->",
                        "",
                        "<!-- MEMEX:FACTS:START -->",
                        "## Accepted Facts",
                        "",
                        '- <a id="memex-fact-s1-f1"></a> '
                        "Alice joined Example Co. **Safely** `fact-1`",
                        "- <script>alert('x')</script>",
                    )
                ),
            )

            with self.serving(create_dashboard_server(workspace, port=0)) as (host, port):
                dashboard = self.request(host, port, "GET", "/")[2]
                dashboard_page = parse_html(dashboard)
                dashboard_page.require("a", {"href": "/wiki/career"})
                self.assertIn(
                    str(root / "vault" / "career.md"),
                    dashboard_page.normalized_text(),
                )

                status, _, body = self.request(host, port, "GET", "/wiki/career")
                page = parse_html(body)

                self.assertEqual(200, status)
                page.require("a", {"href": "/", "aria-label": "MEMEX — dashboard"})
                self.assertEqual("Wiki Detail", page.require("h1").normalized_text())
                self.assertIn("Career", [node.normalized_text() for node in page.find_all("h2")])
                h1_text = [node.normalized_text() for node in page.find_all("h1")]
                self.assertNotIn("Career", h1_text)
                self.assertIn("Accepted Facts", page.normalized_text())
                self.assertIn("Safely", page.normalized_text())
                self.assertIn("fact-1", page.normalized_text())
                page.require("a", {"href": "#memex-fact-s1-f1"})
                page.require("a", {"id": "memex-fact-s1-f1"})
                self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", body)
                self.assertNotIn("MEMEX:FACTS:START", body)

    def test_dashboard_server_returns_not_found_for_unknown_wiki_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = wiki_workspace(Path(temp_dir))

            with self.serving(create_dashboard_server(workspace, port=0)) as (host, port):
                status, _, body = self.request(host, port, "GET", "/wiki/missing")

                self.assertEqual(404, status)
                self.assertEqual("not found", body)
