"""Controlled SourceRecord repair helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .fingerprints import stable_digest
from .records import FactRecord, SourceRecord


def repair_source_record(
    source: SourceRecord,
    *,
    title: str,
    summary: str,
    document_date: str | None,
    source_type: str | None,
    fact_texts: Mapping[str, str],
    deleted_fact_ids: Iterable[str] = (),
    added_fact_texts: Iterable[str] = (),
    added_fact_provenance: Mapping[str, Any] | None = None,
    issue_texts: Mapping[int, str] | None = None,
    deleted_issue_indexes: Iterable[int] = (),
) -> SourceRecord:
    source_fact_ids = {fact.fact_id for fact in source.facts}
    unknown_fact_ids = sorted(set(fact_texts) - source_fact_ids)
    if unknown_fact_ids:
        raise ValueError(f"unknown fact id(s): {', '.join(unknown_fact_ids)}")

    delete_fact_ids = set(deleted_fact_ids)
    unknown_deleted = sorted(delete_fact_ids - source_fact_ids)
    if unknown_deleted:
        raise ValueError(f"unknown deleted fact id(s): {', '.join(unknown_deleted)}")

    facts: list[FactRecord] = []
    for fact in source.facts:
        if fact.fact_id in delete_fact_ids:
            continue
        text = fact_texts.get(fact.fact_id, fact.text).strip()
        if not text:
            raise ValueError(f"fact {fact.fact_id!r} text is required")
        provenance = dict(fact.provenance)
        signature = fact.fact_signature
        if text != fact.text:
            signature = repaired_fact_signature(
                source.source_id,
                fact.fact_id,
                text,
                provenance,
            )
        facts.append(
            FactRecord(
                fact_id=fact.fact_id,
                text=text,
                fact_signature=signature,
                provenance=provenance,
            )
        )

    used_fact_ids = {fact.fact_id for fact in facts}
    for text in added_fact_texts:
        text = text.strip()
        if not text:
            continue
        fact_id = next_repair_fact_id(used_fact_ids)
        provenance = dict(added_fact_provenance or {"repair": "source_repair"})
        facts.append(
            FactRecord(
                fact_id=fact_id,
                text=text,
                fact_signature=repaired_fact_signature(
                    source.source_id,
                    fact_id,
                    text,
                    provenance,
                ),
                provenance=provenance,
            )
        )
        used_fact_ids.add(fact_id)

    return SourceRecord(
        source_id=source.source_id,
        title=title or source.source_id,
        facts=tuple(facts),
        summary=summary,
        document_date=document_date,
        source_type=source_type,
        extraction_issues=_repair_issues(
            source.extraction_issues,
            issue_texts or {},
            set(deleted_issue_indexes),
        ),
    )


def repaired_fact_signature(
    source_id: str,
    fact_id: str,
    text: str,
    provenance: Mapping[str, Any],
) -> str:
    return stable_digest(
        {
            "version": 1,
            "kind": "source_repair_fact_signature",
            "source_id": source_id,
            "fact_id": fact_id,
            "text": text,
            "provenance": dict(provenance),
        }
    )


def next_repair_fact_id(used_fact_ids: set[str]) -> str:
    index = 1
    while True:
        fact_id = f"fact-repair-{index}"
        if fact_id not in used_fact_ids:
            return fact_id
        index += 1


def _repair_issues(
    current_issues: tuple[str, ...],
    issue_texts: Mapping[int, str],
    deleted_issue_indexes: set[int],
) -> tuple[str, ...]:
    _validate_issue_indexes_for_count(
        len(current_issues),
        tuple(issue_texts) + tuple(deleted_issue_indexes),
    )
    issues: list[str] = []
    for index, issue in enumerate(current_issues):
        if index in deleted_issue_indexes:
            continue
        text = issue_texts.get(index, issue).strip()
        if text:
            issues.append(text)
    return tuple(issues)


def _validate_issue_indexes_for_count(count: int, indexes: Iterable[int]) -> None:
    invalid = sorted(index for index in indexes if index < 0 or index >= count)
    if invalid:
        raise ValueError(
            "source repair references unknown issue index(es): "
            + ", ".join(str(index) for index in invalid)
        )
