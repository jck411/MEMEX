import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

from app.wiki.build_guardrails import validate_synthesis_markdown, validate_wiki_build
from app.wiki.build_packets import build_fact_packet
from app.wiki.build_prompts import (
    WIKI_BUILD_RESPONSE_SCHEMA,
    build_prompt_payload,
    parse_build_response,
)
from app.wiki.builders import (
    FixtureWikiBuildProvider,
    ProviderWikiBuildResult,
)
from app.wiki.markdown import (
    FACTS_END,
    FACTS_START,
    REFERENCES_END,
    REFERENCES_START,
    SYNTHESIS_END,
    SYNTHESIS_START,
)
from app.wiki.openrouter_build import (
    OPENROUTER_WIKI_BUILD_MODEL,
    OpenRouterWikiBuildProvider,
)
from app.wiki.openrouter_client import OPENROUTER_CHAT_COMPLETIONS_URL
from app.wiki.review import ReviewResult, apply_review_results
from tests.helpers import (
    JsonResponse,
    RawResponse,
    fact_record,
    source_record,
    wiki_record,
    wiki_workspace,
)


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
            "Previous uncited synthesis that should not anchor the next build.\n\n"
            "Previous supported prose. "
            "([S1:1](#memex-fact-s1-1)[,2](#memex-fact-s1-2))\n\n"
            "### 国籍与公民身份\n\n"
            "Alice负责平台团队领导工作。 ([S1:2](#memex-fact-s1-2))\n\n"
            "Stale generated prose. ([S9:9](#memex-fact-s9-9))\n"
            f"{SYNTHESIS_END}\n\n"
            f"{FACTS_START}\nold audit appendix\n{FACTS_END}\n\n"
            f"{REFERENCES_START}\n## Wiki Provenance\n\n"
            f"- [Facts used to build this page](career/facts)\n{REFERENCES_END}\n\n"
            "## LLM Context\n\n"
            "### Default Conversation Context\n\n"
            "legacy prompt text\n"
        )

        packet = reviewed_packet(existing)
        payload = build_prompt_payload(packet)

        self.assertEqual("Track durable career history.", payload["wiki"]["description"])
        self.assertEqual(
            [
                {
                    "source_title": "Profile",
                    "facts": [
                        {
                            "text": "Alice joined Example Co.",
                            "review_reason": "Career history.",
                        },
                        {
                            "text": "Alice led the platform team.",
                            "review_reason": "Leadership history.",
                        },
                    ],
                },
            ],
            payload["accepted_fact_sources"],
        )
        self.assertNotIn("citation_contract", payload)
        self.assertNotIn("language_contract", payload)
        self.assertNotIn("output_schema", payload)
        self.assertNotIn("facts", payload)
        fact_payload = payload["accepted_fact_sources"][0]["facts"][0]
        self.assertNotIn("fact_id", fact_payload)
        self.assertNotIn("fact_signature", fact_payload)
        self.assertNotIn("source_key", fact_payload)
        self.assertNotIn("citation", fact_payload)
        context = payload["existing_markdown_context"]["markdown"]
        self.assertNotIn("Previous uncited synthesis", context)
        self.assertNotIn("Previous supported prose.", context)
        self.assertNotIn("国籍", context)
        self.assertNotIn("平台团队", context)
        self.assertNotIn("Stale generated prose.", context)
        self.assertNotIn("old audit appendix", context)
        self.assertNotIn("Facts used to build this page", context)
        self.assertNotIn("Default Conversation Context", context)
        self.assertEqual(
            ("fact-1", "fact-2"),
            tuple(fact.fact_id for fact in packet.accepted_facts),
        )

    def test_build_prompt_groups_facts_by_source(self):
        profile = source_record(
            "source-1",
            fact_record("fact-1", "Alice joined Example Co."),
            fact_record("fact-2", "Alice led the platform team."),
            fact_record("fact-3", "Alice lives in Boston."),
            title="Profile",
        )
        memo = source_record(
            "source-2",
            fact_record("fact-1", "Alice managed the hiring plan."),
            title="Manager memo",
        )
        wiki = synthesis_wiki()
        ledger = _reviewed_ledger(wiki, profile)
        apply_review_results(
            wiki,
            profile.source_id,
            ledger,
            profile,
            [ReviewResult("fact-3", False, "Out of scope.")],
        )
        ledger.assign_source(wiki.wiki_id, memo.source_id)
        apply_review_results(
            wiki,
            memo.source_id,
            ledger,
            memo,
            [ReviewResult("fact-1", True, "Leadership history.")],
        )

        payload = build_prompt_payload(build_fact_packet(wiki, ledger, [profile, memo]))

        self.assertEqual(
            [
                {
                    "source_title": "Profile",
                    "facts": [
                        {
                            "text": "Alice joined Example Co.",
                            "review_reason": "Career history.",
                        },
                        {
                            "text": "Alice led the platform team.",
                            "review_reason": "Leadership history.",
                        },
                    ],
                },
                {
                    "source_title": "Manager memo",
                    "facts": [
                        {
                            "text": "Alice managed the hiring plan.",
                            "review_reason": "Leadership history.",
                        }
                    ],
                },
            ],
            payload["accepted_fact_sources"],
        )
        self.assertNotIn("Alice lives in Boston.", json.dumps(payload))

    def test_guardrails_accept_readable_uncited_synthesis(self):
        packet = reviewed_packet()
        markdown = (
            "## Wiki Brief\n\n"
            "Alice joined Example Co. and led the platform team.\n\n"
            "## Open Questions\n\n"
            "The accepted facts do not supply dates for the role."
        )

        self.assertEqual(markdown, validate_synthesis_markdown(packet, markdown))

    def test_guardrails_allow_synthesis_to_omit_audit_only_details(self):
        packet = reviewed_packet()
        markdown = "## Wiki Brief\n\nAlice joined Example Co."

        self.assertEqual(markdown, validate_synthesis_markdown(packet, markdown))

    def test_guardrails_allow_structural_list_labels(self):
        packet = reviewed_packet()
        markdown = (
            "## Wiki Brief\n\n"
            "- **Roles:**\n"
            "  - Alice joined Example Co.\n"
            "  - Alice led the platform team."
        )

        self.assertEqual(markdown, validate_synthesis_markdown(packet, markdown))

    def test_guardrails_allow_occasional_non_latin_proper_nouns_in_english(self):
        packet = reviewed_packet()
        markdown = "## Wiki Brief\n\nAlice worked with Zhang Wei (张伟)."

        self.assertEqual(markdown, validate_synthesis_markdown(packet, markdown))

    def test_guardrails_reject_cjk_dominant_synthesis(self):
        packet = reviewed_packet()

        with self.assertRaisesRegex(ValueError, "must be English"):
            validate_synthesis_markdown(
                packet,
                "## Wiki Brief\n\nAlice负责平台团队领导工作。",
            )

    def test_guardrails_reject_page_titles(self):
        packet = reviewed_packet()

        with self.assertRaisesRegex(ValueError, "must not include a page title"):
            validate_synthesis_markdown(
                packet,
                "# Career\n\n## Wiki Brief\n\nAlice joined Example Co.",
            )

    def test_guardrails_allow_claims_to_omit_audit_only_facts(self):
        packet = reviewed_packet()
        result = ProviderWikiBuildResult(
            summary="Built one claim.",
            claims=("Alice joined Example Co.",),
            synthesis_markdown="## Wiki Brief\n\nAlice joined Example Co.",
        )

        self.assertEqual(result.synthesis_markdown, validate_wiki_build(packet, result))

    def test_parse_build_response_accepts_plain_claims(self):
        summary, claims, synthesis = parse_build_response(
            {
                "summary": "Built one claim.",
                "claims": [
                    "Alice joined Example Co. and led the platform team.",
                ],
                "synthesis_markdown": (
                    "## Wiki Brief\n\n"
                    "Alice joined Example Co. and led the platform team."
                ),
            }
        )

        self.assertEqual("Built one claim.", summary)
        self.assertEqual(
            ("Alice joined Example Co. and led the platform team.",),
            claims,
        )
        self.assertIn("Alice joined Example Co.", synthesis)

    def test_parse_build_response_rejects_blank_claims(self):
        with self.assertRaisesRegex(ValueError, "claim 1 must be a non-empty string"):
            parse_build_response(
                {
                    "summary": "Built one claim.",
                    "claims": [""],
                    "synthesis_markdown": "## Wiki Brief\n\nAlice joined Example Co.",
                }
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
                                        "claims": [
                                            "Alice joined Example Co. and led "
                                            "the platform team."
                                        ],
                                        "synthesis_markdown": (
                                            "## Wiki Brief\n\n"
                                            "Alice joined Example Co. and led the platform team."
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
        self.assertNotIn("(S1:1)", prompt)
        self.assertEqual("openrouter", result.provider)
        self.assertEqual(OPENROUTER_WIKI_BUILD_MODEL, result.model)
        self.assertEqual(
            ("Alice joined Example Co. and led the platform team.",),
            result.claims,
        )
        self.assertEqual(0.001, result.usage["cost"])

    def test_openrouter_build_surfaces_http_error_body(self):
        packet = reviewed_packet()

        def opener(request, timeout):
            raise HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                BytesIO(
                    json.dumps(
                        {
                            "error": {
                                "code": 400,
                                "message": "No endpoints support required parameters.",
                            }
                        }
                    ).encode("utf-8")
                ),
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "OpenRouter returned HTTP 400: 400; No endpoints support required parameters",
        ):
            OpenRouterWikiBuildProvider(api_key="key", opener=opener).build(packet)

    def test_openrouter_build_surfaces_api_error_payload(self):
        packet = reviewed_packet()

        def opener(request, timeout):
            return JsonResponse(
                {
                    "error": {
                        "code": 402,
                        "message": "Insufficient OpenRouter credits.",
                    }
                }
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "OpenRouter returned an error: 402; Insufficient OpenRouter credits",
        ):
            OpenRouterWikiBuildProvider(api_key="key", opener=opener).build(packet)

    def test_openrouter_build_surfaces_malformed_transport_json(self):
        packet = reviewed_packet()

        def opener(request, timeout):
            return RawResponse(b"not-json")

        with self.assertRaisesRegex(ValueError, "OpenRouter response was not JSON"):
            OpenRouterWikiBuildProvider(api_key="key", opener=opener).build(packet)

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

            with self.assertRaisesRegex(ValueError, "must not include a page title"):
                workspace.build_wiki(
                    "career",
                    FixtureWikiBuildProvider(
                        "# Career\n\n## Wiki Brief\n\nAlice joined Example Co."
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
