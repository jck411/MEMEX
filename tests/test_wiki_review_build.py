import tempfile
import unittest
from pathlib import Path

from app.wiki.ledger import WikiLedger
from app.wiki.markdown import (
    FACTS_END,
    FACTS_START,
    build_wiki_markdown,
    replace_reviewed_facts_section,
)
from app.wiki.review import (
    ReviewResult,
    apply_review_results,
    review_delta_for_source,
    review_delta_for_wiki,
)
from app.wiki.status import mark_build_current, status_for_wiki
from app.wiki.vault import read_wiki_page, wiki_page_path, write_wiki_page
from tests.helpers import (
    CAREER_WIKI,
    fact_record,
    review_decision_for_fact,
    source_record,
    wiki_record,
    wiki_workspace,
)


class WikiReviewBuildTests(unittest.TestCase):
    def test_new_assignment_review_delta_includes_all_current_facts(self):
        first = fact_record("fact-1", "Alice joined Example Co.")
        second = fact_record("fact-2", "Alice led the platform team.")
        source = source_record("source-1", first, second, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")

        pending = review_delta_for_source(CAREER_WIKI, "source-1", ledger, [source])

        self.assertEqual(("fact-1", "fact-2"), tuple(fact.fact_id for fact in pending))
        self.assertEqual(first.signature(), pending[0].fact_signature)

    def test_review_results_store_reasons_and_make_build_pending(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        source = source_record("source-1", fact, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")

        count = apply_review_results(
            CAREER_WIKI,
            "source-1",
            ledger,
            source,
            [
                ReviewResult(
                    fact_id="fact-1",
                    ticked=True,
                    reason="Employment history belongs in career.",
                )
            ],
            reviewed_at="2026-06-22T12:00:00Z",
        )

        decision = ledger.decision_for("career", "source-1", "fact-1")
        status = status_for_wiki(CAREER_WIKI, ledger, [source])
        self.assertEqual(1, count)
        self.assertEqual("Employment history belongs in career.", decision.reason)
        self.assertEqual("2026-06-22T12:00:00Z", decision.reviewed_at)
        self.assertFalse(status.needs_review)
        self.assertTrue(status.needs_build)

    def test_review_delta_selects_only_changed_or_new_facts(self):
        original_first = fact_record("fact-1", "Alice joined Example Co.")
        original_second = fact_record("fact-2", "Alice lives in Boston.")
        source = source_record("source-1", original_first, original_second, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            CAREER_WIKI,
            "source-1",
            ledger,
            source,
            [
                ReviewResult("fact-1", True, "Career fact."),
                ReviewResult("fact-2", False, "Personal location is out of scope."),
            ],
        )

        edited_source = source_record(
            "source-1",
            original_first,
            fact_record("fact-2", "Alice lives in Denver."),
            fact_record("fact-3", "Alice presented at PyCon."),
            title="Source One",
        )
        pending = review_delta_for_wiki(CAREER_WIKI, ledger, [edited_source])

        self.assertEqual(("fact-2", "fact-3"), tuple(fact.fact_id for fact in pending))

    def test_matching_unticked_decision_is_not_review_pending(self):
        fact = fact_record("fact-1", "Alice lives in Boston.")
        source = source_record("source-1", fact, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(fact),
        )

        self.assertEqual((), review_delta_for_wiki(CAREER_WIKI, ledger, [source]))

    def test_build_wiki_markdown_creates_and_replaces_generated_section(self):
        fact = fact_record(
            "fact-1",
            "Alice joined Example Co.\nShe led platform work.",
            provenance={"evidence_ids": ["ev1"]},
        )
        wiki = wiki_record(
            "career",
            "Career",
            "career.md",
            description="Track durable career history.",
        )
        source = source_record("source-1", fact, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            wiki,
            "source-1",
            ledger,
            source,
            [ReviewResult("fact-1", True, "Core career history.")],
        )

        markdown = build_wiki_markdown(wiki, ledger, [source])
        self.assertIn("# Career", markdown)
        self.assertIn("## LLM Context", markdown)
        self.assertIn("### Default Conversation Context", markdown)
        self.assertIn("Wiki description:** Track durable career history.", markdown)
        self.assertIn("## Accepted Facts", markdown)
        self.assertIn(FACTS_START, markdown)
        self.assertIn(
            "- Alice joined Example Co. She led platform work. (S1:ev1,fact-1)",
            markdown,
        )
        self.assertIn("Review: Core career history.", markdown)
        self.assertIn("## References", markdown)
        self.assertIn("### S1. Source One (`source-1`)", markdown)
        self.assertIn(
            "- (S1:ev1,fact-1) fact `fact-1` ; evidence `ev1`: "
            "Alice joined Example Co. She led platform work.",
            markdown,
        )

        existing = (
            "# Career\n\n"
            "Human-written intro.\n\n"
            f"{FACTS_START}\nold generated text\n{FACTS_END}\n\n"
            "Human-written footer.\n"
        )
        updated = build_wiki_markdown(wiki, ledger, [source], existing)
        self.assertIn("Human-written intro.", updated)
        self.assertNotIn("old generated text", updated)
        self.assertIn("Human-written footer.", updated)

    def test_restricted_accepted_facts_render_below_default_accepted_facts(self):
        public_fact = fact_record("f1", "Alice is a licensed pharmacist.")
        restricted_fact = fact_record("f2", "Passport number: 123456789")
        resume = source_record("resume", public_fact, title="Resume")
        passport = source_record("passport", restricted_fact, title="United States Passport")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "resume")
        ledger.assign_source("career", "passport")
        apply_review_results(
            CAREER_WIKI,
            "resume",
            ledger,
            resume,
            [ReviewResult("f1", True, "Professional identity.")],
        )
        apply_review_results(
            CAREER_WIKI,
            "passport",
            ledger,
            passport,
            [ReviewResult("f2", True, "Identity document detail.")],
        )

        markdown = build_wiki_markdown(CAREER_WIKI, ledger, [resume, passport])
        context = markdown.split("## Accepted Facts", 1)[0]
        accepted_facts = markdown.split("## Accepted Facts", 1)[1]

        self.assertIn("Alice is a licensed pharmacist.", context)
        self.assertNotIn("Passport number: 123456789", context)
        self.assertIn("1 restricted accepted fact(s) are listed below", context)
        self.assertIn("### Default Accepted Facts", accepted_facts)
        self.assertIn("### Restricted Accepted Facts", accepted_facts)
        self.assertIn("Passport number: 123456789", accepted_facts)
        self.assertLess(
            accepted_facts.find("Alice is a licensed pharmacist."),
            accepted_facts.find("Passport number: 123456789"),
        )

    def test_incomplete_memex_markers_are_rejected(self):
        replacement = f"{FACTS_START}\nnew generated text\n{FACTS_END}"
        cases = (
            f"# Career\n\n{FACTS_START}\nold generated text\n",
            f"# Career\n\nold generated text\n{FACTS_END}\n",
            f"# Career\n\n{FACTS_END}\nold generated text\n{FACTS_START}\n",
        )

        for existing in cases:
            with self.subTest(existing=existing):
                with self.assertRaisesRegex(ValueError, "incomplete MEMEX facts markers"):
                    replace_reviewed_facts_section(existing, replacement)

    def test_vault_helpers_write_inside_vault_root(self):
        wiki = wiki_record("career", "Career", "nested/career.md")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_wiki_page(temp_dir, wiki, "# Career\n")

            self.assertEqual(Path(temp_dir) / "nested" / "career.md", path)
            self.assertEqual("# Career\n", read_wiki_page(temp_dir, wiki))

        unsafe = wiki_record("escape", "Escape", "../escape.md")
        with self.assertRaises(ValueError):
            wiki_page_path("/tmp/vault", unsafe)

    def test_build_baseline_updates_after_successful_page_write(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        wiki = CAREER_WIKI
        source = source_record("source-1", fact, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            wiki,
            "source-1",
            ledger,
            source,
            [ReviewResult("fact-1", True, "Career fact.")],
        )
        self.assertTrue(status_for_wiki(wiki, ledger, [source]).needs_build)

        with tempfile.TemporaryDirectory() as temp_dir:
            markdown = build_wiki_markdown(wiki, ledger, [source])
            write_wiki_page(temp_dir, wiki, markdown)
            mark_build_current(wiki, ledger, [source])

            self.assertTrue(status_for_wiki(wiki, ledger, [source]).current)

    def test_failed_workspace_build_does_not_update_build_baseline(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        source = source_record("source-1", fact, title="Source One")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = wiki_workspace(root, CAREER_WIKI)
            workspace.save_source(source)
            workspace.assign_source("career", "source-1")
            workspace.review_source(
                "career",
                "source-1",
                [ReviewResult("fact-1", True, "Career fact.")],
            )
            before = workspace.status("career")
            page_path = root / "vault" / "career.md"
            page_path.parent.mkdir(parents=True)
            page_path.write_text(
                f"# Career\n\n{FACTS_START}\npartial generated section\n",
                encoding="utf-8",
            )

            self.assertTrue(before.needs_build)
            with self.assertRaisesRegex(ValueError, "incomplete MEMEX facts markers"):
                workspace.build_wiki("career")

            after = workspace.status("career")
            self.assertEqual(before.build_baseline, after.build_baseline)
            self.assertEqual(before.build_fingerprint, after.build_fingerprint)
            self.assertTrue(after.needs_build)
            self.assertNotIn("career", workspace.data_store.load_ledger().build_baselines)
            self.assertEqual(
                f"# Career\n\n{FACTS_START}\npartial generated section\n",
                page_path.read_text(encoding="utf-8"),
            )

    def test_description_change_makes_review_and_build_stale(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        source = source_record("source-1", fact, title="Source One")
        old_wiki = wiki_record(
            "career",
            "Career",
            "career.md",
            description="Track employment history.",
        )
        new_wiki = wiki_record(
            "career",
            "Career",
            "career.md",
            description="Track only public speaking history.",
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            old_wiki,
            "source-1",
            ledger,
            source,
            [ReviewResult("fact-1", True, "Employment belongs here.")],
        )
        mark_build_current(old_wiki, ledger, [source])

        status = status_for_wiki(new_wiki, ledger, [source])

        self.assertTrue(status.needs_review)
        self.assertTrue(status.needs_build)
        self.assertEqual(
            ("fact-1",),
            tuple(
                fact.fact_id for fact in review_delta_for_wiki(new_wiki, ledger, [source])
            ),
        )


if __name__ == "__main__":
    unittest.main()
