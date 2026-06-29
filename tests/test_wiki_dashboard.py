import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.wiki.dashboard import (
    SourceDashboardFilter,
    dashboard_snapshot,
    filter_sources,
)
from app.wiki.dashboard_forms import DashboardForm
from app.wiki.dashboard_review_actions import apply_source_decisions
from app.wiki.ledger import WikiLedger
from app.wiki.review import ReviewResult, apply_review_results
from app.wiki.source_detail import source_detail_view
from app.wiki.status import mark_build_current
from app.wiki.wiki_facts import wiki_facts_view
from app.wiki.workflows import WikiWorkspace
from tests.helpers import fact_record, source_record, wiki_record, wiki_registry, wiki_workspace


class WikiDashboardTests(unittest.TestCase):
    def test_dashboard_modules_use_queries_not_workspace_storage_internals(self):
        repo_root = Path(__file__).resolve().parents[1]
        offenders: list[str] = []
        for path in sorted((repo_root / "app" / "wiki").glob("dashboard*.py")):
            text = path.read_text(encoding="utf-8")
            for token in ("workspace.data_store", "workspace.vault_root"):
                if token in text:
                    offenders.append(f"{path.relative_to(repo_root)} uses {token}")

        self.assertEqual([], offenders)

    def test_dashboard_composes_wiki_status_and_source_assignment_bubbles(self):
        career_fact = fact_record("fact-1", "Alice joined Example Co.")
        source = source_record("source-1", career_fact)
        noisy = source_record(
            "source-2",
            title="Noisy Import",
            extraction_issues=("No fact-like text extracted.",),
        )
        registry = wiki_registry(
            wiki_record("career", "Career", "career.md"),
            wiki_record("life", "Life", "life.md"),
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")

        snapshot = dashboard_snapshot(registry, ledger, [source, noisy])

        self.assertEqual(("career", "life"), tuple(row.wiki_id for row in snapshot.wikis))
        self.assertEqual("needs_review", snapshot.wikis[0].state)
        self.assertEqual(1, snapshot.wikis[0].assigned_source_count)
        self.assertEqual(1, snapshot.wikis[0].review_delta_count)
        self.assertEqual("current", snapshot.wikis[1].state)

        first_source = snapshot.sources[0]
        self.assertEqual(("career",), first_source.assigned_wiki_ids)
        self.assertEqual(("career",), first_source.needs_review_wiki_ids)
        self.assertEqual(
            (("career", True, "needs_review"), ("life", False, "current")),
            tuple(
                (bubble.wiki_id, bubble.assigned, bubble.state)
                for bubble in first_source.wiki_bubbles
            ),
        )
        self.assertTrue(snapshot.sources[1].unassigned)
        self.assertEqual(1, snapshot.sources[1].extraction_issue_count)

    def test_workspace_dashboard_orders_sources_newest_first_from_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(source_record("no-asset", title="No Asset"))
            self._save_source_asset(
                workspace,
                root,
                "older",
                "Older",
                "2026-06-23T10:00:00Z",
            )
            self._save_source_asset(
                workspace,
                root,
                "newer",
                "Newer",
                "2026-06-24T10:00:00Z",
            )

            snapshot = workspace.dashboard()

            self.assertEqual(
                ("newer", "older", "no-asset"),
                tuple(row.source_id for row in snapshot.sources),
            )

    def test_dashboard_source_filters_cover_daily_assignment_views(self):
        source = source_record("source-1", fact_record("fact-1", "Career fact."))
        noisy = source_record(
            "source-2",
            title="Noisy Import",
            extraction_issues=("No fact-like text extracted.",),
        )
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        snapshot = dashboard_snapshot(registry, ledger, [source, noisy])

        self.assertEqual(
            ("source-2",),
            tuple(
                row.source_id
                for row in filter_sources(
                    snapshot.sources,
                    SourceDashboardFilter(unassigned=True, has_issues=True),
                )
            ),
        )
        self.assertEqual(
            ("source-1",),
            tuple(
                row.source_id
                for row in filter_sources(
                    snapshot.sources,
                    SourceDashboardFilter(needs_review=True),
                )
            ),
        )
        self.assertEqual(
            ("source-1",),
            tuple(
                row.source_id
                for row in filter_sources(
                    snapshot.sources,
                    SourceDashboardFilter(search="profile"),
                )
            ),
        )

    def test_wiki_facts_view_separates_used_and_not_used_facts(self):
        accepted = fact_record("fact-1", "Alice joined Example Co.")
        rejected = fact_record("fact-2", "Alice lives in Boston.")
        pending = fact_record("fact-3", "Alice likes skiing.")
        source = source_record("source-1", accepted, rejected, pending, title="Profile")
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            registry.wikis["career"],
            "source-1",
            ledger,
            source,
            [
                ReviewResult("fact-1", True, "Career history."),
                ReviewResult("fact-2", False, "Out of scope."),
            ],
        )

        view = wiki_facts_view(registry, ledger, [source], "career")

        self.assertEqual(1, view.accepted_count)
        self.assertEqual(2, view.not_used_count)
        self.assertEqual(("fact-1",), tuple(fact.fact_id for fact in view.groups[0].accepted))
        self.assertEqual(
            (("fact-2", "rejected"), ("fact-3", "pending")),
            tuple((fact.fact_id, fact.state) for fact in view.groups[0].not_used),
        )

    def test_dashboard_marks_build_pending_wikis_on_assigned_sources(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        source = source_record("source-1", fact)
        registry = wiki_registry(wiki_record("career", "Career", "career.md"))
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            registry.wikis["career"],
            "source-1",
            ledger,
            source,
            [ReviewResult("fact-1", True, "Career fact.")],
        )

        snapshot = dashboard_snapshot(registry, ledger, [source])

        self.assertEqual("needs_build", snapshot.wikis[0].state)
        self.assertEqual(("career",), snapshot.sources[0].needs_build_wiki_ids)

    def test_dashboard_presents_review_before_build_for_stale_wikis(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        source = source_record("source-1", fact)
        old_wiki = wiki_record(
            "career",
            "Career",
            "career.md",
            description="Track employment history.",
        )
        registry = wiki_registry(
            wiki_record(
                "career",
                "Career",
                "career.md",
                description="Track public speaking history.",
            )
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            old_wiki,
            "source-1",
            ledger,
            source,
            [ReviewResult("fact-1", True, "Employment fact.")],
        )
        mark_build_current(old_wiki, ledger, [source])

        snapshot = dashboard_snapshot(registry, ledger, [source])

        self.assertEqual("needs_review", snapshot.wikis[0].state)
        self.assertEqual(("career",), snapshot.sources[0].needs_review_wiki_ids)
        self.assertEqual((), snapshot.sources[0].needs_build_wiki_ids)

    def test_source_detail_view_includes_evidence_issues_and_review_deltas(self):
        pending_fact = fact_record(
            "fact-1",
            "Alice joined Example Co. in 2024.",
            provenance={
                "evidence": [
                    {
                        "id": "ev-joined",
                        "quote": "Alice joined Example Co. in 2024.",
                        "source_channel": "pdf_text",
                        "page": 2,
                        "locator": "paragraph 4",
                    }
                ],
            },
        )
        reviewed_fact = fact_record("fact-2", "Alice lives in Boston.")
        source = source_record(
            "source-1",
            pending_fact,
            reviewed_fact,
            extraction_issues=("Review employment date.",),
        )
        registry = wiki_registry(
            wiki_record("career", "Career", "career.md"),
            wiki_record("life", "Life", "life.md"),
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        ledger.assign_source("life", "source-1")
        apply_review_results(
            registry.wikis["career"],
            "source-1",
            ledger,
            source,
            [ReviewResult("fact-2", False, "Out of scope.")],
        )
        apply_review_results(
            registry.wikis["life"],
            "source-1",
            ledger,
            source,
            [
                ReviewResult("fact-1", False, "Work history is out of scope."),
                ReviewResult("fact-2", True, "Residence belongs here."),
            ],
        )

        detail = source_detail_view(registry, ledger, [source], "source-1")

        self.assertEqual(("Review employment date.",), detail.extraction_issues)
        self.assertEqual("ev-joined", detail.facts[0].evidence[0].evidence_id)
        self.assertEqual("pdf_text", detail.facts[0].evidence[0].source_channel)
        self.assertEqual("pending", detail.facts[0].decisions[0].state)
        self.assertEqual("rejected", detail.facts[1].decisions[0].state)
        self.assertEqual("accepted", detail.facts[1].decisions[1].state)

    def test_workspace_and_cli_render_dashboard_snapshot(self):
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

            self.assertEqual("needs_review", workspace.dashboard().wikis[0].state)

            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_dev.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo-root",
                    str(root),
                    "dashboard",
                    "--needs-review",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            self.assertIn("career\tneeds_review", result.stdout)
            self.assertIn("[x career:needs_review]", result.stdout)

    def test_workspace_delete_source_removes_ledger_references(self):
        source = source_record(
            "source-1",
            fact_record("fact-1", "Alice joined Example Co."),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(source)
            original = root / "profile.txt"
            original.write_text("Alice joined Example Co.", encoding="utf-8")
            workspace.source_assets().stage_file(
                "source-1",
                original,
                source_kind="local_path",
            ).commit(
                extraction_provider="local",
                extraction_model="text-v1",
                extracted_at="2026-06-23T00:00:00Z",
            )
            workspace.assign_source("career", "source-1")
            workspace.set_fact_decision(
                "career",
                "source-1",
                "fact-1",
                True,
                reason="Manual dashboard decision.",
            )

            deleted = workspace.delete_source("source-1")
            ledger = workspace.data_store.load_ledger()

            self.assertEqual("source-1", deleted.source_id)
            self.assertEqual((), ledger.assigned_sources("career"))
            self.assertIsNone(ledger.decision_for("career", "source-1", "fact-1"))
            self.assertEqual((), workspace.dashboard().sources)
            self.assertFalse(workspace.source_assets().asset_dir("source-1").exists())

    def _save_source_asset(
        self,
        workspace: WikiWorkspace,
        root: Path,
        source_id: str,
        title: str,
        created_at: str,
    ) -> None:
        workspace.save_source(source_record(source_id, title=title))
        original = root / f"{source_id}.txt"
        original.write_text(title, encoding="utf-8")
        staged = workspace.source_assets().stage_file(
            source_id,
            original,
            source_kind="file",
            created_at=created_at,
        )
        staged.commit(
            extraction_provider="test",
            extraction_model="test",
            extracted_at=created_at,
        )

    def test_manual_source_decision_save_updates_only_changed_decisions(self):
        source = source_record(
            "source-1",
            fact_record("fact-1", "Alice joined Example Co."),
            fact_record("fact-2", "Alice mentors new hires."),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.add_wiki("tax", "Tax", "tax.md")
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")
            workspace.assign_source("tax", "source-1")
            workspace.set_fact_decision(
                "career",
                "source-1",
                "fact-1",
                True,
                reason="LLM accepted this career fact.",
            )
            workspace.set_fact_decision(
                "tax",
                "source-1",
                "fact-1",
                False,
                reason="LLM rejected this tax fact.",
            )

            apply_source_decisions(
                workspace,
                DashboardForm(
                    fields={
                        "source_id": ("source-1",),
                        "accepted_decision": (
                            '["fact-1","career"]',
                            '["fact-2","career"]',
                        ),
                        "changed_decision": ('["fact-2","career"]',),
                        "reason": ("Manual dashboard decision.",),
                    },
                    files={},
                ),
            )

            ledger = workspace.data_store.load_ledger()
            self.assertEqual(
                "LLM accepted this career fact.",
                ledger.decision_for("career", "source-1", "fact-1").reason,
            )
            self.assertEqual(
                "LLM rejected this tax fact.",
                ledger.decision_for("tax", "source-1", "fact-1").reason,
            )
            self.assertEqual(
                "Manual dashboard decision.",
                ledger.decision_for("career", "source-1", "fact-2").reason,
            )
            self.assertIsNone(ledger.decision_for("tax", "source-1", "fact-2"))

    def test_manual_source_decision_save_can_complete_wiki_review(self):
        source = source_record(
            "source-1",
            fact_record("fact-1", "Alice joined Example Co."),
            fact_record("fact-2", "Alice mentors new hires."),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = wiki_workspace(Path(temp_dir))
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")

            self.assertTrue(workspace.status("career").needs_review)
            apply_source_decisions(
                workspace,
                DashboardForm(
                    fields={
                        "source_id": ("source-1",),
                        "accepted_decision": ('["fact-1","career"]',),
                        "changed_decision": (
                            '["fact-1","career"]',
                            '["fact-2","career"]',
                        ),
                        "reason": ("Manual dashboard decision.",),
                    },
                    files={},
                ),
            )

            ledger = workspace.data_store.load_ledger()
            self.assertFalse(workspace.status("career").needs_review)
            self.assertTrue(workspace.status("career").needs_build)
            self.assertTrue(ledger.decision_for("career", "source-1", "fact-1").ticked)
            self.assertFalse(ledger.decision_for("career", "source-1", "fact-2").ticked)


if __name__ == "__main__":
    unittest.main()
