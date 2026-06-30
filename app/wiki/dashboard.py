"""Dashboard read models for wiki status and source assignment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .ledger import WikiLedger
from .records import SourceRecord, WikiRegistry, source_index
from .review import review_delta_for_source, review_delta_for_wiki
from .status import (
    WikiStatus,
    accepted_facts_for_wiki,
    statuses_for_registry,
)


@dataclass(frozen=True)
class WikiDashboardRow:
    wiki_id: str
    title: str
    path: str
    description: str
    state: str
    assigned_source_count: int
    review_delta_count: int
    accepted_fact_count: int
    file_location: str = ""


@dataclass(frozen=True)
class WikiAssignmentBubble:
    wiki_id: str
    title: str
    assigned: bool
    state: str


@dataclass(frozen=True)
class SourceDashboardRow:
    source_id: str
    title: str
    summary: str
    document_date: str
    source_type: str
    fact_count: int
    extraction_issue_count: int
    wiki_bubbles: tuple[WikiAssignmentBubble, ...]
    needs_review_wiki_ids: tuple[str, ...]
    needs_build_wiki_ids: tuple[str, ...]

    @property
    def unassigned(self) -> bool:
        return not any(bubble.assigned for bubble in self.wiki_bubbles)


@dataclass(frozen=True)
class SourceDashboardFilter:
    search: str = ""
    unassigned: bool = False
    needs_review: bool = False
    needs_build: bool = False
    has_issues: bool = False


@dataclass(frozen=True)
class WikiDashboardSnapshot:
    wikis: tuple[WikiDashboardRow, ...]
    sources: tuple[SourceDashboardRow, ...]


def status_label(status: WikiStatus) -> str:
    if status.current:
        return "current"
    if status.needs_review:
        return "needs_review"
    return "needs_build"


def dashboard_snapshot(
    registry: WikiRegistry,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
    source_created_at_by_id: Mapping[str, str] | None = None,
    statuses: Mapping[str, WikiStatus] | None = None,
) -> WikiDashboardSnapshot:
    source_map = source_index(sources)
    status_map = statuses if statuses is not None else statuses_for_registry(
        registry,
        ledger,
        source_map,
    )
    wiki_rows = tuple(
        _wiki_row(wiki_id, registry, ledger, source_map, status_map[wiki_id])
        for wiki_id in registry.active_ids()
    )
    source_rows = tuple(
        _source_row(source, registry, ledger, source_map, status_map)
        for source in _sources_newest_first(
            source_map.values(),
            source_created_at_by_id or {},
        )
    )
    return WikiDashboardSnapshot(wikis=wiki_rows, sources=source_rows)


def filter_sources(
    rows: Iterable[SourceDashboardRow],
    source_filter: SourceDashboardFilter,
) -> tuple[SourceDashboardRow, ...]:
    return tuple(row for row in rows if source_matches_filter(row, source_filter))


def source_matches_filter(
    row: SourceDashboardRow,
    source_filter: SourceDashboardFilter,
) -> bool:
    if source_filter.search:
        haystack = " ".join((row.source_id, row.title, row.summary)).lower()
        if source_filter.search.lower() not in haystack:
            return False
    if source_filter.unassigned and not row.unassigned:
        return False
    if source_filter.needs_review and not row.needs_review_wiki_ids:
        return False
    if source_filter.needs_build and not row.needs_build_wiki_ids:
        return False
    if source_filter.has_issues and row.extraction_issue_count == 0:
        return False
    return True


def _sources_newest_first(
    sources: Iterable[SourceRecord],
    source_created_at_by_id: Mapping[str, str],
) -> tuple[SourceRecord, ...]:
    if not source_created_at_by_id:
        return tuple(sorted(sources, key=lambda item: item.source_id))
    return tuple(
        sorted(
            sources,
            key=lambda item: (source_created_at_by_id.get(item.source_id, ""), item.source_id),
            reverse=True,
        )
    )


def _wiki_row(
    wiki_id: str,
    registry: WikiRegistry,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord],
    status: WikiStatus,
) -> WikiDashboardRow:
    wiki = registry.wikis[wiki_id]
    return WikiDashboardRow(
        wiki_id=wiki_id,
        title=wiki.title,
        path=wiki.path,
        description=wiki.description,
        state=status_label(status),
        assigned_source_count=len(ledger.assigned_sources(wiki_id)),
        review_delta_count=len(review_delta_for_wiki(wiki, ledger, sources)),
        accepted_fact_count=len(accepted_facts_for_wiki(wiki, ledger, sources)),
    )


def _source_row(
    source: SourceRecord,
    registry: WikiRegistry,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord],
    statuses: Mapping[str, WikiStatus],
) -> SourceDashboardRow:
    needs_review_wikis: list[str] = []
    needs_build_wikis: list[str] = []
    bubbles: list[WikiAssignmentBubble] = []
    for wiki_id in registry.active_ids():
        wiki = registry.wikis[wiki_id]
        assigned = source.source_id in ledger.assigned_sources(wiki_id)
        if assigned and review_delta_for_source(wiki, source.source_id, ledger, sources):
            needs_review_wikis.append(wiki_id)
        if assigned and not statuses[wiki_id].needs_review and statuses[wiki_id].needs_build:
            needs_build_wikis.append(wiki_id)
        bubbles.append(
            WikiAssignmentBubble(
                wiki_id=wiki_id,
                title=wiki.title,
                assigned=assigned,
                state=status_label(statuses[wiki_id]),
            )
        )
    return SourceDashboardRow(
        source_id=source.source_id,
        title=source.title,
        summary=source.summary,
        document_date=source.document_date or "",
        source_type=source.source_type or "",
        fact_count=len(source.facts),
        extraction_issue_count=len(source.extraction_issues),
        wiki_bubbles=tuple(bubbles),
        needs_review_wiki_ids=tuple(needs_review_wikis),
        needs_build_wiki_ids=tuple(needs_build_wikis),
    )
