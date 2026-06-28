"""Review delta selection and review result application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .ledger import ReviewDecision, WikiLedger
from .records import SourceRecord, WikiRecord, source_index
from .wiki_scope import wiki_scope_signature


@dataclass(frozen=True)
class ReviewFact:
    wiki_id: str
    source_id: str
    source_title: str
    fact_id: str
    fact_signature: str
    text: str


@dataclass(frozen=True)
class ReviewResult:
    fact_id: str
    ticked: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, str) or not self.fact_id.strip():
            raise ValueError("fact_id must be a non-empty string")
        if not isinstance(self.ticked, bool):
            raise ValueError("ticked must be a bool")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")


@dataclass(frozen=True)
class WikiReviewContext:
    wiki_id: str
    wiki_title: str
    wiki_intention: str
    source_id: str
    source_title: str
    source_summary: str = ""


def review_delta_for_source(
    wiki: WikiRecord,
    source_id: str,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> tuple[ReviewFact, ...]:
    """Return current facts that need an LLM relevance decision."""

    pending: list[ReviewFact] = []
    current_scope = wiki_scope_signature(wiki)
    wiki_id = wiki.wiki_id
    for fact in review_facts_for_source(wiki, source_id, ledger, sources):
        decision = ledger.decision_for(wiki_id, source_id, fact.fact_id)
        if decision is not None and _decision_current(
            decision,
            fact.fact_signature,
            current_scope,
        ):
            continue
        pending.append(fact)
    return tuple(pending)


def review_facts_for_source(
    wiki: WikiRecord,
    source_id: str,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> tuple[ReviewFact, ...]:
    """Return all current facts from an assigned source for provider review."""

    wiki_id = wiki.wiki_id
    if source_id not in ledger.assigned_sources(wiki_id):
        return ()
    source = source_index(sources).get(source_id)
    if source is None:
        return ()

    review_facts: list[ReviewFact] = []
    for fact in sorted(source.facts, key=lambda item: item.fact_id):
        fact_signature = fact.signature()
        review_facts.append(
            ReviewFact(
                wiki_id=wiki_id,
                source_id=source_id,
                source_title=source.title,
                fact_id=fact.fact_id,
                fact_signature=fact_signature,
                text=fact.text,
            )
        )
    return tuple(review_facts)


def review_delta_for_wiki(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> tuple[ReviewFact, ...]:
    """Return all assigned current facts whose decisions are missing or stale."""

    source_map = source_index(sources)
    pending: list[ReviewFact] = []
    wiki_id = wiki.wiki_id
    for source_id in ledger.assigned_sources(wiki_id):
        pending.extend(review_delta_for_source(wiki, source_id, ledger, source_map))
    return tuple(pending)


def apply_review_results(
    wiki: WikiRecord,
    source_id: str,
    ledger: WikiLedger,
    source: SourceRecord,
    results: Iterable[ReviewResult],
    reviewed_at: str = "",
) -> int:
    """Store review decisions for current facts from one source."""

    wiki_id = wiki.wiki_id
    if source.source_id != source_id:
        raise ValueError("source_id does not match source record")
    if source_id not in ledger.assigned_sources(wiki_id):
        raise ValueError(f"source {source_id!r} is not assigned to wiki {wiki_id!r}")

    facts = source.fact_by_id()
    current_scope = wiki_scope_signature(wiki)
    count = 0
    for result in results:
        fact = facts.get(result.fact_id)
        if fact is None:
            raise ValueError(f"unknown fact_id {result.fact_id!r} for source {source_id!r}")
        ledger.set_decision(
            wiki_id,
            source_id,
            result.fact_id,
            ReviewDecision(
                ticked=result.ticked,
                fact_signature=fact.signature(),
                wiki_scope_signature=current_scope,
                reason=result.reason,
                reviewed_at=reviewed_at,
            ),
        )
        count += 1
    return count


def _decision_current(
    decision: ReviewDecision,
    fact_signature: str,
    wiki_scope: str,
) -> bool:
    return decision.fact_signature == fact_signature and decision.wiki_scope_signature == wiki_scope
