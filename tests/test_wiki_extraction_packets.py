import unittest

from app.wiki.extraction_packets import (
    ExtractionPacketError,
    add_run_metadata,
    source_record_from_extraction_packet,
    validate_extraction_packet,
)
from tests.helpers import extraction_packet


def _packet(source_id="source-1"):
    payload = extraction_packet(
        source_id,
        date="2026-06-22",
        summary="Alice joined Example Co.",
        fact_text="Alice joined Example Co. in 2024.",
        issues=(
            {
                "id": "issue_review",
                "message": "Review employment dates.",
                "evidence_ids": ["ev_joined"],
            },
        ),
    )
    payload["run"] = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "prompt": "test",
        "schema": "memex_wiki_prep_extraction",
        "extracted_at": "2026-06-22T00:00:00Z",
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }
    return payload


class WikiExtractionPacketTests(unittest.TestCase):
    def test_packet_normalizes_to_source_record_with_evidence_provenance(self):
        source = source_record_from_extraction_packet(
            _packet(),
            expected_source_id="source-1",
        )

        self.assertEqual("source-1", source.source_id)
        self.assertEqual("Profile", source.title)
        self.assertEqual("Alice joined Example Co.", source.summary)
        self.assertEqual("2026-06-22", source.document_date)
        self.assertEqual("text", source.source_type)
        self.assertEqual(("Review employment dates.",), source.extraction_issues)
        self.assertEqual("fact_joined", source.facts[0].fact_id)
        self.assertNotIn("sensitivity", source.facts[0].provenance)
        self.assertNotIn("run", source.facts[0].provenance)
        self.assertNotIn("source_fact_id", source.facts[0].provenance)
        self.assertEqual("ev_joined", source.facts[0].provenance["evidence"][0]["id"])

    def test_packet_normalizes_known_metadata_whitespace(self):
        packet = _packet()
        packet["document"]["title"] = "  Profile  "
        packet["document"]["type"] = "  text  "
        packet["document"]["date"] = "  2026-06-22  "
        packet["summary"] = "  Alice joined Example Co.  "

        source = source_record_from_extraction_packet(packet)

        self.assertEqual("Profile", source.title)
        self.assertEqual("text", source.source_type)
        self.assertEqual("2026-06-22", source.document_date)
        self.assertEqual("Alice joined Example Co.", source.summary)

    def test_add_run_metadata_preserves_empty_usage_mapping(self):
        packet = add_run_metadata(
            extraction_packet("source-1"),
            provider="test",
            model="test",
            prompt="test",
            extracted_at="2026-06-22T00:00:00Z",
            usage={},
        )

        self.assertEqual({}, packet["run"]["usage"])

    def test_packet_validation_fails_closed_on_shape_errors(self):
        packet = _packet()
        packet["facts"][0]["evidence_ids"] = ["missing"]

        with self.assertRaises(ExtractionPacketError):
            validate_extraction_packet(packet)

        with self.assertRaises(ExtractionPacketError):
            validate_extraction_packet(_packet("other"), expected_source_id="source-1")


if __name__ == "__main__":
    unittest.main()
