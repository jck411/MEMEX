import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.wiki.ledger import WikiLedger
from app.wiki.source_assets import SourceAssetStore
from app.wiki.source_validation import validate_source_workspace
from app.wiki.storage import WikiDataStore, source_record_path
from tests.helpers import (
    fact_record,
    review_decision_for_fact,
    source_record,
    wiki_record,
    wiki_registry,
)


def source_with_evidence(evidence_ids=("ev-1",)):
    return source_record(
        "source-1",
        fact_record(
            "fact-1",
            "Alice joined Example Co.",
            provenance={
                "evidence_ids": list(evidence_ids),
                "evidence": [
                    {
                        "id": "ev-1",
                        "quote": "Alice joined Example Co.",
                        "source_channel": "document_visible",
                        "page": 1,
                        "locator": "line 1",
                    }
                ],
            },
        ),
    )


class WikiSourceValidationTests(unittest.TestCase):
    def test_validation_accepts_source_asset_and_ledger_references(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = WikiDataStore(root / "data")
            source = source_with_evidence()
            wiki = wiki_record("career", "Career", "career.md")
            store.save_registry(wiki_registry(wiki))
            store.save_source(source)
            self._commit_asset(root, source.source_id)
            ledger = WikiLedger.empty()
            ledger.assign_source("career", source.source_id)
            ledger.set_decision(
                "career",
                source.source_id,
                "fact-1",
                review_decision_for_fact(
                    source.facts[0],
                    wiki=wiki,
                    ticked=True,
                ),
            )
            store.save_ledger(ledger)

            report = validate_source_workspace(root / "data")

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual(1, report.checked_source_count)
            self.assertEqual(1, report.checked_asset_count)

    def test_validation_reports_asset_hash_and_evidence_reference_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = WikiDataStore(root / "data")
            source = source_with_evidence(("missing-ev",))
            store.save_source(source)
            asset_store = self._commit_asset(root, source.source_id)
            manifest = asset_store.load_manifest(source.source_id)
            stored_original = asset_store.asset_dir(source.source_id) / manifest.stored_path
            stored_original.write_text("Alicf joined Example Co.", encoding="utf-8")

            report = validate_source_workspace(root / "data")
            messages = "\n".join(issue.message for issue in report.issues)

            self.assertFalse(report.ok)
            self.assertIn("references unknown evidence 'missing-ev'", messages)
            self.assertIn("sha256 does not match stored original", messages)

    def test_validation_reports_extraction_run_metadata_in_fact_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = WikiDataStore(root / "data")
            source = source_with_evidence()
            fact = source.facts[0]
            fact.provenance["run"] = {
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "usage": {"input_tokens": 10},
            }
            store.save_source(source)
            self._commit_asset(root, source.source_id)

            report = validate_source_workspace(root / "data")
            messages = "\n".join(issue.message for issue in report.issues)

            self.assertFalse(report.ok)
            self.assertIn("stores extraction run metadata in provenance", messages)

    def test_validation_reports_duplicate_source_ids_and_bad_ledger_refs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            store = WikiDataStore(data_root)
            store.save_registry(wiki_registry(wiki_record("career", "Career", "career.md")))
            source_payload = source_with_evidence().to_dict()
            source_record_path(data_root, "source-1").parent.mkdir(parents=True)
            source_record_path(data_root, "source-1").write_text(
                json.dumps(source_payload),
                encoding="utf-8",
            )
            (data_root / "sources" / "copy.json").write_text(
                json.dumps(source_payload),
                encoding="utf-8",
            )
            ledger = WikiLedger.empty()
            ledger.assign_source("career", "missing-source")
            store.save_ledger(ledger)
            ledger_payload = json.loads(store.ledger_path.read_text(encoding="utf-8"))
            ledger_payload["needs_review"] = True
            store.ledger_path.write_text(json.dumps(ledger_payload), encoding="utf-8")

            report = validate_source_workspace(data_root)
            messages = "\n".join(issue.message for issue in report.issues)

            self.assertFalse(report.ok)
            self.assertIn("duplicate source_id 'source-1'", messages)
            self.assertIn("unknown source 'missing-source'", messages)
            self.assertIn("wiki ledger has unknown key(s): needs_review", messages)

    def test_cli_validates_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = WikiDataStore(root / "data")
            store.save_source(source_with_evidence())
            self._commit_asset(root, "source-1")
            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_validate.py"

            result = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(root)],
                check=True,
                text=True,
                capture_output=True,
            )

            self.assertIn("source validation OK: 1 source(s), 1 asset manifest(s)", result.stdout)

    def _commit_asset(self, root: Path, source_id: str) -> SourceAssetStore:
        original = root / f"{source_id}.txt"
        original.write_text("Alice joined Example Co.", encoding="utf-8")
        asset_store = SourceAssetStore(root / "data")
        staged = asset_store.stage_file(source_id, original, source_kind="local_path")
        staged.commit(
            extraction_provider="local",
            extraction_model="test",
            extracted_at="2026-06-23T00:00:00Z",
        )
        return asset_store


if __name__ == "__main__":
    unittest.main()
