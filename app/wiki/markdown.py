"""Markdown rendering for generated wiki sections and fact audit appendix."""

from __future__ import annotations

import re
from typing import Iterable, Mapping
from urllib.parse import quote

from .citations import (
    inline_text,
    natural_key,
)
from .ledger import WikiLedger
from .records import FactRecord, SourceRecord, WikiRecord, source_index
from .wiki_scope import wiki_description, wiki_scope_signature

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
    ledger: WikiLedger,
    sources: Iterable[SourceRecord] | Mapping[str, SourceRecord] = (),
) -> str:
    source_map = source_index(sources)
    lines = [FACTS_START, "## Source Fact Decisions", ""]
    description = wiki_description(wiki)
    if description:
        lines.append(f"**Wiki description:** {inline_text(description)}")
        lines.append("")
    _append_source_decisions(lines, wiki, ledger, source_map)
    if lines[-1] == "":
        lines.pop()
    lines.append(FACTS_END)
    return "\n".join(lines)


def _append_source_decisions(
    lines: list[str],
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Mapping[str, SourceRecord],
) -> None:
    appended = False
    for source_id in ledger.assigned_sources(wiki.wiki_id):
        source = sources.get(source_id)
        if source is None:
            continue
        accepted, rejected = _current_source_decisions(wiki, ledger, source)
        if not accepted and not rejected:
            continue
        appended = True
        lines.extend([f"### {_source_reference_label(source)}", ""])
        _append_decision_group(lines, "Accepted", source.source_id, accepted)
        _append_decision_group(lines, "Rejected", source.source_id, rejected)
        lines.append("")
    if not appended:
        lines.append("_No reviewed facts yet._")


def _current_source_decisions(
    wiki: WikiRecord,
    ledger: WikiLedger,
    source: SourceRecord,
) -> tuple[list[FactRecord], list[FactRecord]]:
    accepted: list[FactRecord] = []
    rejected: list[FactRecord] = []
    current_scope = wiki_scope_signature(wiki)
    for fact in sorted(source.facts, key=lambda item: natural_key(item.fact_id)):
        decision = ledger.decision_for(wiki.wiki_id, source.source_id, fact.fact_id)
        if decision is None:
            continue
        if decision.fact_signature != fact.signature():
            continue
        if decision.wiki_scope_signature != current_scope:
            continue
        if decision.ticked:
            accepted.append(fact)
        else:
            rejected.append(fact)
    return accepted, rejected


def _append_decision_group(
    lines: list[str],
    title: str,
    source_id: str,
    facts: list[FactRecord],
) -> None:
    if not facts:
        return
    lines.extend([f"#### {title}", ""])
    for fact in facts:
        lines.append(_fact_decision_line(source_id, fact))
    lines.append("")


def _fact_decision_line(source_id: str, fact: FactRecord) -> str:
    return (
        f"- {_fact_anchor(source_id, fact.fact_id)}"
        f"`{inline_text(fact.fact_id)}`: {inline_text(fact.text)}"
    )


def _fact_anchor(source_id: str, fact_id: str) -> str:
    anchor = _fact_anchor_id(source_id, fact_id)
    return f'<a id="{anchor}"></a> ' if anchor else ""


def _fact_anchor_id(source_id: str, fact_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.:-]+", "-", f"{source_id}-{fact_id}")
    slug = slug.strip("-").lower()
    return f"memex-fact-{slug}" if slug else ""


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
    markdown = _prepare_existing_markdown(wiki, existing_markdown)
    markdown = replace_synthesis_section(markdown, render_synthesis_section(synthesis_markdown))
    markdown = replace_fact_audit_section(
        markdown,
        render_fact_audit_section(wiki, ledger, source_map),
    )
    return markdown


def _source_reference_label(source: SourceRecord) -> str:
    title = inline_text(source.title) if source.title else inline_text(source.source_id)
    href = "/source/" + quote(source.source_id, safe="")
    if title and title != source.source_id:
        return f"[{title}]({href}) (`{source.source_id}`)"
    return f"[{inline_text(source.source_id)}]({href})"


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
