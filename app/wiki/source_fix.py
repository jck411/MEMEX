"""LLM-assisted extraction fixing via OpenRouter DeepSeek V4 Pro."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.request import urlopen

from .openrouter_client import (
    OPENROUTER_DEEPSEEK_V4_PRO_MODEL,
    chat_completion_text,
    post_openrouter_chat_completion,
    strip_json_fence,
)
from .records import SourceRecord
from .source_repair import repair_source_record

SOURCE_FIX_MODEL = OPENROUTER_DEEPSEEK_V4_PRO_MODEL
_SOURCE_FIX_TEXT_FIELDS = ("source_id", "title", "summary", "document_date", "source_type")

SOURCE_FIX_SYSTEM_PROMPT = """\
You fix editable extraction fields for MEMEX.

The user will give you an instruction and a current editable_source object.
Return a complete copy of editable_source with only the requested fixes applied.

Rules:
- Copy unchanged fields exactly.
- Do not add, remove, reorder, or rename facts.
- Preserve source_id and fact IDs exactly.
- Do not add, remove, reorder, or renumber extraction issues.
- Preserve extraction issue indexes exactly.
- Use empty strings for blank summary, document_date, or source_type.
- Return only the fixed editable_source JSON object.
"""

SOURCE_FIX_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        **{field_name: {"type": "string"} for field_name in _SOURCE_FIX_TEXT_FIELDS},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["fact_id", "text"],
                "additionalProperties": False,
            },
        },
        "extraction_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue_index": {"type": "integer"},
                    "message": {"type": "string"},
                },
                "required": ["issue_index", "message"],
                "additionalProperties": False,
            },
        },
    },
    "required": [*_SOURCE_FIX_TEXT_FIELDS, "facts", "extraction_issues"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class FactDiff:
    fact_id: str
    old_text: str
    new_text: str


@dataclass(frozen=True)
class MetadataDiff:
    field: str
    old_value: str
    new_value: str


@dataclass(frozen=True)
class IssueDiff:
    issue_index: int
    old_message: str
    new_message: str


@dataclass(frozen=True)
class SourceFixResult:
    source: SourceRecord
    fact_diffs: tuple[FactDiff, ...]
    metadata_diffs: tuple[MetadataDiff, ...]
    issue_diffs: tuple[IssueDiff, ...] = ()
    usage: Mapping[str, Any] = field(default_factory=dict)
    model: str = SOURCE_FIX_MODEL

    @property
    def changed(self) -> bool:
        return bool(self.fact_diffs or self.metadata_diffs or self.issue_diffs)

    @property
    def change_count(self) -> int:
        return len(self.fact_diffs) + len(self.metadata_diffs) + len(self.issue_diffs)


def fix_source_extraction(
    source: SourceRecord,
    instruction: str,
    api_key: str,
    *,
    model: str = SOURCE_FIX_MODEL,
    opener: Callable[..., Any] = urlopen,
    max_tokens: int = 4096,
) -> SourceFixResult:
    """Call the LLM to fix editable extraction fields according to *instruction*."""
    if not instruction.strip():
        raise ValueError("fix instruction is required")

    data = post_openrouter_chat_completion(
        api_key,
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SOURCE_FIX_SYSTEM_PROMPT},
                {"role": "user", "content": _render_fix_prompt(source, instruction)},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "provider": {"require_parameters": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "memex_source_fix",
                    "strict": True,
                    "schema": SOURCE_FIX_RESPONSE_SCHEMA,
                },
            },
        },
        opener=opener,
    )
    raw = strip_json_fence(chat_completion_text(data, task="source-fix"))
    payload = _parse_fix_response(raw, source)
    usage = data.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    return _apply_fix(source, payload, usage, model)


def _render_fix_prompt(source: SourceRecord, instruction: str) -> str:
    return json.dumps(
        {
            "instruction": instruction,
            "editable_source": _editable_source_payload(source),
        },
        indent=2,
    )


def _editable_source_payload(source: SourceRecord) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "title": source.title,
        "summary": source.summary,
        "document_date": source.document_date or "",
        "source_type": source.source_type or "",
        "facts": [{"fact_id": fact.fact_id, "text": fact.text} for fact in source.facts],
        "extraction_issues": [
            {"issue_index": index, "message": message}
            for index, message in enumerate(source.extraction_issues)
        ],
    }


def _parse_fix_response(raw: str, source: SourceRecord) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"source-fix response is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("source-fix response must be a JSON object")
    _validate_editable_source_payload(payload, source)
    return payload


def _validate_editable_source_payload(
    payload: Mapping[str, Any],
    source: SourceRecord,
) -> None:
    for field_name in _SOURCE_FIX_TEXT_FIELDS:
        if not isinstance(payload.get(field_name), str):
            raise ValueError(f"source-fix response {field_name!r} must be a string")
    if payload["source_id"] != source.source_id:
        raise ValueError("source_id cannot be changed during source fix")
    _validate_fact_payloads(payload.get("facts"), source)
    _validate_issue_payloads(payload.get("extraction_issues"), source)


def _validate_fact_payloads(value: Any, source: SourceRecord) -> None:
    if not isinstance(value, list):
        raise ValueError("source-fix response 'facts' must be a list")
    fact_ids: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("source-fix response fact must be an object")
        if not isinstance(item.get("fact_id"), str) or not isinstance(item.get("text"), str):
            raise ValueError("source-fix response fact fields must be strings")
        fact_ids.append(item["fact_id"])
    if fact_ids != [fact.fact_id for fact in source.facts]:
        raise ValueError("source-fix response fact IDs must match the source facts")


def _validate_issue_payloads(value: Any, source: SourceRecord) -> None:
    if not isinstance(value, list):
        raise ValueError("source-fix response 'extraction_issues' must be a list")
    issue_indexes: list[int] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("source-fix response extraction issue must be an object")
        issue_index = item.get("issue_index")
        if type(issue_index) is not int or not isinstance(item.get("message"), str):
            raise ValueError("source-fix response extraction issue fields are invalid")
        issue_indexes.append(issue_index)
    if issue_indexes != list(range(len(source.extraction_issues))):
        raise ValueError("source-fix response issue indexes must match the source issues")


def _apply_fix(
    source: SourceRecord,
    payload: Mapping[str, Any],
    usage: Mapping[str, Any],
    model: str,
) -> SourceFixResult:
    repaired = repair_source_record(
        source,
        title=payload["title"].strip() or source.source_id,
        summary=payload["summary"].strip(),
        document_date=payload["document_date"].strip() or None,
        source_type=payload["source_type"].strip() or None,
        fact_texts={item["fact_id"]: item["text"] for item in payload["facts"]},
        issue_texts={item["issue_index"]: item["message"] for item in payload["extraction_issues"]},
    )
    return SourceFixResult(
        source=repaired,
        fact_diffs=_fact_diffs(source, repaired),
        metadata_diffs=_metadata_diffs(source, repaired),
        issue_diffs=_issue_diffs(source, repaired),
        usage=usage,
        model=model,
    )


def _fact_diffs(source: SourceRecord, repaired: SourceRecord) -> tuple[FactDiff, ...]:
    return tuple(
        FactDiff(old.fact_id, old.text, new.text)
        for old, new in zip(source.facts, repaired.facts, strict=True)
        if old.text != new.text
    )


def _metadata_diffs(
    source: SourceRecord,
    repaired: SourceRecord,
) -> tuple[MetadataDiff, ...]:
    values = (
        ("title", source.title, repaired.title),
        ("summary", source.summary, repaired.summary),
        ("document_date", source.document_date or "", repaired.document_date or ""),
        ("source_type", source.source_type or "", repaired.source_type or ""),
    )
    return tuple(MetadataDiff(field, old, new) for field, old, new in values if old != new)


def _issue_diffs(source: SourceRecord, repaired: SourceRecord) -> tuple[IssueDiff, ...]:
    return tuple(
        IssueDiff(index, old, new)
        for index, (old, new) in enumerate(
            zip(source.extraction_issues, repaired.extraction_issues, strict=True)
        )
        if old != new
    )
