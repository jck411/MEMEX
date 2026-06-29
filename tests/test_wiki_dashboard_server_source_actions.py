import tempfile
from pathlib import Path

from app.wiki.dashboard_server import create_dashboard_server
from app.wiki.openrouter_review import OPENROUTER_REVIEW_MODEL
from app.wiki.review import ReviewResult
from app.wiki.source_fix import FactDiff, SourceFixResult
from app.wiki.workflows import ReviewWorkflowResult
from tests.dashboard_server_helpers import DashboardServerTestCase
from tests.helpers import fact_record, profile_source_record, source_record, wiki_workspace
from tests.html_helpers import parse_html


class WikiDashboardServerSourceActionTests(DashboardServerTestCase):
    def test_dashboard_server_repairs_source_and_fixes_with_instructions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("home", "Home", "home.md")
            source = source_record(
                "source-1",
                fact_record("fact-1", "The order requests ricer rock.", "sig-old"),
                title="Ricer rock",
                extraction_issues=("Ricer rock is likely a typo.",),
            )
            workspace.save_source(source)
            workspace.assign_source("home", "source-1")
            workspace.set_fact_decision("home", "source-1", "fact-1", False)

            from app.wiki.source_repair import repair_source_record

            def fix_source(source_id, instruction):
                self.assertEqual("source-1", source_id)
                self.assertEqual("fix ricer rock", instruction)
                current = workspace.data_store.load_source(source_id)
                fixed = repair_source_record(
                    current,
                    title="River rock",
                    summary=current.summary,
                    document_date=current.document_date,
                    source_type=current.source_type,
                    fact_texts={"fact-1": "The order requests river rock."},
                )
                return SourceFixResult(
                    source=fixed,
                    fact_diffs=(
                        FactDiff(
                            "fact-1",
                            "The order requests ricer rock.",
                            "The order requests river rock.",
                        ),
                    ),
                    metadata_diffs=(),
                    usage={},
                )

            server = create_dashboard_server(
                workspace,
                port=0,
                source_fixer=fix_source,
            )
            with self.serving(server) as (host, port):
                body = self.request(host, port, "GET", "/source/source-1")[2]
                page = parse_html(body)
                page.require("form", {"method": "post", "action": "/source-repair"})
                page.require("form", {"method": "post", "action": "/source-fix"})

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/source-fix",
                    {
                        "source_id": "source-1",
                        "instruction": "fix ricer rock",
                    },
                )
                self.assertEqual(303, status)
                self.assertIn("/source/source-1", location)
                self.assertIn("fixed+source+source-1", location)
                stored = workspace.data_store.load_source("source-1")
                self.assertEqual("River rock", stored.title)
                self.assertEqual(
                    ("The order requests river rock.",),
                    tuple(fact.text for fact in stored.facts),
                )
                self.assertTrue(workspace.status("home").needs_review)

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/source-repair",
                    {
                        "source_id": "source-1",
                        "title": "River rock manual",
                        "summary": "",
                        "document_date": "",
                        "source_type": "",
                        "fact_id": ["fact-1"],
                        "fact_text": [
                            "The order requests river rock manually.",
                        ],
                        "new_fact_text": "",
                    },
                )
                self.assertEqual(303, status)
                self.assertIn("/source/source-1", location)
                stored = workspace.data_store.load_source("source-1")
                self.assertEqual("River rock manual", stored.title)
                self.assertEqual((), stored.extraction_issues)
                self.assertEqual(
                    ("The order requests river rock manually.",),
                    tuple(fact.text for fact in stored.facts),
                )
                self.assertTrue(workspace.status("home").needs_review)

    def test_dashboard_server_runs_llm_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki(
                "career",
                "Career",
                "career.md",
                description="Track durable employment history.",
            )
            workspace.save_source(profile_source_record())
            workspace.assign_source("career", "source-1")
            seen = []

            def review_source(wiki_id, source_id, review_all):
                seen.append(
                    {
                        "wiki_id": wiki_id,
                        "source_id": source_id,
                        "review_all": review_all,
                    }
                )
                result = workspace.review_source(
                    wiki_id,
                    source_id,
                    [
                        ReviewResult("fact-1", True, "Employment history."),
                        ReviewResult("fact-2", False, "Residence is out of scope."),
                    ],
                )
                return ReviewWorkflowResult(
                    applied_count=result.applied_count,
                    remaining_review_count=result.remaining_review_count,
                    status=result.status,
                    provider="openrouter",
                    model=OPENROUTER_REVIEW_MODEL,
                    usage={"cost": 0.00042},
                )

            server = create_dashboard_server(
                workspace,
                port=0,
                source_reviewer=review_source,
            )
            with self.serving(server) as (host, port):
                body = self.request(host, port, "GET", "/source/source-1")[2]
                page = parse_html(body)
                page.require("form", {"action": "/source-llm-review"}).require(
                    "input",
                    {"name": "review_all", "value": "0"},
                )
                self.assertEqual(0, page.count(attrs={"name": "acknowledge_cost"}))
                self.assertIn("LLM Review", page.normalized_text())

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/source-llm-review",
                    {
                        "source_id": "source-1",
                        "wiki_id": "career",
                    },
                )
                self.assertEqual(303, status)
                self.assertIn("/source/source-1", location)
                self.assertIn("LLM+reviewed+2+fact", location)
                self.assertEqual(
                    [{"wiki_id": "career", "source_id": "source-1", "review_all": False}],
                    seen,
                )
                self.assertFalse(workspace.status("career").needs_review)

                reviewed = self.request(host, port, "GET", "/source/source-1")[2]
                page = parse_html(reviewed)
                page.require("form", {"action": "/source-llm-review"})
                page.require("form", {"data-pending-count": "0"}).require(
                    "input",
                    {"name": "review_all", "value": "1"},
                )
                self.assertIn("LLM Review All", page.normalized_text())
                self.assertIn("Accepted", page.normalized_text())
                self.assertIn("Rejected", page.normalized_text())
                self.assertIn(
                    "Residence is out of scope.",
                    workspace.data_store.load_ledger()
                    .decision_for("career", "source-1", "fact-2")
                    .reason,
                )

                status, location, _ = self.request(
                    host,
                    port,
                    "POST",
                    "/source-llm-review",
                    {
                        "source_id": "source-1",
                        "wiki_id": "career",
                        "review_all": "1",
                    },
                )
                self.assertEqual(303, status)
                self.assertIn("LLM+reviewed+all+2+fact", location)
                self.assertEqual(
                    [
                        {"wiki_id": "career", "source_id": "source-1", "review_all": False},
                        {"wiki_id": "career", "source_id": "source-1", "review_all": True},
                    ],
                    seen,
                )
