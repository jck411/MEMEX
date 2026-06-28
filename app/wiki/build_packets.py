"""Fact packets for provider-backed wiki synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from .citations import (
    compact_fact_note,
    evidence_ids,
    fact_records_by_key,
    fact_sort_key,
    inline_text,
    source_keys_by_id,
)
from .ledger import WikiLedger
from .markdown import (
    FACTS_END,
    FACTS_START,
    SYNTHESIS_END,
    SYNTHESIS_START,
    remove_obsolete_markdown_sections,
)
from .records import SourceRecord, WikiRecord, source_index
from .status import accepted_facts_for_wiki
from .wiki_scope import wiki_description, wiki_intention_text

MAX_EXISTING_MARKDOWN_CONTEXT = 30_000
MAX_FACT_TEXT = 1_500
_COMPACT_CITATION_RE = re.compile(r"\(S\d+:[A-Za-z0-9_.:-]+(?:,[A-Za-z0-9_.:-]+)*\)")


@dataclass(frozen=True)
class WikiBuildFact:
    source_id: str
    source_title: str
    source_key: str
    fact_id: str
    fact_signature: str
    text: str
    citation: str
    evidence_ids: tuple[str, ...]
    review_reason: str = ""


@dataclass(frozen=True)
class WikiBuildPacket:
    wiki_id: str
    wiki_title: str
    wiki_path: str
    wiki_description: str
    wiki_intention: str
    existing_markdown_context: str
    accepted_facts: tuple[WikiBuildFact, ...]


def build_fact_packet(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
    existing_markdown: str = "",
) -> WikiBuildPacket:
    source_map = source_index(sources)
    facts = tuple(sorted(accepted_facts_for_wiki(wiki, ledger, source_map), key=fact_sort_key))
    fact_records = fact_records_by_key(source_map)
    source_keys = source_keys_by_id(facts)
    packet_facts: list[WikiBuildFact] = []
    for fact in facts:
        source = source_map.get(fact.source_id)
        fact_record = fact_records.get((fact.source_id, fact.fact_id))
        source_key = source_keys.get(fact.source_id, "")
        packet_facts.append(
            WikiBuildFact(
                source_id=fact.source_id,
                source_title=source.title if source else fact.source_id,
                source_key=source_key,
                fact_id=fact.fact_id,
                fact_signature=fact.fact_signature,
                text=_clip(fact.text, MAX_FACT_TEXT),
                citation=compact_fact_note(fact, fact_record, source_key),
                evidence_ids=tuple(evidence_ids(fact_record)),
                review_reason=fact.decision.reason,
            )
        )
    return WikiBuildPacket(
        wiki_id=wiki.wiki_id,
        wiki_title=wiki.title,
        wiki_path=wiki.path,
        wiki_description=wiki_description(wiki),
        wiki_intention=wiki_intention_text(wiki),
        existing_markdown_context=existing_markdown_context(
            existing_markdown,
            allowed_citations={fact.citation for fact in packet_facts if fact.citation},
        ),
        accepted_facts=tuple(packet_facts),
    )


def existing_markdown_context(
    markdown: str,
    *,
    allowed_citations: set[str] | None = None,
) -> str:
    if not markdown.strip():
        return ""
    _validate_marker_pair(markdown, SYNTHESIS_START, SYNTHESIS_END, "synthesis")
    _validate_marker_pair(markdown, FACTS_START, FACTS_END, "facts")
    context = _remove_marked_section(markdown, FACTS_START, FACTS_END)
    context = context.replace(SYNTHESIS_START, "").replace(SYNTHESIS_END, "")
    context = remove_obsolete_markdown_sections(context)
    context = _filter_current_cited_blocks(context, allowed_citations or set())
    return _clip(context.strip(), MAX_EXISTING_MARKDOWN_CONTEXT)


def _validate_marker_pair(markdown: str, start_marker: str, end_marker: str, name: str) -> None:
    start = markdown.find(start_marker)
    end = markdown.find(end_marker)
    if start == -1 and end == -1:
        return
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"existing markdown has incomplete MEMEX {name} markers")


def _remove_marked_section(markdown: str, start_marker: str, end_marker: str) -> str:
    start = markdown.find(start_marker)
    end = markdown.find(end_marker)
    if start == -1 and end == -1:
        return markdown
    end += len(end_marker)
    return (markdown[:start].rstrip() + "\n\n" + markdown[end:].lstrip()).strip() + "\n"


def _filter_current_cited_blocks(markdown: str, allowed_citations: set[str]) -> str:
    if not allowed_citations:
        return markdown
    blocks = [block.strip() for block in re.split(r"\n\s*\n", markdown) if block.strip()]
    kept: list[str] = []
    for block in blocks:
        citations = set(_COMPACT_CITATION_RE.findall(block))
        if citations and not citations.issubset(allowed_citations):
            continue
        kept.append(block)
    return "\n\n".join(kept).strip() + ("\n" if kept else "")


def _clip(value: object, max_chars: int) -> str:
    text = inline_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
