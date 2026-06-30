import unittest

from app.wiki.dashboard_forms import DashboardForm
from app.wiki.dashboard_source_actions import source_record_from_repair_form
from tests.helpers import fact_record, source_record


class WikiDashboardSourceActionTests(unittest.TestCase):
    def test_partial_repair_form_preserves_missing_fields_facts_and_issues(self):
        source = source_record(
            "source-1",
            fact_record("fact-1", "Address is 2800 Oak St.", "sig-old"),
            fact_record("fact-2", "Delivery is Tuesday.", "sig-stable"),
            title="Rocks",
            summary="Original summary.",
            document_date="2026-06-23",
            source_type="invoice",
            extraction_issues=("Possible typo.",),
        )
        form = DashboardForm(
            fields={
                "partial_repair": ("1",),
                "fact_id": ("fact-1",),
                "fact_text": ("Address is 2200 Oak St.",),
            },
            files={},
        )

        repaired = source_record_from_repair_form(source, form)

        self.assertEqual("Rocks", repaired.title)
        self.assertEqual("Original summary.", repaired.summary)
        self.assertEqual("2026-06-23", repaired.document_date)
        self.assertEqual("invoice", repaired.source_type)
        self.assertEqual(("Possible typo.",), repaired.extraction_issues)
        self.assertEqual(
            ("Address is 2200 Oak St.", "Delivery is Tuesday."),
            tuple(fact.text for fact in repaired.facts),
        )

    def test_partial_repair_form_can_clear_extracted_metadata_fields(self):
        source = source_record(
            "source-1",
            fact_record("fact-1", "Address is 2800 Oak St.", "sig-old"),
            title="Rocks",
            summary="Original summary.",
            document_date="2026-06-23",
            source_type="invoice",
        )
        form = DashboardForm(
            fields={
                "partial_repair": ("1",),
                "summary": ("",),
                "document_date": ("",),
                "source_type": ("",),
            },
            files={},
        )

        repaired = source_record_from_repair_form(source, form)

        self.assertEqual("Rocks", repaired.title)
        self.assertEqual("", repaired.summary)
        self.assertIsNone(repaired.document_date)
        self.assertIsNone(repaired.source_type)
        self.assertEqual(("Address is 2800 Oak St.",), tuple(f.text for f in repaired.facts))

    def test_repair_form_marks_added_fact_as_dashboard_repair(self):
        source = source_record(
            "source-1",
            fact_record("fact-1", "Address is 2800 Oak St.", "sig-old"),
            title="Rocks",
        )
        form = DashboardForm(
            fields={
                "partial_repair": ("1",),
                "new_fact_text": ("River rock is needed for the yard.",),
            },
            files={},
        )

        repaired = source_record_from_repair_form(source, form)

        self.assertEqual(("fact-1", "fact-repair-1"), tuple(f.fact_id for f in repaired.facts))
        self.assertEqual({"repair": "dashboard"}, repaired.facts[1].provenance)


if __name__ == "__main__":
    unittest.main()
