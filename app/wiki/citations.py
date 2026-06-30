"""Text helpers for generated wiki markdown."""

from __future__ import annotations

import re

from .status import AcceptedFact

def inline_text(value: object) -> str:
    text = " ".join(str(value).split())
    return text.replace("[[", r"\[\[").replace("]]", r"\]\]")


def fact_sort_key(fact: AcceptedFact) -> tuple[str, tuple[tuple[int, int | str], ...]]:
    return fact.source_id, natural_key(fact.fact_id)


def natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in re.split(r"(\d+)", value)
        if part
    )
