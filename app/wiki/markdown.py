"""Markdown rendering for the generated wiki fact audit appendix."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .fact_visibility import VisibleFact, group_visible_facts
from .ledger import WikiLedger
from .records import FactRecord, SourceRecord, WikiRecord, source_index
from .status import AcceptedFact, accepted_facts_for_wiki
from .wiki_scope import wiki_description

FACTS_START = "<!-- MEMEX:FACTS:START -->"
FACTS_END = "<!-- MEMEX:FACTS:END -->"


def _inline_text(value: str) -> str:
    text = " ".join(str(value).split())
    return text.replace("[[", r"\[\[").replace("]]", r"\]\]")


def render_fact_audit_section(
    wiki: WikiRecord,
    accepted_facts: Iterable[AcceptedFact],
    sources: Iterable[SourceRecord] | Mapping[str, SourceRecord] = (),
) -> str:
    facts = sorted(accepted_facts, key=_fact_sort_key)
    source_map = source_index(sources)
    fact_records = _fact_records_by_key(source_map)
    source_keys = _source_keys_by_id(facts)
    citation_by_fact = {
        (fact.source_id, fact.fact_id): _compact_fact_note(
            fact,
            fact_records.get((fact.source_id, fact.fact_id)),
            source_keys.get(fact.source_id, ""),
        )
        for fact in facts
    }
    fact_groups = group_visible_facts(facts, source_map, citation_by_fact)
    lines = [FACTS_START, "## Accepted Facts", ""]
    description = wiki_description(wiki)
    if description:
        lines.append(f"**Wiki description:** {_inline_text(description)}")
        lines.append("")
    if not facts:
        lines.append("_No accepted facts yet._")
    elif fact_groups.restricted:
        lines.extend(["### General Accepted Facts", ""])
        if fact_groups.general:
            _append_fact_lines(lines, fact_groups.general, source_map)
        else:
            lines.extend(["_No general accepted facts._", ""])
        lines.extend(
            [
                "### Restricted Accepted Facts",
                "",
                "_Accepted facts excluded from generated briefs unless explicitly requested._",
                "",
            ]
        )
        _append_fact_lines(lines, fact_groups.restricted, source_map)
    else:
        _append_fact_lines(lines, fact_groups.general, source_map)
    if facts:
        lines.extend(_references_section(facts, source_map, fact_records, source_keys))
    if lines[-1] == "":
        lines.pop()
    lines.append(FACTS_END)
    return "\n".join(lines)


def _append_fact_lines(
    lines: list[str],
    facts: Iterable[VisibleFact],
    sources: Mapping[str, SourceRecord],
) -> None:
    for item in facts:
        fact = item.fact
        suffix = f" {item.citation}" if item.citation else ""
        lines.append(f"- {_inline_text(fact.text)}{suffix}")
        lines.append(f"  - Source: {_source_reference_label(fact.source_id, sources)}")
        if fact.decision.reason:
            lines.append(f"  - Review: {_inline_text(fact.decision.reason)}")
        lines.append("")


def replace_fact_audit_section(existing_markdown: str, section: str) -> str:
    start = existing_markdown.find(FACTS_START)
    end = existing_markdown.find(FACTS_END)
    if start == -1 and end == -1:
        if not existing_markdown.strip():
            return section + "\n"
        return existing_markdown.rstrip() + "\n\n" + section + "\n"
    if start == -1 or end == -1 or end < start:
        raise ValueError("existing markdown has incomplete MEMEX facts markers")

    end += len(FACTS_END)
    prefix = existing_markdown[:start].rstrip()
    suffix = existing_markdown[end:].lstrip()
    pieces = [piece for piece in (prefix, section, suffix) if piece]
    return "\n\n".join(pieces) + "\n"


def build_wiki_markdown(
    wiki: WikiRecord,
    ledger: WikiLedger,
    sources: Iterable[SourceRecord] | Mapping[str, SourceRecord],
    existing_markdown: str = "",
) -> str:
    source_map = source_index(sources)
    accepted_facts = accepted_facts_for_wiki(wiki, ledger, source_map)
    section = render_fact_audit_section(wiki, accepted_facts, source_map)
    if existing_markdown.strip():
        return replace_fact_audit_section(existing_markdown, section)
    return f"# {wiki.title}\n\n{section}\n"


def _fact_records_by_key(
    sources: Mapping[str, SourceRecord],
) -> dict[tuple[str, str], FactRecord]:
    records: dict[tuple[str, str], FactRecord] = {}
    for source_id, source in sources.items():
        for fact_id, fact in source.fact_by_id().items():
            records[(source_id, fact_id)] = fact
    return records


def _source_reference_label(
    source_id: str,
    sources: Mapping[str, SourceRecord],
) -> str:
    title = _inline_text(sources[source_id].title) if source_id in sources else ""
    if title and title != source_id:
        return f"{title} (`{source_id}`)"
    return f"`{source_id}`"


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
            citation = _compact_fact_note(fact, fact_record, source_key)
            prefix = f"{citation} " if citation else ""
            pieces = [f"fact `{_inline_text(fact.fact_id)}`"]
            evidence_ids = _evidence_ids(fact_record)
            if evidence_ids:
                pieces.append(
                    "evidence " + ", ".join(f"`{_inline_text(item)}`" for item in evidence_ids)
                )
            lines.append(f"- {prefix}{' ; '.join(pieces)}: {_inline_text(fact.text)}")
        lines.append("")
    return lines


def _source_keys_by_id(facts: list[AcceptedFact]) -> dict[str, str]:
    source_ids: list[str] = []
    for fact in facts:
        if fact.source_id not in source_ids:
            source_ids.append(fact.source_id)
    return {source_id: f"S{index}" for index, source_id in enumerate(source_ids, start=1)}


def _fact_sort_key(fact: AcceptedFact) -> tuple[str, tuple[tuple[int, int | str], ...]]:
    return fact.source_id, _natural_key(fact.fact_id)


def _natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in re.split(r"(\d+)", value)
        if part
    )


def _compact_fact_note(
    fact: AcceptedFact,
    fact_record: FactRecord | None,
    source_key: str,
) -> str:
    ids = _unique([*_evidence_ids(fact_record), fact.fact_id])
    if not ids:
        return ""
    prefix = f"{source_key}:" if source_key else ""
    return f"({prefix}{','.join(ids)})"


def _evidence_ids(fact_record: FactRecord | None) -> list[str]:
    if fact_record is None:
        return []
    provenance = fact_record.provenance
    explicit_ids = _string_list(provenance.get("evidence_ids"))
    if explicit_ids:
        return explicit_ids
    return _unique(
        _text(item.get("id"))
        for item in provenance.get("evidence", ())
        if isinstance(item, Mapping)
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [_text(item) for item in value if _text(item)]


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
