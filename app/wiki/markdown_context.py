"""LLM-oriented context rendering for generated wiki markdown."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .records import SourceRecord, WikiRecord
from .status import AcceptedFact
from .wiki_scope import wiki_description

DEFAULT_CONTEXT_FACT_LIMIT = 12

_SENSITIVE_SOURCE_TERMS = (
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

_SENSITIVE_FACT_PATTERNS = tuple(
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
class ContextFact:
    fact: AcceptedFact
    source: SourceRecord | None
    citation: str


@dataclass(frozen=True)
class ContextFacts:
    default: tuple[ContextFact, ...]
    restricted: tuple[ContextFact, ...]


def classify_context_facts(
    accepted_facts: Iterable[AcceptedFact],
    sources: Mapping[str, SourceRecord],
    citation_by_fact: Mapping[tuple[str, str], str],
) -> ContextFacts:
    """Split accepted facts into default-load and restricted context groups."""
    items = [
        ContextFact(
            fact=fact,
            source=sources.get(fact.source_id),
            citation=citation_by_fact.get((fact.source_id, fact.fact_id), ""),
        )
        for fact in accepted_facts
    ]
    restricted = tuple(item for item in items if _is_restricted(item))
    default = tuple(item for item in items if item not in restricted)
    return ContextFacts(default=default, restricted=restricted)


def render_llm_context_section(wiki: WikiRecord, facts: ContextFacts) -> str:
    """Return a compact context surface above the full fact ledger."""
    lines = ["## LLM Context", ""]
    description = wiki_description(wiki)
    if description:
        lines.extend(["### Scope", "", _inline_text(description), ""])

    lines.extend(["### Default Conversation Context", ""])
    if facts.default:
        visible = facts.default[:DEFAULT_CONTEXT_FACT_LIMIT]
        lines.extend(_fact_line(item) for item in visible)
        overflow = len(facts.default) - len(visible)
        if overflow:
            lines.append(
                f"- {overflow} additional non-restricted accepted fact(s) are listed below."
            )
    else:
        lines.append("_No non-restricted context facts yet._")

    if facts.restricted:
        lines.append(
            f"- {len(facts.restricted)} restricted accepted fact(s) are listed below, "
            "outside the default conversation context."
        )

    return "\n".join(lines).rstrip()


def _fact_line(item: ContextFact) -> str:
    suffix = f" {item.citation}" if item.citation else ""
    return f"- {_inline_text(item.fact.text)}{suffix}"


def _is_restricted(item: ContextFact) -> bool:
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
    if any(term in source_text for term in _SENSITIVE_SOURCE_TERMS):
        return True
    return any(pattern.search(item.fact.text) for pattern in _SENSITIVE_FACT_PATTERNS)


def _inline_text(value: str) -> str:
    text = " ".join(str(value).split())
    return text.replace("[[", r"\[\[").replace("]]", r"\]\]")
