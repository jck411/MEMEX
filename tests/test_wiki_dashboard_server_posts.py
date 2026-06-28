import tempfile
from decimal import Decimal
from pathlib import Path

from app.wiki.dashboard_server import create_dashboard_server
from app.wiki.provider_balances import OPENROUTER_LOGS_URL, ProviderBalance
from app.wiki.review import ReviewResult
from app.wiki.wiki_scope import wiki_intention_text
from tests.dashboard_server_helpers import DashboardServerTestCase
from tests.helpers import fact_record, fixture_wiki_build_provider, source_record, wiki_workspace
from tests.html_helpers import parse_html


class WikiDashboardServerPostTests(DashboardServerTestCase):
    def test_dashboard_server_renders_and_toggles_assignments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.add_wiki("tax", "Tax", "tax.md")
            workspace.save_source(
                source_record(
                    "source-1",
                    fact_record("fact-1", "Alice joined Example Co."),
                )
            )

            server = create_dashboard_server(
                workspace,
                port=0,
                balance_provider=lambda: (
                    ProviderBalance(
                        "openrouter",
                        "available",
                        "$9.0000",
                        amount=Decimal("9"),
                        unit="usd",
                        url=OPENROUTER_LOGS_URL,
                    ),
                ),
            )
            with self.serving(server) as (host, port):
                body = self.request(host, port, "GET", "/")[2]
                page = parse_html(body)
                self.assertIn("Wiki Dashboard", page.normalized_text())
                self.assertIn("OpenRouter", page.normalized_text())
                self.assertIn("$9.0000", page.normalized_text())
                page.require("a", {"href": OPENROUTER_LOGS_URL})
                page.require("a", {"href": "/source/source-1"})
                page.require("input", {"name": "operation", "value": "assign"})

                status, _, body = self.request(host, port, "GET", "/source/source-1")
                page = parse_html(body)
                self.assertEqual(200, status)
                self.assertIn("Profile", page.normalized_text())
                self.assertIn("Alice joined Example Co.", page.normalized_text())
                self.assertIn("No assigned wikis.", page.normalized_text())

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/assign",
                    {
                        "source_id": "source-1",
                        "wiki_id": "career",
                        "operation": "assign",
                    },
                )
                self.assertEqual(303, status)
                self.assertEqual("/", location)
                self.assertTrue(workspace.status("career").needs_review)
                workspace.assign_source("tax", "source-1")

                body = self.request(host, port, "GET", "/source/source-1")[2]
                page = parse_html(body)
                career_button = page.require("button", {"aria-label": "Remove Career"})
                self.assertIn("Needs review", career_button.attrs["title"])
                page.require("input", {"name": "wiki_id", "value": "career"})
                page.require("input", {"name": "wiki_id", "value": "tax"})
                self.assertIn("fact-1", page.normalized_text())
                page.require("form", {"action": "/source-decisions"})
                page.require("input", {"name": "accepted_decision"})
                self.assertIn("Save Decisions", page.normalized_text())

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/source-decisions",
                    {
                        "source_id": "source-1",
                        "changed_decision": ['["fact-1","career"]', '["fact-1","tax"]'],
                        "accepted_decision": ['["fact-1","career"]'],
                        "reason": "Manual dashboard decision.",
                        "return_to": "/source/source-1",
                    },
                )
                self.assertEqual(303, status)
                self.assertEqual("/source/source-1", location)
                status = workspace.status("career")
                self.assertFalse(status.needs_review)
                self.assertTrue(status.needs_build)
                self.assertTrue(workspace.status("tax").current)

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/delete-source",
                    {"source_id": "source-1"},
                )
                self.assertEqual(303, status)
                self.assertIn("deleted+source+source-1", location)
                self.assertEqual((), workspace.dashboard().sources)
                self.assertEqual((), workspace.data_store.load_ledger().assigned_sources("career"))

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/assign",
                    {
                        "source_id": "source-1",
                        "wiki_id": "career",
                        "operation": "unassign",
                        "return_to": "/source/source-1",
                    },
                )
                self.assertEqual(303, status)
                self.assertEqual("/source/source-1", location)

                body = self.request(host, port, "GET", "/?needs_review=1")[2]
                self.assertIn("No matching sources.", parse_html(body).normalized_text())

    def test_dashboard_server_adds_wiki_with_description_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = wiki_workspace(Path(temp_dir))

            with self.serving(create_dashboard_server(workspace, port=0)) as (host, port):
                body = self.request(host, port, "GET", "/")[2]
                parse_html(body).require("form", {"method": "post", "action": "/add-wiki"})

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/add-wiki",
                    {
                        "title": "Research Notes",
                        "description": "Track durable research notes.",
                    },
                )

                self.assertEqual(303, status)
                self.assertIn("added+wiki+research-notes", location)
                wiki = workspace.data_store.load_registry().wikis["research-notes"]
                self.assertEqual("Research Notes", wiki.title)
                self.assertEqual("research-notes.md", wiki.path)
                self.assertEqual("Track durable research notes.", wiki.description)
                self.assertEqual("Track durable research notes.", wiki_intention_text(wiki))

                body = self.request(host, port, "GET", "/")[2]
                page_text = parse_html(body).normalized_text()
                self.assertIn("Research Notes", page_text)
                self.assertIn("research-notes.md", page_text)
                self.assertIn("Track durable research notes.", page_text)

    def test_dashboard_server_deletes_wiki_without_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("scratch", "Scratch", "scratch.md")
            wiki_path = root / "vault" / "scratch.md"
            wiki_path.parent.mkdir(parents=True)
            wiki_path.write_text("# Scratch", encoding="utf-8")

            with self.serving(create_dashboard_server(workspace, port=0)) as (host, port):
                body = self.request(host, port, "GET", "/")[2]
                parse_html(body).require(
                    "form",
                    {"method": "post", "action": "/delete-wiki"},
                )
                self.assertNotIn("confirm('Delete this wiki?')", body)

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/delete-wiki",
                    {"wiki_id": "scratch"},
                )

                self.assertEqual(303, status)
                self.assertIn("deleted+wiki+scratch", location)
                self.assertEqual((), workspace.dashboard().wikis)
                self.assertFalse(wiki_path.exists())

    def test_dashboard_server_updates_wiki_description_and_invalidates_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki(
                "career",
                "Career",
                "career.md",
                description="Track employment history.",
            )
            workspace.save_source(
                source_record(
                    "source-1",
                    fact_record("fact-1", "Alice joined Example Co."),
                )
            )
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-1", True, "Employment history.")],
            )
            workspace.build_wiki("career", fixture_wiki_build_provider())

            with self.serving(create_dashboard_server(workspace, port=0)) as (host, port):
                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/wiki-description",
                    {
                        "wiki_id": "career",
                        "description": "Track public speaking history.",
                    },
                )

                self.assertEqual(303, status)
                self.assertIn("updated+wiki+description+for+career", location)
                wiki = workspace.data_store.load_registry().wikis["career"]
                self.assertEqual("Track public speaking history.", wiki.description)
                wiki_status = workspace.status("career")
                self.assertTrue(wiki_status.needs_review)
                self.assertTrue(wiki_status.needs_build)
                body = self.request(host, port, "GET", "/")[2]
                self.assertIn("Track public speaking history.", body)
                self.assertIn("needs_review+build", body)

    def test_dashboard_server_build_verifies_markdown_before_success_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(
                source_record(
                    "source-1",
                    fact_record("fact-1", "Alice joined Example Co."),
                )
            )
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-1", True, "Career history.")],
            )

            with self.serving(
                create_dashboard_server(
                    workspace,
                    port=0,
                    wiki_builder=lambda wiki_id: None,
                )
            ) as (host, port):
                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/build",
                    {"wiki_id": "career"},
                )

                self.assertEqual(303, status)
                self.assertIn("message_type=error", location)
                self.assertIn("did+not+write+markdown", location)
                self.assertNotIn("built+career", location)
                self.assertFalse((root / "vault" / "career.md").exists())
                self.assertTrue(workspace.status("career").needs_build)
                body = self.request(host, port, "GET", location)[2]
                toast = parse_html(body).require("div", {"id": "toast"})
                self.assertEqual("toast toast-error", toast.attrs["class"])

    def test_dashboard_server_build_success_writes_readable_wiki_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(
                source_record(
                    "source-1",
                    fact_record("fact-1", "Alice joined Example Co."),
                )
            )
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-1", True, "Career history.")],
            )

            with self.serving(
                create_dashboard_server(
                    workspace,
                    port=0,
                    wiki_builder=lambda wiki_id: workspace.build_wiki(
                        wiki_id,
                        fixture_wiki_build_provider(),
                    ),
                )
            ) as (host, port):
                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/build",
                    {"wiki_id": "career"},
                )
                _, _, body = self.request(host, port, "GET", "/wiki/career")

                self.assertEqual(303, status)
                self.assertIn("successfully+built+career", location)
                self.assertIn("message_type=success", location)
                self.assertFalse(workspace.status("career").needs_build)
                self.assertIn(
                    "Alice joined Example Co.",
                    parse_html(body).normalized_text(),
                )
                body = self.request(host, port, "GET", location)[2]
                toast = parse_html(body).require("div", {"id": "toast"})
                self.assertEqual("toast toast-success", toast.attrs["class"])
