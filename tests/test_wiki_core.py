import unittest

from app.wiki.ledger import ReviewDecision, WikiLedger
from app.wiki.records import SourceRecord, WikiRegistry
from app.wiki.review import review_delta_for_wiki
from app.wiki.status import (
    accepted_facts_for_wiki,
    mark_build_current,
    status_for_wiki,
    statuses_for_registry,
)
from tests.helpers import (
    CAREER_WIKI,
    fact_record,
    review_decision_for_fact,
    source_record,
    wiki_registry,
)


class WikiCoreTests(unittest.TestCase):
    def test_review_delta_tracks_assignments_and_current_fact_signatures(self):
        first = fact_record("fact-1", "Alice joined Example Co.")
        second = fact_record("fact-2", "Alice lives in Boston.")
        sources = [
            source_record("source-1", second, first, title="Source One"),
            source_record("source-2", fact_record("fact-3", "A second source fact.")),
        ]

        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-2")
        ledger.assign_source("career", "source-1")
        for source in sources:
            for fact in source.facts:
                ledger.set_decision(
                    "career",
                    source.source_id,
                    fact.fact_id,
                    review_decision_for_fact(fact),
                )

        self.assertEqual((), review_delta_for_wiki(CAREER_WIKI, ledger, list(reversed(sources))))

        changed_sources = [
            source_record(
                "source-1",
                first,
                fact_record("fact-2", "Alice lives in Denver."),
                title="Source One",
            ),
            sources[1],
        ]
        self.assertEqual(
            (("source-1", "fact-2"),),
            tuple(
                (fact.source_id, fact.fact_id)
                for fact in review_delta_for_wiki(CAREER_WIKI, ledger, changed_sources)
            ),
        )

    def test_status_moves_from_review_to_build_and_back_to_current(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        sources = [source_record("source-1", fact, title="Source One")]
        ledger = WikiLedger.empty()

        self.assertTrue(status_for_wiki(CAREER_WIKI, ledger, sources).current)

        ledger.assign_source("career", "source-1")
        assigned_status = status_for_wiki(CAREER_WIKI, ledger, sources)
        self.assertTrue(assigned_status.needs_review)
        self.assertFalse(assigned_status.needs_build)

        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(fact),
        )
        reviewed_status = status_for_wiki(CAREER_WIKI, ledger, sources)
        self.assertFalse(reviewed_status.needs_review)
        self.assertFalse(reviewed_status.needs_build)

        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(
                fact,
                ticked=True,
                reason="Career-relevant employment fact.",
                reviewed_at="2026-06-22T12:00:00Z",
            ),
        )
        accepted_status = status_for_wiki(CAREER_WIKI, ledger, sources)
        self.assertFalse(accepted_status.needs_review)
        self.assertTrue(accepted_status.needs_build)

        mark_build_current(CAREER_WIKI, ledger, sources)
        self.assertTrue(status_for_wiki(CAREER_WIKI, ledger, sources).current)

        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(fact),
        )
        self.assertTrue(status_for_wiki(CAREER_WIKI, ledger, sources).needs_build)

        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(fact, ticked=True),
        )
        self.assertTrue(status_for_wiki(CAREER_WIKI, ledger, sources).current)

    def test_build_fingerprint_filters_unassigned_and_stale_decisions(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        sources = [source_record("source-1", fact, title="Source One")]
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(fact, ticked=True),
        )
        mark_build_current(CAREER_WIKI, ledger, sources)
        self.assertEqual(1, len(accepted_facts_for_wiki(CAREER_WIKI, ledger, sources)))

        ledger.unassign_source("career", "source-1")
        self.assertEqual((), accepted_facts_for_wiki(CAREER_WIKI, ledger, sources))
        self.assertTrue(status_for_wiki(CAREER_WIKI, ledger, sources).needs_build)

        ledger.assign_source("career", "source-1")
        self.assertTrue(status_for_wiki(CAREER_WIKI, ledger, sources).current)

        changed_sources = [source_record("source-1", fact_record("fact-1", "Alice left Example Co."))]
        stale_status = status_for_wiki(CAREER_WIKI, ledger, changed_sources)
        self.assertTrue(stale_status.needs_review)
        self.assertTrue(stale_status.needs_build)
        self.assertEqual((), accepted_facts_for_wiki(CAREER_WIKI, ledger, changed_sources))

    def test_accepted_facts_use_natural_fact_order(self):
        fact_10 = fact_record("fact-10", "Alice mentored ten teams.")
        fact_2 = fact_record("fact-2", "Alice led platform work.")
        source = source_record("source-1", fact_10, fact_2, title="Source One")
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        ledger.set_decision(
            "career",
            "source-1",
            "fact-10",
            review_decision_for_fact(fact_10, ticked=True),
        )
        ledger.set_decision(
            "career",
            "source-1",
            "fact-2",
            review_decision_for_fact(fact_2, ticked=True),
        )

        accepted = accepted_facts_for_wiki(CAREER_WIKI, ledger, [source])

        self.assertEqual(("fact-2", "fact-10"), tuple(fact.fact_id for fact in accepted))

    def test_registry_status_ignores_orphaned_ledger_keys(self):
        registry = wiki_registry(CAREER_WIKI)
        ledger = WikiLedger.empty()
        ledger.assign_source("orphaned", "source-1")
        statuses = statuses_for_registry(registry, ledger, [])

        self.assertEqual(("career",), tuple(statuses))
        self.assertTrue(statuses["career"].current)

    def test_remove_wiki_prunes_owned_ledger_state(self):
        fact = fact_record("fact-1", "Alice joined Example Co.")
        ledger = WikiLedger.empty()
        decision = ReviewDecision(
            ticked=True,
            fact_signature=fact.signature(),
            wiki_scope_signature="scope",
        )
        ledger.assign_source("career", "source-1")
        ledger.assign_source("projects", "source-1")
        ledger.set_decision("career", "source-1", "fact-1", decision)
        ledger.set_decision("projects", "source-1", "fact-1", decision)
        ledger.set_build_baseline("career", "career-fingerprint")
        ledger.set_build_baseline("projects", "projects-fingerprint")

        ledger.remove_wiki("career")

        self.assertEqual((), ledger.assigned_sources("career"))
        self.assertIsNone(ledger.decision_for("career", "source-1", "fact-1"))
        self.assertNotIn("career", ledger.build_baselines)
        self.assertEqual(("source-1",), ledger.assigned_sources("projects"))
        self.assertIsNotNone(ledger.decision_for("projects", "source-1", "fact-1"))
        self.assertEqual("projects-fingerprint", ledger.build_baselines["projects"])

    def test_records_and_ledger_round_trip_through_primitive_dicts(self):
        registry = wiki_registry(CAREER_WIKI)
        source = source_record(
            "source-1",
            fact_record(
                "fact-1",
                "Alice joined Example Co.",
                provenance={"page": 2, "quote": "joined Example Co."},
            ),
            title="Profile",
        )
        ledger = WikiLedger.empty()
        ledger.assign_source("career", "source-1")
        ledger.set_decision(
            "career",
            "source-1",
            "fact-1",
            review_decision_for_fact(
                source.facts[0],
                ticked=True,
                reason="Relevant.",
                reviewed_at="2026-06-22T12:00:00Z",
            ),
        )
        mark_build_current(CAREER_WIKI, ledger, [source])

        self.assertEqual(registry, WikiRegistry.from_dict(registry.to_dict()))
        self.assertEqual(source, SourceRecord.from_dict(source.to_dict()))
        self.assertEqual(ledger.to_dict(), WikiLedger.from_dict(ledger.to_dict()).to_dict())


if __name__ == "__main__":
    unittest.main()
