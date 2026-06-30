"""Fact packets for provider-backed wiki synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .citations import (
    fact_sort_key,
    inline_text,
)
from .language_guardrails import remove_cjk_dominant_blocks
from .ledger import WikiLedger
from .markdown import (
    FACTS_END,
    FACTS_START,
    REFERENCES_END,
    REFERENCES_START,
    SYNTHESIS_END,
    SYNTHESIS_START,
    remove_obsolete_markdown_sections,
)
from .records import SourceRecord, WikiRecord, source_index
from .status import accepted_facts_for_wiki
from .wiki_scope import wiki_description, wiki_intention_text

MAX_EXISTING_MARKDOWN_CONTEXT = 30_000
MAX_FACT_TEXT = 1_500


@dataclass(frozen=True)
class WikiBuildFact:
    source_id: str
    source_title: str
    fact_id: str
    fact_signature: str
    text: str
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
    packet_facts: list[WikiBuildFact] = []
    for fact in facts:
        source = source_map.get(fact.source_id)
        packet_facts.append(
            WikiBuildFact(
                source_id=fact.source_id,
                source_title=source.title if source else fact.source_id,
                fact_id=fact.fact_id,
                fact_signature=fact.fact_signature,
                text=_clip(fact.text, MAX_FACT_TEXT),
                review_reason=fact.decision.reason,
            )
        )
    return WikiBuildPacket(
        wiki_id=wiki.wiki_id,
        wiki_title=wiki.title,
        wiki_path=wiki.path,
        wiki_description=wiki_description(wiki),
        wiki_intention=wiki_intention_text(wiki),
        existing_markdown_context=existing_markdown_context(existing_markdown),
        accepted_facts=tuple(packet_facts),
    )


def existing_markdown_context(markdown: str) -> str:
    if not markdown.strip():
        return ""
    _validate_marker_pair(markdown, SYNTHESIS_START, SYNTHESIS_END, "synthesis")
    _validate_marker_pair(markdown, FACTS_START, FACTS_END, "facts")
    _validate_marker_pair(markdown, REFERENCES_START, REFERENCES_END, "references")
    context = _remove_marked_section(markdown, SYNTHESIS_START, SYNTHESIS_END)
    context = _remove_marked_section(context, FACTS_START, FACTS_END)
    context = _remove_marked_section(context, REFERENCES_START, REFERENCES_END)
    context = remove_obsolete_markdown_sections(context)
    context = remove_cjk_dominant_blocks(context)
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


def _clip(value: object, max_chars: int) -> str:
    text = inline_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
