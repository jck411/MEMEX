"""Source detail read model for the local wiki dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .dashboard import WikiAssignmentBubble, status_label
from .ledger import WikiLedger
from .records import FactRecord, SourceRecord, WikiRegistry, source_index
from .status import statuses_for_registry
from .wiki_scope import wiki_scope_signature


@dataclass(frozen=True)
class SourceEvidenceDetail:
    evidence_id: str
    quote: str
    source_channel: str
    page: str
    locator: str


@dataclass(frozen=True)
class SourceFactDetail:
    fact_id: str
    text: str
    fact_signature: str
    evidence: tuple[SourceEvidenceDetail, ...]
    metadata: tuple[tuple[str, str], ...]
    decisions: tuple["SourceFactDecisionDetail", ...]


@dataclass(frozen=True)
class SourceFactDecisionDetail:
    wiki_id: str
    title: str
    state: str
    reason: str
    reviewed_at: str
    ticked: bool | None
    stale: bool


@dataclass(frozen=True)
class SourceDetailView:
    source_id: str
    title: str
    summary: str
    document_date: str
    source_type: str
    facts: tuple[SourceFactDetail, ...]
    extraction_issues: tuple[str, ...]
    wiki_bubbles: tuple[WikiAssignmentBubble, ...]

    @property
    def fact_count(self) -> int:
        return len(self.facts)

    @property
    def extraction_issue_count(self) -> int:
        return len(self.extraction_issues)


def source_detail_view(
    registry: WikiRegistry,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
    source_id: str,
) -> SourceDetailView:
    source_map = source_index(sources)
    source = source_map.get(source_id)
    if source is None:
        raise KeyError(f"unknown source_id {source_id!r}")

    statuses = statuses_for_registry(registry, ledger, source_map)
    bubbles: list[WikiAssignmentBubble] = []
    assigned_wiki_ids: list[str] = []
    for wiki_id in registry.active_ids():
        status = statuses[wiki_id]
        assigned = source.source_id in ledger.assigned_sources(wiki_id)
        bubble = WikiAssignmentBubble(
            wiki_id=wiki_id,
            title=registry.wikis[wiki_id].title,
            assigned=assigned,
            state=status_label(status),
        )
        bubbles.append(bubble)
        if assigned:
            assigned_wiki_ids.append(wiki_id)

    return SourceDetailView(
        source_id=source.source_id,
        title=source.title,
        summary=source.summary,
        document_date=source.document_date or "",
        source_type=source.source_type or "",
        facts=tuple(
            _source_fact_detail(
                fact,
                source.source_id,
                registry,
                ledger,
                assigned_wiki_ids,
            )
            for fact in sorted(source.facts, key=lambda item: item.fact_id)
        ),
        extraction_issues=source.extraction_issues,
        wiki_bubbles=tuple(bubbles),
    )


def _source_fact_detail(
    fact: FactRecord,
    source_id: str,
    registry: WikiRegistry,
    ledger: WikiLedger,
    assigned_wiki_ids: Iterable[str],
) -> SourceFactDetail:
    provenance = dict(fact.provenance)
    return SourceFactDetail(
        fact_id=fact.fact_id,
        text=fact.text,
        fact_signature=fact.signature(),
        evidence=_evidence_details(provenance),
        metadata=_provenance_metadata(provenance),
        decisions=_decision_details(fact, source_id, registry, ledger, assigned_wiki_ids),
    )


def _decision_details(
    fact: FactRecord,
    source_id: str,
    registry: WikiRegistry,
    ledger: WikiLedger,
    assigned_wiki_ids: Iterable[str],
) -> tuple[SourceFactDecisionDetail, ...]:
    signature = fact.signature()
    details: list[SourceFactDecisionDetail] = []
    for wiki_id in assigned_wiki_ids:
        wiki = registry.wikis[wiki_id]
        decision = ledger.decision_for(wiki_id, source_id, fact.fact_id)
        if decision is None:
            details.append(
                SourceFactDecisionDetail(
                    wiki_id=wiki_id,
                    title=wiki.title,
                    state="pending",
                    reason="",
                    reviewed_at="",
                    ticked=None,
                    stale=False,
                )
            )
            continue
        stale = (
            decision.fact_signature != signature
            or decision.wiki_scope_signature != wiki_scope_signature(wiki)
        )
        state = "accepted" if decision.ticked else "rejected"
        if stale:
            state = "stale " + state
        details.append(
            SourceFactDecisionDetail(
                wiki_id=wiki_id,
                title=wiki.title,
                state=state,
                reason=decision.reason,
                reviewed_at=decision.reviewed_at,
                ticked=decision.ticked,
                stale=stale,
            )
        )
    return tuple(details)


def _evidence_details(provenance: Mapping[str, Any]) -> tuple[SourceEvidenceDetail, ...]:
    details: list[SourceEvidenceDetail] = []
    raw_evidence = provenance.get("evidence")
    if isinstance(raw_evidence, (list, tuple)):
        for item in raw_evidence:
            if not isinstance(item, Mapping):
                continue
            details.append(
                SourceEvidenceDetail(
                    evidence_id=_string_value(item.get("id")),
                    quote=_string_value(item.get("quote")),
                    source_channel=_string_value(item.get("source_channel")),
                    page=_string_value(item.get("page")),
                    locator=_string_value(item.get("locator")),
                )
            )
    if details:
        return tuple(details)

    quote = _string_value(provenance.get("quote"))
    locator = _fallback_locator(provenance)
    page = _string_value(provenance.get("page"))
    if quote or locator or page:
        return (
            SourceEvidenceDetail(
                evidence_id="",
                quote=quote,
                source_channel=_string_value(provenance.get("source_channel")),
                page=page,
                locator=locator,
            ),
        )
    return ()


def _fallback_locator(provenance: Mapping[str, Any]) -> str:
    parts: list[str] = []
    origin = _string_value(provenance.get("origin"))
    if origin:
        parts.append(origin)
    line_start = provenance.get("line_start")
    line_end = provenance.get("line_end")
    if line_start:
        if line_end and line_end != line_start:
            parts.append(f"lines {line_start}-{line_end}")
        else:
            parts.append(f"line {line_start}")
    locator = _string_value(provenance.get("locator"))
    if locator:
        parts.append(locator)
    return "; ".join(parts)


def _provenance_metadata(provenance: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    evidence_keys = {
        "evidence",
        "evidence_ids",
        "sensitivity",
        "quote",
        "source_channel",
        "page",
        "locator",
        "origin",
        "line_start",
        "line_end",
    }
    nested_keys = {"document", "run"}
    metadata: list[tuple[str, str]] = []
    for key in sorted(provenance):
        if key in evidence_keys or key in nested_keys:
            continue
        value = _string_value(provenance[key])
        if value:
            metadata.append((key, value))
    return tuple(metadata)


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value)
