import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.wiki.review import ReviewResult
from app.wiki.source_assets import SourceAssetStore
from app.wiki.source_validation import validate_source_workspace
from app.wiki.storage import WikiDataStore
from tests.helpers import (
    fixture_wiki_build_provider,
    profile_source_record,
    wiki_workspace,
    write_text_source,
)


class WikiSourceDeletionTests(unittest.TestCase):
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

    def test_delete_source_asset_stage_failure_preserves_valid_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            text_path = write_text_source(root, text="# Note\n\nAlice joined Example Co.")
            workspace.import_text_source(text_path, "source-1")
            workspace.assign_source("career", "source-1")

            with patch.object(SourceAssetStore, "stage_delete", side_effect=OSError("asset failed")):
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

    def test_delete_source_asset_cleanup_failure_still_deletes_active_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("career", "Career", "career.md")
            text_path = write_text_source(root, text="# Note\n\nAlice joined Example Co.")
            workspace.import_text_source(text_path, "source-1")
            workspace.assign_source("career", "source-1")

            with patch("app.wiki.source_assets.shutil.rmtree", side_effect=OSError("cleanup failed")):
                deleted = workspace.delete_source("source-1")

            report = validate_source_workspace(root / "data")
            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual("source-1", deleted.source_id)
            with self.assertRaises(FileNotFoundError):
                workspace.data_store.load_source("source-1")
            self.assertFalse(workspace.source_assets().asset_dir("source-1").exists())
            self.assertEqual((), workspace.data_store.load_ledger().assigned_sources("career"))


if __name__ == "__main__":
    unittest.main()
