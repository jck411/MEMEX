"""Workspace review orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .ledger import WikiLedger
from .records import SourceRecord, WikiRecord
from .review import (
    ReviewFact,
    ReviewResult,
    WikiReviewContext,
    apply_review_results,
    review_delta_for_source,
    review_delta_for_wiki,
    review_facts_for_source,
)
from .review_prompts import validate_review_results
from .reviewers import ReviewProvider
from .status import WikiStatus, status_for_wiki
from .storage import WikiDataStore
from .timestamps import utc_now
from .wiki_scope import wiki_intention_text


@dataclass(frozen=True)
class ReviewWorkflowResult:
    applied_count: int
    remaining_review_count: int
    status: WikiStatus
    provider: str = ""
    model: str = ""
    usage: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "usage", dict(self.usage or {}))


class WorkspaceReviewMixin:
    data_store: WikiDataStore

    def review_delta(self, wiki_id: str) -> tuple[ReviewFact, ...]:
        wiki = self._load_wiki(wiki_id)
        return review_delta_for_wiki(
            wiki,
            self.data_store.load_ledger(),
            self.data_store.load_sources(),
        )

    def review_source(
        self,
        wiki_id: str,
        source_id: str,
        results: Iterable[ReviewResult],
        reviewed_at: str = "",
    ) -> ReviewWorkflowResult:
        wiki = self._load_wiki(wiki_id)
        source = self.data_store.load_source(source_id)
        sources = self.data_store.load_sources()
        ledger = self.data_store.load_ledger()
        applied_count = apply_review_results(
            wiki,
            source_id,
            ledger,
            source,
            results,
            reviewed_at=reviewed_at,
        )
        self.data_store.save_ledger(ledger)
        return _review_result(wiki, ledger, sources, applied_count)

    def set_fact_decision(
        self,
        wiki_id: str,
        source_id: str,
        fact_id: str,
        ticked: bool,
        *,
        reason: str = "",
        reviewed_at: str = "",
    ) -> ReviewWorkflowResult:
        return self.review_source(
            wiki_id,
            source_id,
            [ReviewResult(fact_id=fact_id, ticked=ticked, reason=reason)],
            reviewed_at=reviewed_at or utc_now(),
        )

    def review_source_with_provider(
        self,
        wiki_id: str,
        source_id: str,
        provider: ReviewProvider,
        reviewed_at: str = "",
        review_all: bool = False,
    ) -> ReviewWorkflowResult:
        wiki = self._load_wiki(wiki_id)
        source = self.data_store.load_source(source_id)
        sources = self.data_store.load_sources()
        ledger = self.data_store.load_ledger()
        if source_id not in ledger.assigned_sources(wiki_id):
            raise ValueError(f"source {source_id!r} is not assigned to wiki {wiki_id!r}")
        pending = (
            review_facts_for_source(wiki, source_id, ledger, sources)
            if review_all
            else review_delta_for_source(wiki, source_id, ledger, sources)
        )
        provider_result = provider.review(_review_context(wiki, source), pending)
        results = validate_review_results(pending, provider_result.decisions)
        applied_count = 0
        if results:
            applied_count = apply_review_results(
                wiki,
                source_id,
                ledger,
                source,
                results,
                reviewed_at=reviewed_at or utc_now(),
            )
        self.data_store.save_ledger(ledger)
        return _review_result(
            wiki,
            ledger,
            sources,
            applied_count,
            provider=provider_result.provider,
            model=provider_result.model,
            usage=provider_result.usage,
        )


def _review_result(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
    applied_count: int,
    *,
    provider: str = "",
    model: str = "",
    usage: Mapping[str, Any] | None = None,
) -> ReviewWorkflowResult:
    return ReviewWorkflowResult(
        applied_count=applied_count,
        remaining_review_count=len(review_delta_for_wiki(wiki, ledger, sources)),
        status=status_for_wiki(wiki, ledger, sources),
        provider=provider,
        model=model,
        usage=usage or {},
    )


def _review_context(wiki: WikiRecord, source: SourceRecord) -> WikiReviewContext:
    return WikiReviewContext(
        wiki_id=wiki.wiki_id,
        wiki_title=wiki.title,
        wiki_intention=wiki_intention_text(wiki),
        source_id=source.source_id,
        source_title=source.title,
        source_summary=source.summary,
    )
