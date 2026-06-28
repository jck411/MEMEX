"""Compact citation helpers for accepted wiki facts."""

from __future__ import annotations

import re
from typing import Iterable

from .status import AcceptedFact

_COMPACT_FACT_NOTE_TEXT = r"\(S\d+:\d+\)"
_COMPACT_FACT_LINK_TEXT = (
    rf"\[{_COMPACT_FACT_NOTE_TEXT}\]"
    r"\((?:#[A-Za-z0-9_.:-]+|[^)\s]*#memex-fact-[A-Za-z0-9_.:-]+)\)"
)
_COMPACT_FACT_TOKEN_TEXT = rf"(?:{_COMPACT_FACT_LINK_TEXT}|{_COMPACT_FACT_NOTE_TEXT})"

COMPACT_FACT_NOTE_RE = re.compile(_COMPACT_FACT_NOTE_TEXT)
COMPACT_FACT_NOTE_RUN_RE = re.compile(
    rf"{_COMPACT_FACT_TOKEN_TEXT}(?:[ \t]*{_COMPACT_FACT_TOKEN_TEXT})*"
)
_COMPACT_FACT_ANCHOR_REF_RE = re.compile(r"#memex-fact-s(?P<source>\d+)-(?P<number>\d+)")
_COMPACT_FACT_PARTS_RE = re.compile(r"\((?P<source>S\d+):(?P<number>\d+)\)")


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


def compact_fact_anchor(citation: str) -> str:
    anchor_id = compact_fact_anchor_id(citation)
    return f'<a id="{anchor_id}"></a>' if anchor_id else ""


def compact_fact_anchor_id(citation: str) -> str:
    if not COMPACT_FACT_NOTE_RE.fullmatch(citation.strip()):
        return ""
    value = citation.strip()[1:-1]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return f"memex-fact-{slug}" if slug else ""


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


def link_compact_fact_notes(text: str, citations: Iterable[str]) -> str:
    allowed = {citation for citation in citations if citation}
    if not allowed:
        return text

    def replace(match: re.Match[str]) -> str:
        run = match.group(0)
        found = COMPACT_FACT_NOTE_RE.findall(run)
        if not found or any(citation not in allowed for citation in found):
            return run
        return _linked_fact_note_run(found)

    return COMPACT_FACT_NOTE_RUN_RE.sub(replace, text)


def _linked_fact_note_run(citations: list[str]) -> str:
    groups: list[tuple[str, list[str]]] = []
    for citation in citations:
        parts = _COMPACT_FACT_PARTS_RE.fullmatch(citation)
        if parts is None:
            continue
        source = parts.group("source")
        number = parts.group("number")
        if groups and groups[-1][0] == source:
            groups[-1][1].append(number)
        else:
            groups.append((source, [number]))
    return "".join(_linked_fact_note_group(source, numbers) for source, numbers in groups)


def _linked_fact_note_group(source: str, numbers: list[str]) -> str:
    links = [
        f"[{label}](#{compact_fact_anchor_id(f'({source}:{number})')})"
        for label, number in _fact_note_group_labels(source, numbers)
    ]
    return f"({''.join(links)})"


def _fact_note_group_labels(source: str, numbers: list[str]) -> list[tuple[str, str]]:
    labels: list[tuple[str, str]] = []
    for index, number in enumerate(numbers):
        label = f"{source}:{number}" if index == 0 else f",{number}"
        labels.append((label, number))
    return labels


def fact_sort_key(fact: AcceptedFact) -> tuple[str, tuple[tuple[int, int | str], ...]]:
    return fact.source_id, natural_key(fact.fact_id)


def natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in re.split(r"(\d+)", value)
        if part
    )
