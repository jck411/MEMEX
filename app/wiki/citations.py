"""Compact citation helpers for accepted wiki facts."""

from __future__ import annotations

import re
from typing import Iterable

from .status import AcceptedFact

_COMPACT_FACT_NOTE_TEXT = r"\(S\d+:\d+\)"
COMPACT_FACT_NOTE_RE = re.compile(_COMPACT_FACT_NOTE_TEXT)
_COMPACT_FACT_ANCHOR_REF_RE = re.compile(r"#memex-fact-s(?P<source>\d+)-(?P<number>\d+)")


def inline_text(value: object) -> str:
    text = " ".join(str(value).split())
    return text.replace("[[", r"\[\[").replace("]]", r"\]\]")


def source_keys_by_id(facts: Iterable[AcceptedFact]) -> dict[str, str]:
    source_ids: list[str] = []
    for fact in facts:
        if fact.source_id not in source_ids:
            source_ids.append(fact.source_id)
    return {source_id: f"S{index}" for index, source_id in enumerate(source_ids, start=1)}


def fact_numbers_by_key(facts: Iterable[AcceptedFact]) -> dict[tuple[str, str], int]:
    counts: dict[str, int] = {}
    numbers: dict[tuple[str, str], int] = {}
    for fact in facts:
        counts[fact.source_id] = counts.get(fact.source_id, 0) + 1
        numbers[(fact.source_id, fact.fact_id)] = counts[fact.source_id]
    return numbers


def compact_fact_note(
    fact: AcceptedFact,
    source_key: str,
    fact_number: int,
) -> str:
    if not source_key or fact_number < 1:
        return ""
    return f"({source_key}:{fact_number})"


def compact_fact_notes_in_text(text: str) -> tuple[str, ...]:
    notes: list[str] = []
    seen: set[str] = set()

    def add(citation: str) -> None:
        if citation not in seen:
            seen.add(citation)
            notes.append(citation)

    for citation in COMPACT_FACT_NOTE_RE.findall(text):
        add(citation)
    for match in _COMPACT_FACT_ANCHOR_REF_RE.finditer(text):
        add(f"(S{match.group('source')}:{match.group('number')})")
    return tuple(notes)


def fact_sort_key(fact: AcceptedFact) -> tuple[str, tuple[tuple[int, int | str], ...]]:
    return fact.source_id, natural_key(fact.fact_id)


def natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in re.split(r"(\d+)", value)
        if part
    )
