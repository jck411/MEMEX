import json
import tempfile
import unittest
from pathlib import Path

from app.wiki.ledger import WikiLedger
from app.wiki.source_assets import (
    SourceAssetManifest,
    SourceAssetStore,
    sha256_for_path,
    source_asset_dir,
)
from app.wiki.status import mark_build_current, status_for_wiki
from app.wiki.storage import WikiDataStore, source_record_path
from tests.helpers import (
    fact_record,
    review_decision_for_fact,
    source_record,
    wiki_record,
    wiki_registry,
)


class WikiStorageTests(unittest.TestCase):
    def test_missing_store_loads_empty_top_level_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = WikiDataStore(temp_dir)

            self.assertEqual({}, store.load_ledger().to_dict()["assignments"])
            self.assertEqual({}, store.load_registry().to_dict()["wikis"])
            self.assertEqual({}, store.load_sources())
            with self.assertRaises(FileNotFoundError):
                store.load_source("missing")

    def test_round_trips_registry_ledger_and_source_records(self):
        source = source_record(
            "web/article 1",
            fact_record(
                "fact-1",
                "Alice joined Example Co.",
                provenance={"page": 2, "quote": "joined Example Co."},
            ),
            summary="A short source summary.",
        )
        registry = wiki_registry(
            wiki_record(
                "career",
                "Career",
                "career.md",
                description="Employment and professional history.",
            )
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", source.source_id)
        wiki = registry.wikis["career"]
        ledger.set_decision(
            "career",
            source.source_id,
            "fact-1",
            review_decision_for_fact(
                source.facts[0],
                wiki=wiki,
                ticked=True,
                reason="Career history.",
                reviewed_at="2026-06-22T12:00:00Z",
            ),
        )
        mark_build_current(wiki, ledger, [source])

        with tempfile.TemporaryDirectory() as temp_dir:
            store = WikiDataStore(temp_dir)
            store.save_registry(registry)
            store.save_ledger(ledger)
            store.save_source(source)

            self.assertEqual(registry, store.load_registry())
            self.assertEqual(
                "Employment and professional history.",
                store.load_registry().wikis["career"].description,
            )
            self.assertEqual(ledger.to_dict(), store.load_ledger().to_dict())
            self.assertEqual(source, store.load_source(source.source_id))
            self.assertEqual({source.source_id: source}, store.load_sources())

    def test_source_record_path_escapes_ids_inside_sources_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = source_record_path(temp_dir, "../nested/source 1")

            self.assertEqual(Path(temp_dir) / "sources", path.parent)
            self.assertEqual("..%2Fnested%2Fsource%201.json", path.name)

    def test_storage_rejects_invalid_source_and_asset_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "source_id"):
                source_record_path(temp_dir, "")

        for stored_path in ("/absolute.txt", "../escape.txt", "original/../escape.txt"):
            with self.subTest(stored_path=stored_path):
                with self.assertRaisesRegex(ValueError, "relative path inside the asset"):
                    SourceAssetManifest(
                        source_id="source-1",
                        source_kind="local_path",
                        original_name="profile.txt",
                        stored_path=stored_path,
                        mime_type="text/plain",
                        size_bytes=1,
                        sha256="a" * 64,
                        created_at="2026-06-23T00:00:00Z",
                    )

    def test_saved_ledger_does_not_store_derived_status_flags(self):
        source = source_record("source-1", fact_record("fact-1", "Alice joined Example Co."))
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        wiki = wiki_record("career", "Career", "career.md")
        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(source.facts[0], wiki=wiki),
        )
        status = status_for_wiki(wiki, ledger, [source])
        self.assertFalse(status.needs_review)

        with tempfile.TemporaryDirectory() as temp_dir:
            store = WikiDataStore(temp_dir)
            store.save_ledger(ledger)

            payload = json.loads(store.ledger_path.read_text(encoding="utf-8"))
            serialized = json.dumps(payload, sort_keys=True)
            self.assertNotIn("needs_review", serialized)
            self.assertNotIn("needs_build", serialized)
            self.assertNotIn("current", serialized)
            self.assertNotIn("reviewed", serialized)
            self.assertNotIn("stale", serialized)

    def test_save_sources_keeps_one_file_per_source(self):
        first = source_record("source-2", title="Second")
        second = source_record("source-1", title="First")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = WikiDataStore(temp_dir)
            store.save_sources([first, second])

            self.assertEqual(
                ["source-1.json", "source-2.json"],
                sorted(path.name for path in store.sources_dir.glob("*.json")),
            )
            self.assertEqual(("source-1", "source-2"), tuple(sorted(store.load_sources())))

    def test_delete_source_removes_source_file(self):
        source = source_record("source-1")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = WikiDataStore(temp_dir)
            store.save_source(source)

            self.assertTrue(store.delete_source("source-1"))
            self.assertFalse(source_record_path(temp_dir, "source-1").exists())
            self.assertFalse(store.delete_source("source-1"))

    def test_source_asset_store_stages_original_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = root / "Profile Note.md"
            original.write_text("# Profile\n\nAlice joined Example Co.", encoding="utf-8")
            store = SourceAssetStore(root / "data")

            staged = store.stage_file(
                "../nested/source 1",
                original,
                source_kind="local_path",
            )
            manifest = staged.commit(
                extraction_provider="anthropic",
                extraction_model="claude-sonnet-4-6",
                extracted_at="2026-06-23T00:00:00Z",
                usage={"input_tokens": 10},
            )

            asset_dir = source_asset_dir(root / "data", "../nested/source 1")
            stored_original = asset_dir / "original" / "Profile Note.md"
            self.assertEqual(asset_dir, store.asset_dir("../nested/source 1"))
            self.assertEqual(
                "source-assets/..%2Fnested%2Fsource%201", str(asset_dir.relative_to(root / "data"))
            )
            self.assertTrue(stored_original.exists())
            self.assertEqual(sha256_for_path(original), manifest.sha256)
            self.assertEqual("original/Profile Note.md", manifest.stored_path)
            self.assertEqual("text/markdown", manifest.mime_type)
            self.assertEqual(manifest, store.load_manifest("../nested/source 1"))
            self.assertEqual(
                "../nested/source 1",
                store.duplicate_source_id_for_sha256(manifest.sha256),
            )


if __name__ == "__main__":
    unittest.main()
