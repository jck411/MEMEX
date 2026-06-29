"""Text helpers for generated wiki markdown."""

from __future__ import annotations

import re

from .status import AcceptedFact

_COMPACT_FACT_NOTE_TEXT = r"\(S\d+:\d+\)"
COMPACT_FACT_NOTE_RE = re.compile(_COMPACT_FACT_NOTE_TEXT)
_COMPACT_FACT_ANCHOR_REF_RE = re.compile(r"#memex-fact-s(?P<source>\d+)-(?P<number>\d+)")


def inline_text(value: object) -> str:
    text = " ".join(str(value).split())
    return text.replace("[[", r"\[\[").replace("]]", r"\]\]")


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
