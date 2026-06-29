import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.wiki.ledger import WikiLedger
from app.wiki.markdown import (
    FACTS_END,
    FACTS_START,
    REFERENCES_END,
    REFERENCES_START,
    SYNTHESIS_END,
    SYNTHESIS_START,
    build_wiki_markdown,
    remove_fact_audit_section,
    remove_references_section,
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
    fixture_wiki_build_provider,
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

    def test_build_wiki_markdown_creates_clean_page_and_removes_fact_audit_section(self):
        accepted_fact = fact_record(
            "fact-1",
            "Alice joined Example Co.\nShe led platform work.",
            provenance={"evidence_ids": ["ev1"]},
        )
        rejected_fact = fact_record("fact-2", "Alice lives in Boston.")
        wiki = wiki_record(
            "career",
            "Career",
            "career.md",
            description="Track durable career history.",
        )
        source = source_record("source-1", accepted_fact, rejected_fact, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        apply_review_results(
            wiki,
            "source-1",
            ledger,
            source,
            [
                ReviewResult("fact-1", True, "Core career history."),
                ReviewResult("fact-2", False, "Out of scope."),
            ],
        )

        synthesis = "## Wiki Brief\n\nAlice joined Example Co. and led platform work."
        markdown = build_wiki_markdown(wiki, synthesis)
        self.assertIn("# Career", markdown)
        self.assertIn(SYNTHESIS_START, markdown)
        self.assertIn("## Wiki Brief", markdown)
        self.assertIn("led platform work.", markdown)
        self.assertIn(SYNTHESIS_END, markdown)
        self.assertNotIn("## LLM Context", markdown)
        self.assertNotIn("### Default Conversation Context", markdown)
        self.assertNotIn("Source Fact Decisions", markdown)
        self.assertNotIn(FACTS_START, markdown)
        self.assertNotIn(FACTS_END, markdown)
        self.assertNotIn("source-1", markdown)
        self.assertNotIn("fact-1", markdown)
        self.assertNotIn("fact-2", markdown)
        self.assertNotIn("Alice lives in Boston.", markdown)
        self.assertIn(REFERENCES_START, markdown)
        self.assertIn("## References", markdown)
        self.assertIn("- [Facts used](career/facts)", markdown)
        self.assertIn(REFERENCES_END, markdown)

        existing = (
            "# Career\n\n"
            "Human-written intro.\n\n"
            f"{SYNTHESIS_START}\nold synthesis\n{SYNTHESIS_END}\n\n"
            f"{FACTS_START}\nold generated text\n{FACTS_END}\n\n"
            f"{REFERENCES_START}\n## References\n\n- [Facts used](old/facts)\n{REFERENCES_END}\n\n"
            "## LLM Context\n\n"
            "### Default Conversation Context\n\n"
            "legacy context\n\n"
            "Human-written footer.\n"
        )
        updated = build_wiki_markdown(wiki, synthesis, existing)
        self.assertIn("Human-written intro.", updated)
        self.assertNotIn("old synthesis", updated)
        self.assertNotIn("old generated text", updated)
        self.assertNotIn(FACTS_START, updated)
        self.assertNotIn(FACTS_END, updated)
        self.assertNotIn("old/facts", updated)
        self.assertIn("- [Facts used](career/facts)", updated)
        self.assertNotIn("Default Conversation Context", updated)
        self.assertIn("Human-written footer.", updated)

    def test_build_wiki_markdown_omits_source_fact_inventory(self):
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

        markdown = build_wiki_markdown(
            CAREER_WIKI,
            "## Wiki Brief\n\nAccepted identity and career facts are available.",
        )

        self.assertNotIn("Default Conversation Context", markdown)
        self.assertNotIn("Source Fact Decisions", markdown)
        self.assertNotIn("Alice is a licensed pharmacist.", markdown)
        self.assertNotIn("Passport number: 123456789", markdown)
        self.assertNotIn("resume", markdown)
        self.assertNotIn("passport", markdown)
        self.assertNotIn("f1", markdown)
        self.assertNotIn("f2", markdown)
        self.assertIn("- [Facts used](career/facts)", markdown)

    def test_incomplete_memex_fact_audit_markers_are_rejected(self):
        cases = (
            f"# Career\n\n{FACTS_START}\nold generated text\n",
            f"# Career\n\nold generated text\n{FACTS_END}\n",
            f"# Career\n\n{FACTS_END}\nold generated text\n{FACTS_START}\n",
        )

        for existing in cases:
            with self.subTest(existing=existing):
                with self.assertRaisesRegex(ValueError, "incomplete MEMEX facts markers"):
                    remove_fact_audit_section(existing)

    def test_incomplete_memex_references_markers_are_rejected(self):
        cases = (
            f"# Career\n\n{REFERENCES_START}\nold generated text\n",
            f"# Career\n\nold generated text\n{REFERENCES_END}\n",
            f"# Career\n\n{REFERENCES_END}\nold generated text\n{REFERENCES_START}\n",
        )

        for existing in cases:
            with self.subTest(existing=existing):
                with self.assertRaisesRegex(ValueError, "incomplete MEMEX references markers"):
                    remove_references_section(existing)

    def test_vault_helpers_write_inside_vault_root(self):
        wiki = wiki_record("career", "Career", "nested/career.md")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_wiki_page(temp_dir, wiki, "# Career\n")

            self.assertEqual(Path(temp_dir) / "nested" / "career.md", path)
            self.assertEqual("# Career\n", read_wiki_page(temp_dir, wiki))

        unsafe = wiki_record("escape", "Escape", "../escape.md")
        with self.assertRaises(ValueError):
            wiki_page_path("/tmp/vault", unsafe)

    def test_vault_write_failure_preserves_existing_page(self):
        wiki = wiki_record("career", "Career", "nested/career.md")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_wiki_page(temp_dir, wiki, "# Career\n\nOld page.\n")

            with patch.object(Path, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    write_wiki_page(temp_dir, wiki, "# Career\n\nNew page.\n")

            self.assertEqual("# Career\n\nOld page.\n", path.read_text(encoding="utf-8"))
            self.assertEqual((), tuple(path.parent.glob(f".{path.name}.*.tmp")))

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
            markdown = build_wiki_markdown(
                wiki,
                "## Wiki Brief\n\nAlice joined Example Co.",
            )
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
                workspace.build_wiki("career", fixture_wiki_build_provider())

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
