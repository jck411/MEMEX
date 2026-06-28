"""Accepted fact visibility grouping for generated wiki markdown."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .records import SourceRecord
from .status import AcceptedFact

_RESTRICTED_SOURCE_TERMS = (
    "passport",
    "driver license",
    "driving license",
    "identity document",
    "social security",
    "tax return",
    "w-2",
    "1099",
    "bank statement",
    "medical record",
    "insurance card",
)

_RESTRICTED_FACT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(passport|driver license|driving license)\s+(number|no\.?)\b",
        r"\blicense number\b",
        r"\b(personal number|pesel|ssn|social security number|taxpayer id|tin)\b",
        r"\b(date of birth|dob|place of birth|born on)\b",
        r"\b(address is|home address|resides at|lives at)\b",
        r"\b(contact email|email address|email is|phone number|telephone)\b",
        r"\b(sex is|gender is|height is|weight is)\b",
        r"\b(account number|routing number|credit card|debit card)\b",
        r"\bmedical record\b",
    )
)


@dataclass(frozen=True)
class VisibleFact:
    fact: AcceptedFact
    source: SourceRecord | None
    citation: str


@dataclass(frozen=True)
class FactGroups:
    general: tuple[VisibleFact, ...]
    restricted: tuple[VisibleFact, ...]


def group_visible_facts(
    accepted_facts: Iterable[AcceptedFact],
    sources: Mapping[str, SourceRecord],
    citation_by_fact: Mapping[tuple[str, str], str],
) -> FactGroups:
    """Split accepted facts into general wiki facts and restricted ledger facts."""
    items = tuple(
        VisibleFact(
            fact=fact,
            source=sources.get(fact.source_id),
            citation=citation_by_fact.get((fact.source_id, fact.fact_id), ""),
        )
        for fact in accepted_facts
    )
    restricted = tuple(item for item in items if _is_restricted(item))
    general = tuple(item for item in items if item not in restricted)
    return FactGroups(general=general, restricted=restricted)


def _is_restricted(item: VisibleFact) -> bool:
    source = item.source
    source_text = " ".join(
        part
        for part in (
            source.source_id if source else item.fact.source_id,
            source.title if source else "",
            source.source_type if source else "",
        )
        if part
    ).lower()
    if any(term in source_text for term in _RESTRICTED_SOURCE_TERMS):
        return True
    return any(pattern.search(item.fact.text) for pattern in _RESTRICTED_FACT_PATTERNS)
