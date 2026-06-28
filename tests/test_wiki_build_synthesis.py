import json
import tempfile
import unittest
from pathlib import Path

from app.wiki.build_guardrails import validate_synthesis_markdown
from app.wiki.build_packets import build_fact_packet
from app.wiki.build_prompts import WIKI_BUILD_RESPONSE_SCHEMA, build_prompt_payload
from app.wiki.builders import FixtureWikiBuildProvider
from app.wiki.markdown import FACTS_END, FACTS_START, SYNTHESIS_END, SYNTHESIS_START
from app.wiki.openrouter_build import (
    OPENROUTER_WIKI_BUILD_MODEL,
    OpenRouterWikiBuildProvider,
)
from app.wiki.openrouter_client import OPENROUTER_CHAT_COMPLETIONS_URL
from app.wiki.review import ReviewResult, apply_review_results
from tests.helpers import JsonResponse, fact_record, source_record, wiki_record, wiki_workspace


def synthesis_wiki():
    return wiki_record(
        "career",
        "Career",
        "career.md",
        description="Track durable career history.",
    )


def reviewed_packet(existing_markdown: str = ""):
    first = fact_record(
        "fact-1",
        "Alice joined Example Co.",
        provenance={"evidence_ids": ["ev1"]},
    )
    second = fact_record(
        "fact-2",
        "Alice led the platform team.",
        provenance={"evidence_ids": ["ev2"]},
    )
    source = source_record("source-1", first, second, title="Profile")
    wiki = synthesis_wiki()
    ledger = _reviewed_ledger(wiki, source)
    return build_fact_packet(wiki, ledger, [source], existing_markdown)


class WikiBuildSynthesisTests(unittest.TestCase):
    def test_build_packet_contains_only_current_accepted_facts_and_context(self):
        existing = (
            "# Career\n\n"
            f"{SYNTHESIS_START}\n"
            "## Wiki Brief\n\n"
            "Previous supported prose. (S1:ev1,fact-1)\n\n"
            "Stale generated prose. (S9:ev9,fact-9)\n"
            f"{SYNTHESIS_END}\n\n"
            f"{FACTS_START}\nold audit appendix\n{FACTS_END}\n\n"
            "## LLM Context\n\n"
            "### Default Conversation Context\n\n"
            "legacy prompt text\n"
        )

        packet = reviewed_packet(existing)
        payload = build_prompt_payload(packet)

        self.assertEqual("Track durable career history.", payload["wiki"]["description"])
        self.assertEqual(
            ["(S1:ev1,fact-1)", "(S1:ev2,fact-2)"],
            payload["citation_contract"]["allowed_citations"],
        )
        context = payload["existing_markdown_context"]["markdown"]
        self.assertIn("Previous supported prose.", context)
        self.assertNotIn("Stale generated prose.", context)
        self.assertNotIn("old audit appendix", context)
        self.assertNotIn("Default Conversation Context", context)
        self.assertEqual(("fact-1", "fact-2"), tuple(fact.fact_id for fact in packet.accepted_facts))

    def test_guardrails_accept_synthesis_that_cites_each_fact(self):
        packet = reviewed_packet()
        markdown = (
            "## Wiki Brief\n\n"
            "Alice joined Example Co. and led the platform team. "
            "(S1:ev1,fact-1) (S1:ev2,fact-2)\n\n"
            "## Open Questions\n\n"
            "The accepted facts do not supply dates for the role. (S1:ev1,fact-1)"
        )

        self.assertEqual(markdown, validate_synthesis_markdown(packet, markdown))

    def test_guardrails_allow_structural_list_labels_with_cited_claims(self):
        packet = reviewed_packet()
        markdown = (
            "## Wiki Brief\n\n"
            "- **Roles:**\n"
            "  - Alice joined Example Co. (S1:ev1,fact-1)\n"
            "  - Alice led the platform team. (S1:ev2,fact-2)"
        )

        self.assertEqual(markdown, validate_synthesis_markdown(packet, markdown))

    def test_guardrails_reject_unknown_or_missing_citations(self):
        packet = reviewed_packet()

        with self.assertRaisesRegex(ValueError, "unknown facts"):
            validate_synthesis_markdown(
                packet,
                "## Wiki Brief\n\nAlice joined Example Co. (S1:ev9,fact-9)",
            )

        with self.assertRaisesRegex(ValueError, "omitted accepted fact citations"):
            validate_synthesis_markdown(
                packet,
                "## Wiki Brief\n\nAlice joined Example Co. (S1:ev1,fact-1)",
            )

    def test_guardrails_reject_uncited_substantive_text(self):
        packet = reviewed_packet()

        with self.assertRaisesRegex(ValueError, "uncited substantive text"):
            validate_synthesis_markdown(
                packet,
                (
                    "## Wiki Brief\n\n"
                    "Alice joined Example Co. (S1:ev1,fact-1) (S1:ev2,fact-2)\n\n"
                    "She was an important leader."
                ),
            )

    def test_openrouter_build_requests_strict_json_synthesis(self):
        packet = reviewed_packet()
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
                                        "summary": "Built concise synthesis.",
                                        "synthesis_markdown": (
                                            "## Wiki Brief\n\n"
                                            "Alice joined Example Co. and led the platform team. "
                                            "(S1:ev1,fact-1) (S1:ev2,fact-2)"
                                        ),
                                    }
                                )
                            },
                        }
                    ],
                    "usage": {"total_tokens": 200, "cost": 0.001},
                }
            )

        result = OpenRouterWikiBuildProvider(api_key="key", opener=opener).build(packet)

        self.assertEqual(OPENROUTER_CHAT_COMPLETIONS_URL, seen["url"])
        self.assertEqual(180, seen["timeout"])
        self.assertEqual("Bearer key", seen["headers"]["Authorization"])
        self.assertEqual(OPENROUTER_WIKI_BUILD_MODEL, seen["body"]["model"])
        self.assertEqual({"require_parameters": True}, seen["body"]["provider"])
        self.assertEqual(
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "memex_wiki_build",
                    "strict": True,
                    "schema": WIKI_BUILD_RESPONSE_SCHEMA,
                },
            },
            seen["body"]["response_format"],
        )
        prompt = seen["body"]["messages"][1]["content"]
        self.assertIn("Track durable career history", prompt)
        self.assertIn("(S1:ev1,fact-1)", prompt)
        self.assertEqual("openrouter", result.provider)
        self.assertEqual(OPENROUTER_WIKI_BUILD_MODEL, result.model)
        self.assertEqual(0.001, result.usage["cost"])

    def test_failed_synthesis_guardrail_does_not_update_baseline(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        source = source_record("source-1", fact, title="Profile")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root, synthesis_wiki())
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-1", True, "Career history.")],
            )
            before = workspace.status("career")

            with self.assertRaisesRegex(ValueError, "uncited substantive text"):
                workspace.build_wiki(
                    "career",
                    FixtureWikiBuildProvider(
                        "## Wiki Brief\n\nAlice joined Example Co. (S1:fact-1)\n\nUncited claim."
                    ),
                )

            after = workspace.status("career")
            self.assertEqual(before.build_baseline, after.build_baseline)
            self.assertTrue(after.needs_build)
            self.assertNotIn("career", workspace.data_store.load_ledger().build_baselines)
            self.assertFalse((root / "vault" / "career.md").exists())


def _reviewed_ledger(wiki, source):
    from app.wiki.ledger import WikiLedger

    ledger = WikiLedger.empty()
    ledger.assign_source(wiki.wiki_id, source.source_id)
    apply_review_results(
        wiki,
        source.source_id,
        ledger,
        source,
        [
            ReviewResult("fact-1", True, "Career history."),
            ReviewResult("fact-2", True, "Leadership history."),
        ],
    )
    return ledger


if __name__ == "__main__":
    unittest.main()
