"""Derived wiki review/build status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .fingerprints import stable_digest
from .ledger import ReviewDecision, WikiLedger
from .records import FactRecord, SourceRecord, WikiRecord, WikiRegistry, source_index
from .review import review_delta_for_wiki
from .sort_keys import natural_key
from .wiki_scope import wiki_scope_signature

BUILD_FINGERPRINT_VERSION = 7


@dataclass(frozen=True)
class AcceptedFact:
    source_id: str
    fact_id: str
    fact_signature: str
    text: str
    decision: ReviewDecision


@dataclass(frozen=True)
class WikiStatus:
    wiki_id: str
    build_fingerprint: str
    build_baseline: str
    needs_review: bool
    needs_build: bool

    @property
    def current(self) -> bool:
        return not self.needs_review and not self.needs_build


def _build_payload(
    wiki: WikiRecord,
    accepted_facts: tuple[AcceptedFact, ...],
) -> dict[str, object]:
    return {
        "version": BUILD_FINGERPRINT_VERSION,
        "kind": "build",
        "wiki_id": wiki.wiki_id,
        "wiki_scope_signature": wiki_scope_signature(wiki),
        "accepted_facts": [
            {
                "source_id": fact.source_id,
                "fact_id": fact.fact_id,
                "fact_signature": fact.fact_signature,
            }
            for fact in accepted_facts
        ],
    }


def _empty_build_fingerprint(wiki: WikiRecord) -> str:
    return stable_digest(_build_payload(wiki, ()))


def accepted_facts_for_wiki(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> tuple[AcceptedFact, ...]:
    source_map = source_index(sources)
    accepted: list[AcceptedFact] = []
    wiki_id = wiki.wiki_id
    current_scope = wiki_scope_signature(wiki)
    for source_id in ledger.assigned_sources(wiki_id):
        source = source_map.get(source_id)
        if source is None:
            continue
        facts_by_id: dict[str, FactRecord] = source.fact_by_id()
        for fact_id in sorted(facts_by_id, key=natural_key):
            fact = facts_by_id[fact_id]
            decision = ledger.decision_for(wiki_id, source_id, fact_id)
            if decision is None or not decision.ticked:
                continue
            fact_signature = fact.signature()
            if (
                decision.fact_signature != fact_signature
                or decision.wiki_scope_signature != current_scope
            ):
                continue
            accepted.append(
                AcceptedFact(
                    source_id=source_id,
                    fact_id=fact_id,
                    fact_signature=fact_signature,
                    text=fact.text,
                    decision=decision,
                )
            )
    return tuple(accepted)


def build_fingerprint(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> str:
    return stable_digest(_build_payload(wiki, accepted_facts_for_wiki(wiki, ledger, sources)))


def status_for_wiki(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> WikiStatus:
    source_map = source_index(sources)
    build_current = stable_digest(
        _build_payload(wiki, accepted_facts_for_wiki(wiki, ledger, source_map))
    )
    wiki_id = wiki.wiki_id
    build_baseline = ledger.build_baselines.get(wiki_id, _empty_build_fingerprint(wiki))
    return WikiStatus(
        wiki_id=wiki_id,
        build_fingerprint=build_current,
        build_baseline=build_baseline,
        needs_review=bool(review_delta_for_wiki(wiki, ledger, source_map)),
        needs_build=build_current != build_baseline,
    )


def statuses_for_registry(
    registry: WikiRegistry,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> dict[str, WikiStatus]:
    source_map = source_index(sources)
    return {
        wiki_id: status_for_wiki(registry.wikis[wiki_id], ledger, source_map)
        for wiki_id in registry.active_ids()
    }


def mark_build_current(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> str:
    fingerprint = build_fingerprint(wiki, ledger, sources)
    ledger.set_build_baseline(wiki.wiki_id, fingerprint)
    return fingerprint
