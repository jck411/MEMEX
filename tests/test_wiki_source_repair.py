import tempfile
import unittest
from pathlib import Path

from app.wiki.source_repair import repair_source_record
from tests.helpers import fact_record, review_decision_for_fact, source_record, wiki_workspace


class WikiSourceRepairTests(unittest.TestCase):
    def test_fact_edit_regenerates_signature_and_keeps_unchanged_signature(self):
        first = fact_record("fact-1", "Address is 2800 Oak St.", "sig-old")
        second = fact_record("fact-2", "Delivery is Tuesday.", "sig-stable")
        source = source_record(
            "source-1",
            first,
            second,
            title="Rocks",
            extraction_issues=("Possible typo.",),
        )

        repaired = repair_source_record(
            source,
            title="Rocks",
            summary="",
            document_date=None,
            source_type=None,
            fact_texts={"fact-1": "Address is 2200 Oak St."},
        )

        self.assertNotEqual("sig-old", repaired.facts[0].fact_signature)
        self.assertEqual("sig-stable", repaired.facts[1].fact_signature)

    def test_workspace_repair_prunes_deleted_fact_decisions_and_leaves_stale_edits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root)
            workspace.add_wiki("home", "Home", "home.md")
            source = source_record(
                "source-1",
                fact_record("fact-1", "Address is 2800 Oak St.", "sig-old"),
                fact_record("fact-2", "Duplicate detail.", "sig-delete"),
                title="Rocks",
            )
            workspace.save_source(source)
            workspace.assign_source("home", "source-1")
            wiki = workspace.data_store.load_registry().wikis["home"]
            ledger = workspace.data_store.load_ledger()
            ledger.set_decision(
                "home",
                "source-1",
                "fact-1",
                review_decision_for_fact(
                    source.facts[0],
                    wiki=wiki,
                    ticked=True,
                ),
            )
            ledger.set_decision(
                "home",
                "source-1",
                "fact-2",
                review_decision_for_fact(source.facts[1], wiki=wiki),
            )
            workspace.data_store.save_ledger(ledger)

            repaired = repair_source_record(
                source,
                title="Rocks",
                summary="",
                document_date=None,
                source_type=None,
                fact_texts={"fact-1": "Address is 2200 Oak St."},
                deleted_fact_ids=("fact-2",),
                added_fact_texts=("River rock is needed for the yard.",),
            )
            workspace.repair_source("source-1", repaired)

            ledger = workspace.data_store.load_ledger()
            self.assertIsNone(ledger.decision_for("home", "source-1", "fact-2"))
            self.assertTrue(workspace.status("home").needs_review)
            stored = workspace.data_store.load_source("source-1")
            self.assertEqual(("fact-1", "fact-repair-1"), tuple(f.fact_id for f in stored.facts))
            self.assertEqual({"repair": "source_repair"}, stored.facts[1].provenance)


if __name__ == "__main__":
    unittest.main()
