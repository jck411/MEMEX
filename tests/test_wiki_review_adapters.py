import json
import unittest

from app.wiki.review import ReviewFact, ReviewResult, WikiReviewContext
from app.wiki.review_prompts import (
    parse_review_response,
    render_review_prompt,
    review_prompt_payload,
)
from app.wiki.reviewers import FixtureReviewProvider


def review_facts():
    return (
        ReviewFact(
            wiki_id="career",
            source_id="source-1",
            source_title="Profile",
            fact_id="fact-1",
            fact_signature="sig-1",
            text="Alice joined Example Co.",
        ),
        ReviewFact(
            wiki_id="career",
            source_id="source-1",
            source_title="Profile",
            fact_id="fact-2",
            fact_signature="sig-2",
            text="Alice lives in Boston.",
        ),
    )


def review_context():
    return WikiReviewContext(
        wiki_id="career",
        wiki_title="Career",
        wiki_intention="Track durable employment, role, and professional history.",
        source_id="source-1",
        source_title="Profile",
        source_summary="A short professional profile.",
    )


class WikiReviewAdapterTests(unittest.TestCase):
    def test_review_prompt_payload_is_compact_and_schemaed(self):
        payload = review_prompt_payload(review_context(), review_facts())
        rendered = render_review_prompt(review_context(), review_facts())

        self.assertEqual("career", payload["wiki"]["wiki_id"])
        self.assertEqual(
            "Track durable employment, role, and professional history.",
            payload["wiki"]["intention"],
        )
        self.assertEqual("source-1", payload["source"]["source_id"])
        self.assertEqual(("fact-1", "fact-2"), tuple(fact["fact_id"] for fact in payload["facts"]))
        self.assertIn("output_schema", payload)
        self.assertEqual(payload, json.loads(rendered))

    def test_parse_review_response_requires_exact_expected_fact_ids(self):
        parsed = parse_review_response(
            {
                "decisions": [
                    {"fact_id": "fact-2", "ticked": False, "reason": "Out of scope."},
                    {"fact_id": "fact-1", "ticked": True, "reason": "Career fact."},
                ]
            },
            review_facts(),
        )

        self.assertEqual(("fact-1", "fact-2"), tuple(result.fact_id for result in parsed))
        self.assertTrue(parsed[0].ticked)
        self.assertFalse(parsed[1].ticked)

        with self.assertRaisesRegex(ValueError, "missing review decisions"):
            parse_review_response(
                {"decisions": [{"fact_id": "fact-1", "ticked": True}]},
                review_facts(),
            )
        with self.assertRaisesRegex(ValueError, "unexpected review decisions"):
            parse_review_response(
                {
                    "decisions": [
                        {"fact_id": "fact-1", "ticked": True},
                        {"fact_id": "fact-2", "ticked": False},
                        {"fact_id": "fact-3", "ticked": True},
                    ]
                },
                review_facts(),
            )
        with self.assertRaisesRegex(ValueError, "duplicate review decisions"):
            parse_review_response(
                {
                    "decisions": [
                        {"fact_id": "fact-1", "ticked": True},
                        {"fact_id": "fact-1", "ticked": False},
                        {"fact_id": "fact-2", "ticked": False},
                    ]
                },
                review_facts(),
            )

    def test_fixture_provider_returns_deterministic_decisions(self):
        provider = FixtureReviewProvider.from_payload(
            {
                "decisions": [{"fact_id": "fact-1", "ticked": True, "reason": "Career fact."}],
                "default_ticked": False,
                "default_reason": "Default no.",
            }
        )

        results = provider.review(review_context(), review_facts()).decisions

        self.assertEqual(
            (
                ReviewResult("fact-1", True, "Career fact."),
                ReviewResult("fact-2", False, "Default no."),
            ),
            results,
        )

    def test_fixture_provider_can_use_default_only_payload(self):
        provider = FixtureReviewProvider.from_payload(
            {"default_ticked": False, "default_reason": "Default no."}
        )

        results = provider.review(review_context(), review_facts()).decisions

        self.assertEqual(
            (
                ReviewResult("fact-1", False, "Default no."),
                ReviewResult("fact-2", False, "Default no."),
            ),
            results,
        )

    def test_fixture_provider_requires_decisions_without_default(self):
        provider = FixtureReviewProvider.from_payload([{"fact_id": "fact-1", "ticked": True}])

        with self.assertRaisesRegex(KeyError, "fact-2"):
            provider.review(review_context(), review_facts())

    def test_fixture_provider_rejects_duplicate_fixture_decisions(self):
        with self.assertRaisesRegex(ValueError, "duplicate fixture decisions"):
            FixtureReviewProvider.from_payload(
                [
                    {"fact_id": "fact-1", "ticked": True},
                    {"fact_id": "fact-1", "ticked": False},
                ]
            )


if __name__ == "__main__":
    unittest.main()
