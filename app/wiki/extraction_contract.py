"""Shared JSON contract for LLM source extraction."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

EXTRACTION_SCHEMA_NAME = "memex_wiki_prep_extraction"

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "MEMEX Wiki Prep Extraction",
    "type": "object",
    "properties": {
        "source_id": {
            "type": "string",
            "description": "Copy the manifest source ID exactly.",
        },
        "document": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Visible or stated source title. Use literal 'unknown' when no title is visible or stated.",
                },
                "type": {
                    "type": "string",
                    "description": "Source document type. Use literal 'unknown' when the type cannot be determined from the source, manifest, or source scan.",
                },
                "date": {
                    "type": "string",
                    "description": "Date visible or stated in the source. Use ISO format when clear. Use literal 'unknown' when no source date is visible or stated.",
                },
                "language": {
                    "type": "string",
                    "description": "Primary language of the source. Use literal 'unknown' when it cannot be determined.",
                },
            },
            "required": ["title", "type", "date", "language"],
            "additionalProperties": False,
        },
        "summary": {"type": "string"},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {
                        "type": "string",
                        "description": "Source-grounded fact text. Do not guess; omit the fact when the value would be unknown.",
                    },
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["id", "text", "evidence_ids"],
                "additionalProperties": False,
            },
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "quote": {"type": "string"},
                    "source_channel": {
                        "type": "string",
                        "enum": [
                            "document_visible",
                            "ocr_text",
                            "pdf_text",
                            "docx_text",
                            "exif",
                            "file_metadata",
                            "source_scan",
                            "unknown",
                        ],
                        "description": "One of document_visible, ocr_text, pdf_text, docx_text, exif, file_metadata, source_scan, or unknown.",
                    },
                    "page": {"type": "integer"},
                    "locator": {"type": "string"},
                },
                "required": ["id", "quote", "source_channel", "page", "locator"],
                "additionalProperties": False,
            },
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "message": {"type": "string"},
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["id", "message", "evidence_ids"],
                "additionalProperties": False,
            },
        },
        "run": {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "model": {"type": "string"},
                "prompt": {"type": "string"},
                "schema": {"type": "string"},
                "extracted_at": {"type": "string"},
            },
            "required": ["provider", "model", "prompt", "schema", "extracted_at"],
            "additionalProperties": True,
        },
    },
    "required": [
        "source_id",
        "document",
        "summary",
        "facts",
        "evidence",
        "issues",
        "run",
    ],
    "additionalProperties": False,
}


def extraction_json_schema() -> dict[str, Any]:
    return deepcopy(EXTRACTION_JSON_SCHEMA)


def extraction_model_json_schema() -> dict[str, Any]:
    schema = extraction_json_schema()
    schema.get("properties", {}).pop("run", None)
    schema["required"] = [field for field in schema.get("required", ()) if field != "run"]
    return schema


def provider_extraction_json_schema(
    *,
    remove_additional_properties: bool = False,
) -> dict[str, Any]:
    return _strip_schema_metadata(
        extraction_model_json_schema(),
        remove_additional_properties=remove_additional_properties,
    )


def openai_extraction_text_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": EXTRACTION_SCHEMA_NAME,
        "strict": True,
        "schema": provider_extraction_json_schema(),
    }


def anthropic_extraction_output_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "schema": provider_extraction_json_schema(),
    }


def _strip_schema_metadata(
    value: Any,
    *,
    remove_additional_properties: bool,
) -> Any:
    if isinstance(value, list):
        return [
            _strip_schema_metadata(
                item,
                remove_additional_properties=remove_additional_properties,
            )
            for item in value
        ]
    if not isinstance(value, dict):
        return value
    removed = {"$schema"}
    if remove_additional_properties:
        removed.add("additionalProperties")
    return {
        key: _strip_schema_metadata(
            item,
            remove_additional_properties=remove_additional_properties,
        )
        for key, item in value.items()
        if key not in removed and not (key == "title" and isinstance(item, str))
    }
