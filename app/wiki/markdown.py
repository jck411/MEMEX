"""Markdown rendering for generated wiki sections."""

from __future__ import annotations

import re
from urllib.parse import quote

from .citations import (
    inline_text,
)
from .records import WikiRecord

SYNTHESIS_START = "<!-- MEMEX:SYNTHESIS:START -->"
SYNTHESIS_END = "<!-- MEMEX:SYNTHESIS:END -->"
FACTS_START = "<!-- MEMEX:FACTS:START -->"
FACTS_END = "<!-- MEMEX:FACTS:END -->"
REFERENCES_START = "<!-- MEMEX:REFERENCES:START -->"
REFERENCES_END = "<!-- MEMEX:REFERENCES:END -->"

_HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")


def render_synthesis_section(synthesis_markdown: str) -> str:
    body = synthesis_markdown.strip()
    if not body:
        raise ValueError("synthesis markdown is required")
    return "\n".join((SYNTHESIS_START, body, SYNTHESIS_END))


def render_references_section(wiki: WikiRecord) -> str:
    link = f"{quote(wiki.wiki_id, safe='')}/facts"
    body = f"## Wiki Provenance\n\n- [Facts used to build this page]({link})"
    return "\n".join((REFERENCES_START, body, REFERENCES_END))


def replace_synthesis_section(existing_markdown: str, section: str) -> str:
    return _replace_or_insert_marked_section(
        existing_markdown,
        section,
        SYNTHESIS_START,
        SYNTHESIS_END,
        error="existing markdown has incomplete MEMEX synthesis markers",
        insert_after_title=True,
    )


def replace_references_section(existing_markdown: str, section: str) -> str:
    return _replace_or_insert_marked_section(
        existing_markdown,
        section,
        REFERENCES_START,
        REFERENCES_END,
        error="existing markdown has incomplete MEMEX references markers",
        insert_after_title=False,
    )


def remove_fact_audit_section(existing_markdown: str) -> str:
    return _remove_marked_section(
        existing_markdown,
        FACTS_START,
        FACTS_END,
        error="existing markdown has incomplete MEMEX facts markers",
    )


def remove_references_section(existing_markdown: str) -> str:
    return _remove_marked_section(
        existing_markdown,
        REFERENCES_START,
        REFERENCES_END,
        error="existing markdown has incomplete MEMEX references markers",
    )


def build_wiki_markdown(
    wiki: WikiRecord,
    synthesis_markdown: str,
    existing_markdown: str = "",
) -> str:
    markdown = _prepare_existing_markdown(wiki, existing_markdown)
    markdown = replace_synthesis_section(markdown, render_synthesis_section(synthesis_markdown))
    markdown = replace_references_section(markdown, render_references_section(wiki))
    return markdown


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


def _remove_marked_section(
    existing_markdown: str,
    start_marker: str,
    end_marker: str,
    *,
    error: str,
) -> str:
    start = existing_markdown.find(start_marker)
    end = existing_markdown.find(end_marker)
    if start == -1 and end == -1:
        return existing_markdown
    if start == -1 or end == -1 or end < start:
        raise ValueError(error)

    end += len(end_marker)
    prefix = existing_markdown[:start].rstrip()
    suffix = existing_markdown[end:].lstrip()
    pieces = [piece for piece in (prefix, suffix) if piece]
    return "\n\n".join(pieces) + ("\n" if pieces else "")


def _prepare_existing_markdown(wiki: WikiRecord, existing_markdown: str) -> str:
    without_audit = remove_fact_audit_section(existing_markdown)
    without_references = remove_references_section(without_audit)
    without_obsolete = remove_obsolete_markdown_sections(without_references)
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
