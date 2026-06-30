"""Read model for facts behind a wiki build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .citations import natural_key
from .ledger import ReviewDecision, WikiLedger
from .records import FactRecord, SourceRecord, WikiRecord, WikiRegistry, source_index
from .status import WikiStatus, status_for_wiki
from .wiki_scope import wiki_scope_signature


@dataclass(frozen=True)
class WikiFactDetail:
    fact_id: str
    text: str
    state: str
    reason: str = ""
    reviewed_at: str = ""


@dataclass(frozen=True)
class WikiFactSourceGroup:
    source_id: str
    source_title: str
    accepted: tuple[WikiFactDetail, ...]
    not_used: tuple[WikiFactDetail, ...]


@dataclass(frozen=True)
class WikiFactsView:
    wiki: WikiRecord
    status: WikiStatus
    groups: tuple[WikiFactSourceGroup, ...]

    @property
    def accepted_count(self) -> int:
        return sum(len(group.accepted) for group in self.groups)

    @property
    def not_used_count(self) -> int:
        return sum(len(group.not_used) for group in self.groups)


def wiki_facts_view(
    registry: WikiRegistry,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
    wiki_id: str,
    status: WikiStatus | None = None,
) -> WikiFactsView:
    wiki = registry.wikis.get(wiki_id)
    if wiki is None:
        raise KeyError(f"unknown wiki_id {wiki_id!r}")
    source_map = source_index(sources)
    groups: list[WikiFactSourceGroup] = []
    for source_id in ledger.assigned_sources(wiki_id):
        source = source_map.get(source_id)
        if source is None:
            continue
        group = _source_group(wiki, ledger, source)
        if group.accepted or group.not_used:
            groups.append(group)
    return WikiFactsView(
        wiki=wiki,
        status=status if status is not None else status_for_wiki(wiki, ledger, source_map),
        groups=tuple(groups),
    )


def _source_group(
    wiki: WikiRecord,
    ledger: WikiLedger,
    source: SourceRecord,
) -> WikiFactSourceGroup:
    accepted: list[WikiFactDetail] = []
    not_used: list[WikiFactDetail] = []
    current_scope = wiki_scope_signature(wiki)
    for fact in sorted(source.facts, key=lambda item: natural_key(item.fact_id)):
        decision = ledger.decision_for(wiki.wiki_id, source.source_id, fact.fact_id)
        detail = _fact_detail(fact, decision, current_scope)
        if detail.state == "accepted":
            accepted.append(detail)
        else:
            not_used.append(detail)
    return WikiFactSourceGroup(
        source_id=source.source_id,
        source_title=source.title or source.source_id,
        accepted=tuple(accepted),
        not_used=tuple(not_used),
    )


def _fact_detail(
    fact: FactRecord,
    decision: ReviewDecision | None,
    current_scope: str,
) -> WikiFactDetail:
    if decision is None:
        return WikiFactDetail(fact_id=fact.fact_id, text=fact.text, state="pending")
    stale = decision.fact_signature != fact.signature() or decision.wiki_scope_signature != current_scope
    state = "accepted" if decision.ticked else "rejected"
    if stale:
        state = "stale " + state
    return WikiFactDetail(
        fact_id=fact.fact_id,
        text=fact.text,
        state=state,
        reason=decision.reason,
        reviewed_at=decision.reviewed_at,
    )
