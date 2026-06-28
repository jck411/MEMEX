import json
import unittest

from app.wiki.openrouter_client import OPENROUTER_CHAT_COMPLETIONS_URL
from app.wiki.openrouter_review import OPENROUTER_REVIEW_MODEL, OpenRouterReviewProvider
from app.wiki.review import ReviewFact, WikiReviewContext
from app.wiki.review_prompts import REVIEW_RESPONSE_SCHEMA
from tests.helpers import JsonResponse


def review_context():
    return WikiReviewContext(
        wiki_id="career",
        wiki_title="Career",
        wiki_intention="Track durable employment and professional role facts.",
        source_id="source-1",
        source_title="Profile",
        source_summary="A profile about Alice.",
    )


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


class WikiOpenRouterReviewTests(unittest.TestCase):
    def test_openrouter_review_requests_strict_json_decisions(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["headers"] = dict(request.header_items())
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return JsonResponse(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps(
                                    {
                                        "decisions": [
                                            {
                                                "fact_id": "fact-1",
                                                "ticked": True,
                                                "reason": "Employment history.",
                                            },
                                            {
                                                "fact_id": "fact-2",
                                                "ticked": False,
                                                "reason": "Residence is out of scope.",
                                            },
                                        ]
                                    }
                                )
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "total_tokens": 120,
                        "cost": 0.00042,
                    },
                }
            )

        result = OpenRouterReviewProvider(api_key="key", opener=opener).review(
            review_context(),
            review_facts(),
        )

        self.assertEqual(OPENROUTER_CHAT_COMPLETIONS_URL, seen["url"])
        self.assertEqual(120, seen["timeout"])
        self.assertEqual("Bearer key", seen["headers"]["Authorization"])
        self.assertEqual(OPENROUTER_REVIEW_MODEL, seen["body"]["model"])
        self.assertEqual({"require_parameters": True}, seen["body"]["provider"])
        self.assertEqual(
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "memex_review_decisions",
                    "strict": True,
                    "schema": REVIEW_RESPONSE_SCHEMA,
                },
            },
            seen["body"]["response_format"],
        )
        prompt = seen["body"]["messages"][1]["content"]
        self.assertIn("Track durable employment", prompt)
        self.assertEqual(("fact-1", "fact-2"), tuple(item.fact_id for item in result.decisions))
        self.assertTrue(result.decisions[0].ticked)
        self.assertFalse(result.decisions[1].ticked)
        self.assertEqual("openrouter", result.provider)
        self.assertEqual(OPENROUTER_REVIEW_MODEL, result.model)
        self.assertEqual(0.00042, result.usage["cost"])

    def test_empty_review_batch_skips_api_call(self):
        def opener(request, timeout):
            raise AssertionError("empty review should not call OpenRouter")

        result = OpenRouterReviewProvider(api_key="key", opener=opener).review(
            review_context(),
            (),
        )

        self.assertEqual((), result.decisions)
        self.assertEqual("openrouter", result.provider)
        self.assertEqual(OPENROUTER_REVIEW_MODEL, result.model)


if __name__ == "__main__":
    unittest.main()
