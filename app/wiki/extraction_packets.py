"""Validation and V2 normalization for MEMEX extraction packets."""

from __future__ import annotations

from typing import Any, Mapping

from .extraction_contract import EXTRACTION_SCHEMA_NAME
from .fingerprints import stable_digest
from .records import FactRecord, SourceRecord

LLM_EXTRACTOR_VERSION = "llm-v1"

SOURCE_CHANNELS = {
    "document_visible",
    "ocr_text",
    "pdf_text",
    "docx_text",
    "exif",
    "file_metadata",
    "source_scan",
    "unknown",
}

_MODEL_PACKET_KEYS = {"source_id", "document", "summary", "facts", "evidence", "issues"}
_STORED_PACKET_KEYS = _MODEL_PACKET_KEYS | {"run"}
_DOCUMENT_KEYS = {"title", "type", "date", "language"}
_FACT_KEYS = {"id", "text", "evidence_ids"}
_EVIDENCE_KEYS = {"id", "quote", "source_channel", "page", "locator"}
_ISSUE_KEYS = {"id", "message", "evidence_ids"}
_RUN_KEYS = {"provider", "model", "prompt", "schema", "extracted_at"}


class ExtractionPacketError(ValueError):
    """Raised when an LLM extraction packet is malformed."""


def validate_extraction_packet(
    packet: Mapping[str, Any],
    *,
    expected_source_id: str = "",
    require_run: bool = True,
) -> None:
    payload = _mapping(packet, "extraction")
    required = _STORED_PACKET_KEYS if require_run else _MODEL_PACKET_KEYS
    _require_keys(payload, required, "extraction")
    _reject_unknown(payload, required, "extraction")
    source_id = _string(payload["source_id"], "source_id")
    if expected_source_id and source_id != expected_source_id:
        raise ExtractionPacketError(
            f"extraction source_id {source_id!r} does not match {expected_source_id!r}"
        )
    _validate_document(payload["document"])
    evidence_ids = _validate_evidence(payload["evidence"])
    _validate_facts(payload["facts"], evidence_ids)
    _validate_issues(payload["issues"], evidence_ids)
    if require_run:
        _validate_run(payload["run"])


def source_record_from_extraction_packet(
    packet: Mapping[str, Any],
    *,
    expected_source_id: str = "",
    require_run: bool = True,
) -> SourceRecord:
    validate_extraction_packet(
        packet,
        expected_source_id=expected_source_id,
        require_run=require_run,
    )
    document = packet["document"]
    evidence_by_id = {item["id"]: dict(item) for item in packet["evidence"]}
    facts = tuple(
        FactRecord(
            fact_id=fact["id"],
            text=fact["text"],
            fact_signature=_fact_signature(packet, fact, evidence_by_id),
            provenance=_fact_provenance(packet, fact, evidence_by_id),
        )
        for fact in packet["facts"]
    )
    return SourceRecord(
        source_id=packet["source_id"],
        title=_known_or_empty(document["title"]) or packet["source_id"],
        facts=facts,
        summary=_known_or_empty(packet["summary"]),
        document_date=_known_or_none(document["date"]),
        source_type=_known_or_none(document["type"]),
        extraction_issues=tuple(issue["message"] for issue in packet["issues"]),
    )


def add_run_metadata(
    packet: Mapping[str, Any],
    *,
    provider: str,
    model: str,
    prompt: str,
    extracted_at: str,
    usage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(packet)
    payload["run"] = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "schema": EXTRACTION_SCHEMA_NAME,
        "extracted_at": extracted_at,
    }
    if usage is not None:
        payload["run"]["usage"] = dict(usage)
    return payload


def _validate_document(value: Any) -> None:
    document = _mapping(value, "document")
    _require_keys(document, _DOCUMENT_KEYS, "document")
    _reject_unknown(document, _DOCUMENT_KEYS, "document")
    for key in _DOCUMENT_KEYS:
        _string(document[key], f"document.{key}", allow_empty=True)


def _validate_evidence(value: Any) -> set[str]:
    evidence_ids: set[str] = set()
    for index, item in enumerate(_array(value, "evidence")):
        evidence = _mapping(item, f"evidence[{index}]")
        _require_keys(evidence, _EVIDENCE_KEYS, f"evidence[{index}]")
        _reject_unknown(evidence, _EVIDENCE_KEYS, f"evidence[{index}]")
        evidence_id = _unique_id(evidence["id"], evidence_ids, f"evidence[{index}].id")
        _string(evidence["quote"], f"evidence[{index}].quote", allow_empty=True)
        channel = _string(evidence["source_channel"], f"evidence[{index}].source_channel")
        if channel not in SOURCE_CHANNELS:
            raise ExtractionPacketError(f"unknown evidence source_channel {channel!r}")
        if not isinstance(evidence["page"], int):
            raise ExtractionPacketError(f"evidence[{index}].page must be an integer")
        _string(evidence["locator"], f"evidence[{index}].locator", allow_empty=True)
        evidence_ids.add(evidence_id)
    return evidence_ids


def _validate_facts(value: Any, evidence_ids: set[str]) -> None:
    fact_ids: set[str] = set()
    for index, item in enumerate(_array(value, "facts")):
        fact = _mapping(item, f"facts[{index}]")
        _require_keys(fact, _FACT_KEYS, f"facts[{index}]")
        _reject_unknown(fact, _FACT_KEYS, f"facts[{index}]")
        fact_ids.add(_unique_id(fact["id"], fact_ids, f"facts[{index}].id"))
        _string(fact["text"], f"facts[{index}].text")
        _validate_evidence_refs(fact["evidence_ids"], evidence_ids, f"facts[{index}]")


def _validate_issues(value: Any, evidence_ids: set[str]) -> None:
    issue_ids: set[str] = set()
    for index, item in enumerate(_array(value, "issues")):
        issue = _mapping(item, f"issues[{index}]")
        _require_keys(issue, _ISSUE_KEYS, f"issues[{index}]")
        _reject_unknown(issue, _ISSUE_KEYS, f"issues[{index}]")
        issue_ids.add(_unique_id(issue["id"], issue_ids, f"issues[{index}].id"))
        _string(issue["message"], f"issues[{index}].message")
        _validate_evidence_refs(issue["evidence_ids"], evidence_ids, f"issues[{index}]")


def _validate_run(value: Any) -> None:
    run = _mapping(value, "run")
    _require_keys(run, _RUN_KEYS, "run")
    for key in _RUN_KEYS:
        _string(run[key], f"run.{key}")


def _fact_signature(
    packet: Mapping[str, Any],
    fact: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    return stable_digest(
        {
            "version": 1,
            "kind": "llm_extraction_fact_signature",
            "schema": EXTRACTION_SCHEMA_NAME,
            "source_id": packet["source_id"],
            "text": fact["text"],
            "evidence": [
                evidence_by_id[evidence_id]
                for evidence_id in fact["evidence_ids"]
                if evidence_id in evidence_by_id
            ],
        }
    )


def _fact_provenance(
    packet: Mapping[str, Any],
    fact: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "extractor": LLM_EXTRACTOR_VERSION,
        "schema": EXTRACTION_SCHEMA_NAME,
        "evidence_ids": list(fact["evidence_ids"]),
        "evidence": [
            dict(evidence_by_id[evidence_id])
            for evidence_id in fact["evidence_ids"]
            if evidence_id in evidence_by_id
        ],
        "document": dict(packet["document"]),
    }
    return provenance


def _validate_evidence_refs(value: Any, evidence_ids: set[str], label: str) -> None:
    for evidence_id in _string_array(value, f"{label}.evidence_ids", allow_empty=True):
        if evidence_id not in evidence_ids:
            raise ExtractionPacketError(f"{label} references unknown evidence {evidence_id!r}")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExtractionPacketError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ExtractionPacketError(f"{label} must be an array")
    return value


def _string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ExtractionPacketError(f"{label} must be a string")
    if not allow_empty and not value.strip():
        raise ExtractionPacketError(f"{label} must be a non-empty string")
    return value


def _string_array(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    items = _array(value, label)
    for index, item in enumerate(items):
        _string(item, f"{label}[{index}]", allow_empty=allow_empty)
    return items


def _unique_id(value: Any, seen: set[str], label: str) -> str:
    item_id = _string(value, label)
    if item_id in seen:
        raise ExtractionPacketError(f"duplicate {label} {item_id!r}")
    return item_id


def _require_keys(payload: Mapping[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(keys - set(payload))
    if missing:
        raise ExtractionPacketError(f"{label} missing required key(s): {', '.join(missing)}")


def _reject_unknown(payload: Mapping[str, Any], keys: set[str], label: str) -> None:
    unknown = sorted(set(payload) - keys)
    if unknown:
        raise ExtractionPacketError(f"{label} has unknown key(s): {', '.join(unknown)}")


def _known_or_empty(value: str) -> str:
    text = value.strip()
    return "" if text.lower() == "unknown" else text


def _known_or_none(value: str) -> str | None:
    text = value.strip()
    return None if text.lower() in {"", "unknown"} else text
