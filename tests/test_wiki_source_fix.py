import json
import unittest

from app.wiki.source_fix import (
    SOURCE_FIX_MODEL,
    FactDiff,
    IssueDiff,
    MetadataDiff,
    SourceFixResult,
    _apply_fix,
    _parse_fix_response,
    _render_fix_prompt,
    fix_source_extraction,
)
from app.wiki.source_fix_html import render_fix_result_message
from tests.helpers import JsonResponse, fact_record, source_record


def _source():
    return source_record(
        "source-1",
        fact_record("fact-1", "Alice joind Example Co."),
        fact_record("fact-2", "Bob left on 2024/01/15."),
        title="Old Title",
        summary="A profile.",
        extraction_issues=("Bob's departure date format is inconsistent.",),
    )


def _response_payload(**overrides):
    payload = {
        "source_id": "source-1",
        "title": "Old Title",
        "summary": "A profile.",
        "document_date": "",
        "source_type": "",
        "facts": [
            {"fact_id": "fact-1", "text": "Alice joind Example Co."},
            {"fact_id": "fact-2", "text": "Bob left on 2024/01/15."},
        ],
        "extraction_issues": [
            {
                "issue_index": 0,
                "message": "Bob's departure date format is inconsistent.",
            }
        ],
    }
    payload.update(overrides)
    return payload


def _openrouter_response(content_text: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": content_text,
                },
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30},
    }


class SourceFixPromptTests(unittest.TestCase):
    def test_render_fix_prompt_includes_full_editable_source_and_instruction(self):
        prompt = _render_fix_prompt(_source(), "fix the spelling of joined")
        payload = json.loads(prompt)

        self.assertEqual("fix the spelling of joined", payload["instruction"])
        editable = payload["editable_source"]
        self.assertEqual("source-1", editable["source_id"])
        self.assertEqual("Old Title", editable["title"])
        self.assertEqual("A profile.", editable["summary"])
        self.assertEqual("", editable["document_date"])
        self.assertEqual("", editable["source_type"])
        self.assertEqual("fact-1", editable["facts"][0]["fact_id"])
        self.assertEqual("Alice joind Example Co.", editable["facts"][0]["text"])
        self.assertEqual(0, editable["extraction_issues"][0]["issue_index"])


class SourceFixParseTests(unittest.TestCase):
    def test_parse_fix_response_accepts_full_editable_source(self):
        result = _parse_fix_response(json.dumps(_response_payload()), _source())

        self.assertEqual("source-1", result["source_id"])
        self.assertEqual(2, len(result["facts"]))

    def test_parse_fix_response_rejects_changed_source_id(self):
        raw = json.dumps(_response_payload(source_id="other-source"))

        with self.assertRaisesRegex(ValueError, "source_id cannot be changed"):
            _parse_fix_response(raw, _source())

    def test_parse_fix_response_rejects_changed_fact_ids(self):
        raw = json.dumps(
            _response_payload(
                facts=[
                    {"fact_id": "fact-2", "text": "Bob left on 2024/01/15."},
                    {"fact_id": "fact-1", "text": "Alice joind Example Co."},
                ],
            )
        )

        with self.assertRaisesRegex(ValueError, "fact IDs must match"):
            _parse_fix_response(raw, _source())

    def test_parse_fix_response_rejects_changed_issue_indexes(self):
        raw = json.dumps(
            _response_payload(
                extraction_issues=[
                    {"issue_index": 1, "message": "Different index."},
                ],
            )
        )

        with self.assertRaisesRegex(ValueError, "issue indexes must match"):
            _parse_fix_response(raw, _source())

    def test_parse_fix_response_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            _parse_fix_response("not json", _source())


class SourceFixApplyTests(unittest.TestCase):
    def test_apply_fix_uses_full_returned_source_and_builds_diffs(self):
        payload = _response_payload(
            title="New Title",
            summary="",
            document_date="2024-01-15",
            source_type="email",
            facts=[
                {"fact_id": "fact-1", "text": "Alice joined Example Co."},
                {"fact_id": "fact-2", "text": "Bob left on 2024-01-15."},
            ],
            extraction_issues=[
                {
                    "issue_index": 0,
                    "message": "Bob's departure date now uses YYYY-MM-DD.",
                }
            ],
        )
        result = _apply_fix(_source(), payload, {}, SOURCE_FIX_MODEL)

        self.assertEqual("New Title", result.source.title)
        self.assertEqual("", result.source.summary)
        self.assertEqual("2024-01-15", result.source.document_date)
        self.assertEqual("email", result.source.source_type)
        self.assertEqual(
            ("Alice joined Example Co.", "Bob left on 2024-01-15."),
            tuple(fact.text for fact in result.source.facts),
        )
        self.assertEqual(
            ("Bob's departure date now uses YYYY-MM-DD.",),
            result.source.extraction_issues,
        )
        self.assertEqual(2, len(result.fact_diffs))
        self.assertEqual(
            (
                MetadataDiff("title", "Old Title", "New Title"),
                MetadataDiff("summary", "A profile.", ""),
                MetadataDiff("document_date", "", "2024-01-15"),
                MetadataDiff("source_type", "", "email"),
            ),
            result.metadata_diffs,
        )
        self.assertEqual(
            (
                IssueDiff(
                    0,
                    "Bob's departure date format is inconsistent.",
                    "Bob's departure date now uses YYYY-MM-DD.",
                ),
            ),
            result.issue_diffs,
        )
        self.assertEqual(7, result.change_count)

    def test_apply_fix_no_changes(self):
        result = _apply_fix(_source(), _response_payload(), {}, SOURCE_FIX_MODEL)

        self.assertFalse(result.changed)
        self.assertEqual(0, result.change_count)
        self.assertEqual("A profile.", result.source.summary)


class SourceFixEndToEndTests(unittest.TestCase):
    def test_fix_source_extraction_calls_openrouter_and_applies(self):
        response_payload = _response_payload(
            summary="A corrected profile.",
            facts=[
                {"fact_id": "fact-1", "text": "Alice joined Example Co."},
                {"fact_id": "fact-2", "text": "Bob left on 2024-01-15."},
            ],
            extraction_issues=[
                {
                    "issue_index": 0,
                    "message": "Bob's departure date now uses YYYY-MM-DD.",
                }
            ],
        )
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return JsonResponse(_openrouter_response(json.dumps(response_payload)))

        result = fix_source_extraction(
            _source(),
            "fix the spelling of joined, change dates to YYYY-MM-DD",
            "test-api-key",
            opener=opener,
        )

        self.assertTrue(result.changed)
        self.assertEqual(2, len(result.fact_diffs))
        self.assertEqual(1, len(result.issue_diffs))
        self.assertEqual("A corrected profile.", result.source.summary)
        self.assertIn("openrouter", seen["url"])
        self.assertEqual(SOURCE_FIX_MODEL, seen["body"]["model"])
        self.assertEqual(0, seen["body"]["temperature"])
        self.assertIn(
            "source_id", seen["body"]["response_format"]["json_schema"]["schema"]["required"]
        )

    def test_fix_source_extraction_allows_metadata_only_source(self):
        source = source_record("source-1", title="Wrong Title")
        response_payload = _response_payload(
            title="Right Title",
            summary="",
            facts=[],
            extraction_issues=[],
        )

        def opener(request, timeout):
            return JsonResponse(_openrouter_response(json.dumps(response_payload)))

        result = fix_source_extraction(source, "fix title", "test-api-key", opener=opener)

        self.assertEqual("Right Title", result.source.title)
        self.assertEqual(
            (MetadataDiff("title", "Wrong Title", "Right Title"),), result.metadata_diffs
        )

    def test_fix_source_extraction_rejects_empty_instruction(self):
        with self.assertRaisesRegex(ValueError, "fix instruction is required"):
            fix_source_extraction(_source(), "  ", "key")


class SourceFixHtmlTests(unittest.TestCase):
    def test_render_fix_result_message_no_changes(self):
        result = SourceFixResult(
            source=source_record("s", title="T"),
            fact_diffs=(),
            metadata_diffs=(),
        )
        self.assertEqual(
            f"no changes needed; model {SOURCE_FIX_MODEL}",
            render_fix_result_message(result),
        )

    def test_render_fix_result_message_with_diffs(self):
        result = SourceFixResult(
            source=source_record("s", title="T"),
            fact_diffs=(FactDiff("f1", "old", "new"),),
            metadata_diffs=(MetadataDiff("title", "Old", "New"),),
            issue_diffs=(IssueDiff(0, "old issue", "new issue"),),
        )
        message = render_fix_result_message(result)
        self.assertIn("1 fact(s) fixed", message)
        self.assertIn("metadata updated (title)", message)
        self.assertIn("1 issue(s) fixed", message)
        self.assertIn(f"model {SOURCE_FIX_MODEL}", message)


if __name__ == "__main__":
    unittest.main()
