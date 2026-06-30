import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.wiki.review import ReviewResult
from app.wiki.source_assets import SourceAssetStore
from app.wiki.source_validation import validate_source_workspace
from app.wiki.storage import WikiDataStore
from tests.helpers import (
    fixture_review_provider,
    fixture_wiki_build_provider,
    profile_source_record,
    wiki_record,
    wiki_registry,
    wiki_workspace,
    write_text_source,
)


class WikiWorkflowTests(unittest.TestCase):
    def test_workspace_runs_review_and_build_loop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            source = profile_source_record()
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(source)

            assigned = workspace.assign_source("career", "source-1")
            self.assertTrue(assigned.needs_review)
            self.assertEqual(
                ("fact-1", "fact-2"),
                tuple(fact.fact_id for fact in workspace.review_delta("career")),
            )

            partial = workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-1", True, "Career history.")],
            )
            self.assertEqual(1, partial.applied_count)
            self.assertEqual(1, partial.remaining_review_count)
            self.assertTrue(partial.status.needs_review)

            reviewed = workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-2", False, "Location is out of scope.")],
            )
            self.assertEqual(0, reviewed.remaining_review_count)
            self.assertFalse(reviewed.status.needs_review)
            self.assertTrue(reviewed.status.needs_build)

            built = workspace.build_wiki("career", fixture_wiki_build_provider())
            self.assertTrue(built.status.current)
            self.assertEqual(root / "vault" / "career.md", built.path)
            self.assertIn(
                "Alice joined Example Co.",
                built.path.read_text(encoding="utf-8"),
            )

            reloaded = wiki_workspace(root)
            self.assertTrue(reloaded.status("career").current)

    def test_workspace_add_wiki_rejects_paths_outside_vault(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)

            invalid_paths = (
                "../escape.md",
                "nested/../../escape.md",
                str(root / "outside.md"),
            )
            for index, path in enumerate(invalid_paths, start=1):
                with self.subTest(path=path):
                    with self.assertRaises(ValueError):
                        workspace.add_wiki(f"escape-{index}", "Escape", path)

            self.assertEqual((), workspace.dashboard().wikis)

    def test_workspace_add_wiki_rejects_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)

            workspace.add_wiki("career", "Career", "career.md")

            with self.assertRaises(ValueError):
                workspace.add_wiki("work", "Work", "career.md")

    def test_delete_wiki_removes_registry_ledger_and_vault_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            source = profile_source_record()
            workspace.add_wiki("career", "Career", "career.md")
            workspace.add_wiki("life", "Life", "life.md")
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")
            workspace.assign_source("life", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [
                    ReviewResult("fact-1", True, "Career history."),
                    ReviewResult("fact-2", False, "Location is out of scope."),
                ],
            )
            workspace.build_wiki("career", fixture_wiki_build_provider())

            deleted = workspace.delete_wiki("career")
            registry = workspace.data_store.load_registry()
            ledger = workspace.data_store.load_ledger()

            self.assertEqual("career", deleted.wiki_id)
            self.assertNotIn("career", registry.wikis)
            self.assertFalse((root / "vault" / "career.md").exists())
            self.assertEqual((), ledger.assigned_sources("career"))
            self.assertIsNone(ledger.decision_for("career", "source-1", "fact-1"))
            self.assertNotIn("career", ledger.build_baselines)
            self.assertEqual(("source-1",), ledger.assigned_sources("life"))
            self.assertIn("source-1", workspace.data_store.load_sources())

    def test_delete_wiki_keeps_vault_file_still_referenced_by_another_wiki(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.data_store.save_registry(
                wiki_registry(
                    wiki_record("career", "Career", "shared.md"),
                    wiki_record("work", "Work", "shared.md"),
                )
            )
            shared_path = root / "vault" / "shared.md"
            shared_path.parent.mkdir(parents=True)
            shared_path.write_text("# Shared", encoding="utf-8")

            workspace.delete_wiki("career")

            self.assertTrue(shared_path.exists())
            self.assertEqual(("work",), workspace.data_store.load_registry().active_ids())

    def test_delete_wiki_ledger_failure_preserves_valid_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            text_path = write_text_source(root, text="# Note\n\nAlice joined Example Co.")
            workspace.import_text_source(text_path, "source-1")
            workspace.assign_source("career", "source-1")

            with patch.object(WikiDataStore, "save_ledger", side_effect=OSError("ledger failed")):
                with self.assertRaisesRegex(OSError, "ledger failed"):
                    workspace.delete_wiki("career")

            report = validate_source_workspace(root / "data")
            self.assertTrue(report.ok, report.to_dict())
            self.assertIn("career", workspace.data_store.load_registry().wikis)
            self.assertEqual(
                ("source-1",),
                workspace.data_store.load_ledger().assigned_sources("career"),
            )

    def test_delete_source_clears_review_need_and_keeps_build_need(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            source = profile_source_record()
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [
                    ReviewResult("fact-1", True, "Career history."),
                    ReviewResult("fact-2", False, "Location is out of scope."),
                ],
            )
            workspace.build_wiki("career", fixture_wiki_build_provider())

            workspace.delete_source("source-1")
            status = workspace.status("career")
            ledger = workspace.data_store.load_ledger()

            self.assertFalse(status.needs_review)
            self.assertTrue(status.needs_build)
            self.assertEqual((), workspace.review_delta("career"))
            self.assertEqual((), ledger.assigned_sources("career"))
            self.assertIsNone(ledger.decision_for("career", "source-1", "fact-1"))

    def test_delete_source_ledger_failure_preserves_valid_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            text_path = write_text_source(root, text="# Note\n\nAlice joined Example Co.")
            workspace.import_text_source(text_path, "source-1")
            workspace.assign_source("career", "source-1")

            with patch.object(WikiDataStore, "save_ledger", side_effect=OSError("ledger failed")):
                with self.assertRaisesRegex(OSError, "ledger failed"):
                    workspace.delete_source("source-1")

            report = validate_source_workspace(root / "data")
            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual("source-1", workspace.data_store.load_source("source-1").source_id)
            self.assertTrue(workspace.source_assets().asset_dir("source-1").exists())
            self.assertEqual(
                ("source-1",),
                workspace.data_store.load_ledger().assigned_sources("career"),
            )

    def test_delete_source_asset_failure_rolls_back_valid_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            text_path = write_text_source(root, text="# Note\n\nAlice joined Example Co.")
            workspace.import_text_source(text_path, "source-1")
            workspace.assign_source("career", "source-1")

            with patch.object(SourceAssetStore, "delete", side_effect=OSError("asset failed")):
                with self.assertRaisesRegex(OSError, "asset failed"):
                    workspace.delete_source("source-1")

            report = validate_source_workspace(root / "data")
            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual("source-1", workspace.data_store.load_source("source-1").source_id)
            self.assertTrue(workspace.source_assets().asset_dir("source-1").exists())
            self.assertEqual(
                ("source-1",),
                workspace.data_store.load_ledger().assigned_sources("career"),
            )

    def test_unassign_source_clears_review_need_and_keeps_build_need(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            source = profile_source_record()
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [
                    ReviewResult("fact-1", True, "Career history."),
                    ReviewResult("fact-2", False, "Location is out of scope."),
                ],
            )
            workspace.build_wiki("career", fixture_wiki_build_provider())

            status = workspace.unassign_source("career", "source-1")

            self.assertFalse(status.needs_review)
            self.assertTrue(status.needs_build)
            self.assertEqual((), workspace.review_delta("career"))

    def test_import_text_source_preserves_original_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            text_path = write_text_source(root, text="# Note\n\nAlice joined Example Co.")
            workspace = wiki_workspace(root)

            result = workspace.import_text_source(text_path, "source-1")
            source = result.source

            manifest = workspace.source_assets().load_manifest("source-1")
            stored_original = workspace.source_assets().asset_dir("source-1") / manifest.stored_path
            self.assertEqual("source-1", source.source_id)
            self.assertTrue(result.created)
            self.assertEqual("local_path", manifest.source_kind)
            self.assertEqual("note.md", manifest.original_name)
            self.assertEqual("local", manifest.extraction_provider)
            self.assertEqual("text-v1", manifest.extraction_model)
            self.assertEqual(
                "# Note\n\nAlice joined Example Co.",
                stored_original.read_text(encoding="utf-8"),
            )

    def test_import_text_source_returns_existing_source_for_duplicate_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_path = write_text_source(root, "note.md", "# Note\n\nAlice joined Example Co.")
            duplicate_path = write_text_source(root, "copy.md", "# Note\n\nAlice joined Example Co.")
            workspace = wiki_workspace(root)

            first = workspace.import_text_source(first_path, "source-1")
            duplicate = workspace.import_text_source(duplicate_path, "source-2")

            self.assertTrue(first.created)
            self.assertFalse(duplicate.created)
            self.assertTrue(duplicate.duplicate)
            self.assertEqual("source-1", duplicate.duplicate_source_id)
            self.assertEqual(first.source, duplicate.source)
            self.assertFalse(workspace.source_assets().asset_dir("source-2").exists())
            with self.assertRaises(FileNotFoundError):
                workspace.data_store.load_source("source-2")

    def test_cli_drives_end_to_end_dev_loop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.json"
            decisions_path = root / "decisions.json"
            source_path.write_text(
                json.dumps(profile_source_record().to_dict()),
                encoding="utf-8",
            )
            decisions_path.write_text(
                json.dumps(
                    [
                        {
                            "fact_id": "fact-1",
                            "ticked": True,
                            "reason": "Career history.",
                        },
                        {
                            "fact_id": "fact-2",
                            "ticked": False,
                            "reason": "Location is out of scope.",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_dev.py"
            base = [sys.executable, str(script), "--repo-root", str(root)]

            self._run(base + ["add-wiki", "career", "Career", "career.md"])
            self._run(base + ["import-source", str(source_path)])
            assign = self._run(base + ["assign", "career", "source-1"])
            self.assertIn("needs_review", assign.stdout)

            delta = self._run(base + ["review-delta", "career"])
            self.assertIn("source-1\tfact-1\tAlice joined Example Co.", delta.stdout)

            review = self._run(base + ["review", "career", "source-1", str(decisions_path)])
            self.assertIn("remaining_review=0", review.stdout)
            self.assertIn("needs_build", review.stdout)

            build = self._run(base + ["build", "career", "--fixture"])
            self.assertIn("current", build.stdout)
            self.assertIn(
                "Alice joined Example Co.",
                (root / "vault" / "career.md").read_text(encoding="utf-8"),
            )

            delete = self._run(base + ["delete-wiki", "career"])
            self.assertIn("deleted wiki career -> career.md", delete.stdout)
            self.assertFalse((root / "vault" / "career.md").exists())
            missing_status = subprocess.run(
                base + ["status", "career"],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(0, missing_status.returncode)

    def test_workspace_reviews_pending_facts_with_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(profile_source_record())
            workspace.assign_source("career", "source-1")

            result = workspace.review_source_with_provider(
                "career",
                "source-1",
                fixture_review_provider(
                    ReviewResult("fact-1", True, "Career history."),
                    ReviewResult("fact-2", False, "Location is out of scope."),
                ),
            )

            self.assertEqual(2, result.applied_count)
            self.assertFalse(result.status.needs_review)
            self.assertTrue(result.status.needs_build)

    def test_cli_review_fixture_drives_pending_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.json"
            decisions_path = root / "fixture.json"
            source_path.write_text(
                json.dumps(profile_source_record().to_dict()),
                encoding="utf-8",
            )
            decisions_path.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "fact_id": "fact-1",
                                "ticked": True,
                                "reason": "Career history.",
                            },
                            {
                                "fact_id": "fact-2",
                                "ticked": False,
                                "reason": "Location is out of scope.",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_dev.py"
            base = [sys.executable, str(script), "--repo-root", str(root)]

            self._run(base + ["add-wiki", "career", "Career", "career.md"])
            self._run(base + ["import-source", str(source_path)])
            self._run(base + ["assign", "career", "source-1"])
            review = self._run(base + ["review-fixture", "career", "source-1", str(decisions_path)])

            self.assertIn("applied 2", review.stdout)
            self.assertIn("remaining_review=0", review.stdout)
            self.assertIn("needs_build", review.stdout)

    def test_workspace_reviews_only_source_delta_with_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(profile_source_record())
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-1", True, "Already reviewed.")],
            )

            result = workspace.review_source_with_provider(
                "career",
                "source-1",
                fixture_review_provider(ReviewResult("fact-2", False, "Location.")),
            )

            self.assertEqual(1, result.applied_count)
            self.assertFalse(result.status.needs_review)
            self.assertTrue(result.status.needs_build)

    def test_workspace_can_force_provider_review_for_all_current_source_facts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            workspace.save_source(profile_source_record())
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [
                    ReviewResult("fact-1", True, "Old career reason."),
                    ReviewResult("fact-2", False, "Old location reason."),
                ],
            )

            result = workspace.review_source_with_provider(
                "career",
                "source-1",
                fixture_review_provider(
                    ReviewResult("fact-1", False, "Rerun excluded career."),
                    ReviewResult("fact-2", True, "Rerun included location."),
                ),
                review_all=True,
            )

            ledger = workspace.data_store.load_ledger()
            self.assertEqual(2, result.applied_count)
            self.assertFalse(result.status.needs_review)
            self.assertEqual(
                "Rerun excluded career.",
                ledger.decision_for("career", "source-1", "fact-1").reason,
            )
            self.assertEqual(
                "Rerun included location.",
                ledger.decision_for("career", "source-1", "fact-2").reason,
            )

    def _run(self, command):
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )


if __name__ == "__main__":
    unittest.main()
