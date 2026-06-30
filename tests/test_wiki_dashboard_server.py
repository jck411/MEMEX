import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

import app.wiki.dashboard_routes as dashboard_routes
from app.wiki.dashboard_server import (
    create_dashboard_handler,
    create_dashboard_server,
    run_dashboard_server,
)
from app.wiki.dashboard_runtime import DashboardRuntime
from app.wiki.dashboard_routes import handle_dashboard_get
from app.wiki.markdown import build_wiki_markdown
from app.wiki.review import ReviewResult
from app.wiki.vault import write_wiki_page
from tests.dashboard_server_helpers import DashboardServerTestCase
from tests.helpers import fact_record, source_record, wiki_workspace
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

    def test_run_dashboard_server_rejects_alternate_port(self):
        with self.assertRaisesRegex(ValueError, "canonical port 8765"):
            run_dashboard_server(object(), port=9999)

    def test_dashboard_get_routes_reuse_one_read_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = wiki_workspace(Path(temp_dir))
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(
                source_record(
                    "source-1",
                    fact_record("fact-1", "Alice joined Example Co."),
                )
            )
            workspace.assign_source("career", "source-1")
            runtime = DashboardRuntime(workspace)
            original_snapshot = dashboard_routes.workspace_read_snapshot

            def counting_snapshot(workspace_arg):
                calls.append(workspace_arg)
                return original_snapshot(workspace_arg)

            for target in ("/", "/source/source-1", "/wiki/career", "/wiki/career/facts"):
                with self.subTest(target=target):
                    calls = []
                    with patch(
                        "app.wiki.dashboard_routes.workspace_read_snapshot",
                        side_effect=counting_snapshot,
                    ):
                        response = handle_dashboard_get(runtime, target)

                    self.assertEqual(200, response.status)
                    self.assertEqual([workspace], calls)

    def test_dashboard_server_renders_built_wiki_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            wiki = workspace.add_wiki("career", "Career", "career.md")
            write_wiki_page(
                workspace.vault_root,
                wiki,
                build_wiki_markdown(
                    wiki,
                    "\n".join(
                        (
                            "## Wiki Brief",
                            "",
                            "Alice joined Example Co. **Safely**",
                            "",
                            "- <script>alert('x')</script>",
                        )
                    ),
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
                page.require("a", {"href": "/wiki/career/facts"})
                page.require("a", {"href": "career/facts"})
                h1_text = [node.normalized_text() for node in page.find_all("h1")]
                self.assertNotIn("Career", h1_text)
                self.assertNotIn("Source Fact Decisions", page.normalized_text())
                page.require("ul")
                self.assertIn("Safely", page.normalized_text())
                self.assertNotIn("fact-1", page.normalized_text())
                self.assertNotIn("/source/source-1", body)
                self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", body)
                self.assertNotIn("MEMEX:FACTS:START", body)

    def test_dashboard_server_renders_wiki_facts_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = wiki_workspace(Path(temp_dir))
            workspace.add_wiki("career", "Career", "career.md")
            source = source_record(
                "source-1",
                fact_record("fact-1", "Alice joined Example Co."),
                fact_record("fact-2", "Alice lives in Boston."),
                title="Source One",
            )
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [
                    ReviewResult("fact-1", True, "Career history."),
                    ReviewResult("fact-2", False, "Out of scope."),
                ],
            )

            with self.serving(create_dashboard_server(workspace, port=0)) as (host, port):
                dashboard = self.request(host, port, "GET", "/")[2]
                dashboard_page = parse_html(dashboard)
                dashboard_page.require("a", {"href": "/wiki/career/facts"})

                status, _, body = self.request(host, port, "GET", "/wiki/career/facts")
                page = parse_html(body)

                self.assertEqual(200, status)
                self.assertEqual("Wiki Facts", page.require("h1").normalized_text())
                page.require("a", {"href": "/wiki/career"})
                page.require("a", {"href": "/source/source-1"})
                accepted = page.by_testid("wiki-accepted-facts").normalized_text()
                not_used = page.by_testid("wiki-not-used-facts").normalized_text()
                self.assertIn("Alice joined Example Co.", accepted)
                self.assertIn("Career history.", accepted)
                self.assertIn("Alice lives in Boston.", not_used)
                self.assertIn("Out of scope.", not_used)
                self.assertNotIn("MEMEX:FACTS:START", body)
                self.assertNotIn("Source Fact Decisions", body)

    def test_dashboard_server_returns_not_found_for_unknown_wiki_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = wiki_workspace(Path(temp_dir))

            with self.serving(create_dashboard_server(workspace, port=0)) as (host, port):
                status, _, body = self.request(host, port, "GET", "/wiki/missing")

                self.assertEqual(404, status)
                self.assertEqual("not found", body)
