"""SourceRecord validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .records import FactRecord, SourceRecord
from .source_validation_io import (
    add_issue,
    location,
    read_required_json_object,
    reject_unknown_keys,
    string_sequence,
)
from .source_validation_types import SourceValidationIssue
from .storage import SOURCES_DIRNAME, source_record_path

_SOURCE_KEYS = {
    "source_id",
    "title",
    "facts",
    "summary",
    "document_date",
    "source_type",
    "extraction_issues",
}
_FACT_KEYS = {"fact_id", "text", "fact_signature", "provenance"}


def load_sources(
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> dict[str, SourceRecord]:
    sources_dir = data_root / SOURCES_DIRNAME
    if not sources_dir.exists():
        return {}
    sources: dict[str, SourceRecord] = {}
    source_locations: dict[str, Path] = {}
    for path in sorted(sources_dir.glob("*.json")):
        payload = read_required_json_object(path, data_root, issues)
        if payload is None:
            continue
        _validate_source_payload_shape(payload, path, data_root, issues)
        try:
            source = SourceRecord.from_dict(payload)
        except Exception as error:
            add_issue(issues, data_root, path, f"invalid source record: {error}")
            continue
        _validate_source_path(source, path, data_root, issues)
        if source.source_id in sources:
            add_issue(
                issues,
                data_root,
                path,
                f"duplicate source_id {source.source_id!r}; "
                f"first seen in {location(source_locations[source.source_id], data_root)}",
            )
            continue
        sources[source.source_id] = source
        source_locations[source.source_id] = path
        _validate_source_record(source, path, data_root, issues)
    return sources


def _validate_source_payload_shape(
    payload: Mapping[str, Any],
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    reject_unknown_keys(payload, _SOURCE_KEYS, data_root, path, "source record", issues)
    facts = payload.get("facts", [])
    if not isinstance(facts, list):
        return
    for index, fact in enumerate(facts):
        if isinstance(fact, Mapping):
            reject_unknown_keys(
                fact,
                _FACT_KEYS,
                data_root,
                path,
                f"facts[{index}]",
                issues,
            )


def _validate_source_path(
    source: SourceRecord,
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    expected_path = source_record_path(data_root, source.source_id)
    if path != expected_path:
        add_issue(
            issues,
            data_root,
            path,
            f"source_id {source.source_id!r} belongs in {expected_path.name}",
        )


def _validate_source_record(
    source: SourceRecord,
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    for fact in source.facts:
        _validate_fact_evidence(source.source_id, fact, path, data_root, issues)


def _validate_fact_evidence(
    source_id: str,
    fact: FactRecord,
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    evidence_ids_value = fact.provenance.get("evidence_ids")
    if evidence_ids_value is None:
        return

    label = f"source {source_id!r} fact {fact.fact_id!r}"
    evidence_ids = string_sequence(
        evidence_ids_value,
        data_root,
        path,
        f"{label} provenance.evidence_ids",
        issues,
    )
    evidence_value = fact.provenance.get("evidence")
    if evidence_value is None:
        if evidence_ids:
            add_issue(
                issues,
                data_root,
                path,
                f"{label} has evidence_ids but no provenance.evidence list",
            )
        return
    if not isinstance(evidence_value, (list, tuple)):
        add_issue(
            issues,
            data_root,
            path,
            f"{label} provenance.evidence must be an array",
        )
        return

    evidence_by_id = _evidence_by_id(label, evidence_value, path, data_root, issues)
    for evidence_id in evidence_ids:
        if evidence_id not in evidence_by_id:
            add_issue(
                issues,
                data_root,
                path,
                f"{label} references unknown evidence {evidence_id!r}",
            )


def _evidence_by_id(
    label: str,
    evidence_items: tuple[Any, ...] | list[Any],
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> dict[str, Mapping[str, Any]]:
    evidence_by_id: dict[str, Mapping[str, Any]] = {}
    for index, evidence in enumerate(evidence_items):
        if not isinstance(evidence, Mapping):
            add_issue(
                issues,
                data_root,
                path,
                f"{label} provenance.evidence[{index}] must be an object",
            )
            continue
        evidence_id = evidence.get("id")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            add_issue(
                issues,
                data_root,
                path,
                f"{label} provenance.evidence[{index}].id must be a non-empty string",
            )
            continue
        if evidence_id in evidence_by_id:
            add_issue(
                issues,
                data_root,
                path,
                f"{label} has duplicate evidence id {evidence_id!r}",
            )
            continue
        evidence_by_id[evidence_id] = evidence
        _validate_evidence_shape(label, index, evidence, path, data_root, issues)
    return evidence_by_id


def _validate_evidence_shape(
    label: str,
    index: int,
    evidence: Mapping[str, Any],
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    for key in ("quote", "source_channel", "locator"):
        if key in evidence and not isinstance(evidence[key], str):
            add_issue(
                issues,
                data_root,
                path,
                f"{label} provenance.evidence[{index}].{key} must be a string",
            )
    if "page" in evidence and not isinstance(evidence["page"], int):
        add_issue(
            issues,
            data_root,
            path,
            f"{label} provenance.evidence[{index}].page must be an integer",
        )
