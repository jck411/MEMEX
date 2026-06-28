"""Markdown rendering for generated wiki sections and fact audit appendix."""

from __future__ import annotations

import re
from typing import Iterable, Mapping

from .citations import (
    compact_fact_anchor,
    compact_fact_note,
    evidence_ids,
    fact_records_by_key,
    fact_sort_key,
    inline_text,
    link_compact_fact_notes,
    source_keys_by_id,
)
from .ledger import WikiLedger
from .records import SourceRecord, WikiRecord, source_index
from .status import AcceptedFact, accepted_facts_for_wiki
from .wiki_scope import wiki_description

SYNTHESIS_START = "<!-- MEMEX:SYNTHESIS:START -->"
SYNTHESIS_END = "<!-- MEMEX:SYNTHESIS:END -->"
FACTS_START = "<!-- MEMEX:FACTS:START -->"
FACTS_END = "<!-- MEMEX:FACTS:END -->"

_HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")


def render_synthesis_section(synthesis_markdown: str) -> str:
    body = synthesis_markdown.strip()
    if not body:
        raise ValueError("synthesis markdown is required")
    return "\n".join((SYNTHESIS_START, body, SYNTHESIS_END))


def render_fact_audit_section(
    wiki: WikiRecord,
    accepted_facts: Iterable[AcceptedFact],
    sources: Iterable[SourceRecord] | Mapping[str, SourceRecord] = (),
) -> str:
    facts = sorted(accepted_facts, key=fact_sort_key)
    source_map = source_index(sources)
    fact_records = fact_records_by_key(source_map)
    source_keys = source_keys_by_id(facts)
    citation_by_fact = _citation_by_fact(facts, fact_records, source_keys)
    lines = [FACTS_START, "## Accepted Facts", ""]
    description = wiki_description(wiki)
    if description:
        lines.append(f"**Wiki description:** {inline_text(description)}")
        lines.append("")
    if not facts:
        lines.append("_No accepted facts yet._")
    else:
        _append_fact_lines(lines, facts, source_map, citation_by_fact)
    if facts:
        lines.extend(_references_section(facts, source_map, fact_records, source_keys))
    if lines[-1] == "":
        lines.pop()
    lines.append(FACTS_END)
    return "\n".join(lines)


def _append_fact_lines(
    lines: list[str],
    facts: Iterable[AcceptedFact],
    sources: Mapping[str, SourceRecord],
    citation_by_fact: Mapping[tuple[str, str], str],
) -> None:
    for fact in facts:
        citation = citation_by_fact.get((fact.source_id, fact.fact_id), "")
        suffix = f" {citation}" if citation else ""
        anchor = compact_fact_anchor(citation)
        prefix = f"{anchor} " if anchor else ""
        lines.append(f"- {prefix}{inline_text(fact.text)}{suffix}")
        lines.append(f"  - Source: {_source_reference_label(fact.source_id, sources)}")
        if fact.decision.reason:
            lines.append(f"  - Review: {inline_text(fact.decision.reason)}")
        lines.append("")


def replace_synthesis_section(existing_markdown: str, section: str) -> str:
    return _replace_or_insert_marked_section(
        existing_markdown,
        section,
        SYNTHESIS_START,
        SYNTHESIS_END,
        error="existing markdown has incomplete MEMEX synthesis markers",
        insert_after_title=True,
    )


def replace_fact_audit_section(existing_markdown: str, section: str) -> str:
    return _replace_or_insert_marked_section(
        existing_markdown,
        section,
        FACTS_START,
        FACTS_END,
        error="existing markdown has incomplete MEMEX facts markers",
        insert_after_title=False,
    )


def build_wiki_markdown(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Iterable[SourceRecord] | Mapping[str, SourceRecord],
    synthesis_markdown: str,
    existing_markdown: str = "",
) -> str:
    source_map = source_index(sources)
    accepted_facts = accepted_facts_for_wiki(wiki, ledger, source_map)
    fact_records = fact_records_by_key(source_map)
    source_keys = source_keys_by_id(accepted_facts)
    citations = _citation_by_fact(accepted_facts, fact_records, source_keys).values()
    linked_synthesis = link_compact_fact_notes(synthesis_markdown, citations)
    markdown = _prepare_existing_markdown(wiki, existing_markdown)
    markdown = replace_synthesis_section(markdown, render_synthesis_section(linked_synthesis))
    markdown = replace_fact_audit_section(
        markdown,
        render_fact_audit_section(wiki, accepted_facts, source_map),
    )
    return markdown


def _source_reference_label(
    source_id: str,
    sources: Mapping[str, SourceRecord],
) -> str:
    title = inline_text(sources[source_id].title) if source_id in sources else ""
    if title and title != source_id:
        return f"{title} (`{source_id}`)"
    return f"`{source_id}`"


def _citation_by_fact(
    facts: Iterable[AcceptedFact],
    fact_records: Mapping[tuple[str, str], FactRecord],
    source_keys: Mapping[str, str],
) -> dict[tuple[str, str], str]:
    return {
        (fact.source_id, fact.fact_id): compact_fact_note(
            fact,
            fact_records.get((fact.source_id, fact.fact_id)),
            source_keys.get(fact.source_id, ""),
        )
        for fact in facts
    }


def _references_section(
    facts: list[AcceptedFact],
    sources: Mapping[str, SourceRecord],
    fact_records: Mapping[tuple[str, str], FactRecord],
    source_keys: Mapping[str, str],
) -> list[str]:
    lines = ["## References", ""]
    for source_id, source_key in source_keys.items():
        lines.extend([f"### {source_key}. {_source_reference_label(source_id, sources)}", ""])
        source_facts = [fact for fact in facts if fact.source_id == source_id]
        for fact in source_facts:
            fact_record = fact_records.get((fact.source_id, fact.fact_id))
            citation = compact_fact_note(fact, fact_record, source_key)
            prefix = f"{citation} " if citation else ""
            pieces = [f"fact `{inline_text(fact.fact_id)}`"]
            fact_evidence_ids = evidence_ids(fact_record)
            if fact_evidence_ids:
                pieces.append(
                    "evidence " + ", ".join(f"`{inline_text(item)}`" for item in fact_evidence_ids)
                )
            lines.append(f"- {prefix}{' ; '.join(pieces)}: {inline_text(fact.text)}")
        lines.append("")
    return lines


def _replace_or_insert_marked_section(
    existing_markdown: str,
    section: str,
    start_marker: str,
    end_marker: str,
    *,
    error: str,
    insert_after_title: bool,
) -> str:
    start = existing_markdown.find(start_marker)
    end = existing_markdown.find(end_marker)
    if start == -1 and end == -1:
        if not existing_markdown.strip():
            return section + "\n"
        if insert_after_title:
            return _insert_after_title(existing_markdown, section)
        return existing_markdown.rstrip() + "\n\n" + section + "\n"
    if start == -1 or end == -1 or end < start:
        raise ValueError(error)

    end += len(end_marker)
    prefix = existing_markdown[:start].rstrip()
    suffix = existing_markdown[end:].lstrip()
    pieces = [piece for piece in (prefix, section, suffix) if piece]
    return "\n\n".join(pieces) + "\n"


def _prepare_existing_markdown(wiki: WikiRecord, existing_markdown: str) -> str:
    without_obsolete = remove_obsolete_markdown_sections(existing_markdown)
    if not without_obsolete.strip():
        return f"# {inline_text(wiki.title)}\n"
    return _ensure_wiki_title(wiki, without_obsolete)


def _ensure_wiki_title(wiki: WikiRecord, markdown: str) -> str:
    title = f"# {inline_text(wiki.title)}"
    lines = markdown.rstrip().splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.lstrip().startswith("# "):
            lines[index] = title
            return "\n".join(lines) + "\n"
        return title + "\n\n" + markdown.strip() + "\n"
    return title + "\n"


def _insert_after_title(existing_markdown: str, section: str) -> str:
    markdown = existing_markdown.rstrip()
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith("# "):
            prefix = "\n".join(lines[: index + 1]).rstrip()
            suffix = "\n".join(lines[index + 1 :]).strip()
            pieces = [piece for piece in (prefix, section, suffix) if piece]
            return "\n\n".join(pieces) + "\n"
    return markdown + "\n\n" + section + "\n"


def remove_obsolete_markdown_sections(markdown: str) -> str:
    if not markdown.strip():
        return markdown
    lines = markdown.splitlines()
    result: list[str] = []
    skip_default_level: int | None = None
    skipped_default_content = False
    for line in lines:
        match = _HEADING_RE.match(line.strip())
        if skip_default_level is not None:
            if match and len(match.group("level")) <= skip_default_level:
                skip_default_level = None
                skipped_default_content = False
            elif not line.strip():
                if skipped_default_content:
                    skip_default_level = None
                    skipped_default_content = False
                continue
            else:
                skipped_default_content = True
                continue

        if match:
            title = _normalized_heading(match.group("title"))
            if title == "default conversation context":
                skip_default_level = len(match.group("level"))
                skipped_default_content = False
                continue
            if title == "llm context":
                continue
        result.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(result)).strip() + ("\n" if result else "")


def _normalized_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip("#")).lower()
