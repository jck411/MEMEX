"""Compact citation helpers for accepted wiki facts."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .records import FactRecord
from .status import AcceptedFact

COMPACT_FACT_NOTE_RE = re.compile(r"\(S\d+:[A-Za-z0-9_.:-]+(?:,[A-Za-z0-9_.:-]+)*\)")


def inline_text(value: object) -> str:
    text = " ".join(str(value).split())
    return text.replace("[[", r"\[\[").replace("]]", r"\]\]")


def fact_records_by_key(
    sources: Mapping[str, object],
) -> dict[tuple[str, str], FactRecord]:
    records: dict[tuple[str, str], FactRecord] = {}
    for source_id, source in sources.items():
        fact_by_id = getattr(source, "fact_by_id", None)
        if not callable(fact_by_id):
            continue
        for fact_id, fact in fact_by_id().items():
            if isinstance(fact, FactRecord):
                records[(source_id, fact_id)] = fact
    return records


def source_keys_by_id(facts: Iterable[AcceptedFact]) -> dict[str, str]:
    source_ids: list[str] = []
    for fact in facts:
        if fact.source_id not in source_ids:
            source_ids.append(fact.source_id)
    return {source_id: f"S{index}" for index, source_id in enumerate(source_ids, start=1)}


def compact_fact_note(
    fact: AcceptedFact,
    fact_record: FactRecord | None,
    source_key: str,
) -> str:
    ids = unique([*evidence_ids(fact_record), fact.fact_id])
    if not ids:
        return ""
    prefix = f"{source_key}:" if source_key else ""
    return f"({prefix}{','.join(ids)})"


def compact_fact_anchor(citation: str) -> str:
    anchor_id = compact_fact_anchor_id(citation)
    return f'<a id="{anchor_id}"></a>' if anchor_id else ""


def compact_fact_anchor_id(citation: str) -> str:
    if not COMPACT_FACT_NOTE_RE.fullmatch(citation.strip()):
        return ""
    value = citation.strip()[1:-1]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return f"memex-fact-{slug}" if slug else ""


def link_compact_fact_notes(text: str, citations: Iterable[str]) -> str:
    allowed = {citation for citation in citations if citation}
    if not allowed:
        return text

    def replace(match: re.Match[str]) -> str:
        citation = match.group(0)
        if citation not in allowed or _already_linked(text, match):
            return citation
        anchor_id = compact_fact_anchor_id(citation)
        return f"[{citation}](#{anchor_id})" if anchor_id else citation

    return COMPACT_FACT_NOTE_RE.sub(replace, text)


def _already_linked(text: str, match: re.Match[str]) -> bool:
    start, end = match.span()
    return start > 0 and text[start - 1] == "[" and end < len(text) and text[end] == "]"


def evidence_ids(fact_record: FactRecord | None) -> list[str]:
    if fact_record is None:
        return []
    provenance = fact_record.provenance
    explicit_ids = string_list(provenance.get("evidence_ids"))
    if explicit_ids:
        return explicit_ids
    return unique(
        text(item.get("id"))
        for item in provenance.get("evidence", ())
        if isinstance(item, Mapping)
    )


def fact_sort_key(fact: AcceptedFact) -> tuple[str, tuple[tuple[int, int | str], ...]]:
    return fact.source_id, natural_key(fact.fact_id)


def natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in re.split(r"(\d+)", value)
        if part
    )


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [text(item) for item in value if text(item)]


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = text(value)
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def text(value: object) -> str:
    return "" if value is None else str(value).strip()
