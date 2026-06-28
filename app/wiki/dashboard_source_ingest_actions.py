"""Dashboard source ingest actions."""

from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory

from .dashboard_action_types import SourceExtractionRunner
from .dashboard_action_urls import dashboard_location
from .dashboard_forms import (
    DashboardForm,
    source_id_from_filename,
    source_id_from_text,
)
from .source_extraction import (
    SourceExtractionJob,
    SourceExtractionWorkflowResult,
)
from .workflows import WikiWorkspace
from .workspace_queries import source_record_exists


def apply_upload(
    workspace: WikiWorkspace,
    form: DashboardForm,
    source_extractor: SourceExtractionRunner | None,
    extraction_model_spec: str,
) -> str:
    if source_extractor is None:
        raise ValueError("source extraction is not configured")
    upload = form.file("source_file")
    if upload is None or not upload.data:
        raise ValueError("source file is required")
    model_spec = form.first("model_spec").strip() or extraction_model_spec
    allow_duplicate = form.flag("allow_duplicate")
    source_id = _upload_source_id(
        workspace,
        source_id_from_filename(upload.file_name),
        model_spec,
        allow_duplicate=allow_duplicate,
    )
    with TemporaryDirectory(prefix="memex-upload-") as temp_dir:
        path = Path(temp_dir) / upload.file_name
        path.write_bytes(upload.data)
        result = source_extractor(
            SourceExtractionJob(
                source_id=source_id,
                path=path,
                model_spec=model_spec,
                source_kind="file",
                mime_type=upload.content_type,
                allow_duplicate=allow_duplicate,
            )
        )
    return dashboard_location(_upload_result_message(upload.file_name, result))


def apply_text_source(
    workspace: WikiWorkspace,
    form: DashboardForm,
    source_extractor: SourceExtractionRunner | None,
    extraction_model_spec: str,
) -> str:
    if source_extractor is None:
        raise ValueError("source extraction is not configured")
    text = form.first("source_text")
    if not text.strip():
        raise ValueError("text source is required")
    title = form.first("text_title").strip()
    model_spec = form.first("model_spec").strip() or extraction_model_spec
    allow_duplicate = form.flag("allow_duplicate")
    source_id = _text_source_id(
        workspace,
        source_id_from_text(title, text),
        model_spec,
        allow_duplicate=allow_duplicate,
    )
    with TemporaryDirectory(prefix="memex-text-source-") as temp_dir:
        path = Path(temp_dir) / f"{source_id}.txt"
        path.write_text(text, encoding="utf-8")
        result = source_extractor(
            SourceExtractionJob(
                source_id=source_id,
                path=path,
                title=title,
                source_type="text",
                model_spec=model_spec,
                source_kind="typed_text",
                mime_type="text/plain",
                allow_duplicate=allow_duplicate,
            )
        )
    return dashboard_location(_text_result_message(result))


def _upload_result_message(
    file_name: str,
    result: SourceExtractionWorkflowResult,
) -> str:
    if result.duplicate:
        return (
            f"uploaded {file_name}; byte-identical source already exists as "
            f"{result.source.source_id}"
        )
    return (
        f"uploaded {file_name}; extracted {result.source.source_id} "
        f"({len(result.source.facts)} facts)"
    )


def _text_result_message(result: SourceExtractionWorkflowResult) -> str:
    if result.duplicate:
        return (
            f"added text source; byte-identical source already exists as {result.source.source_id}"
        )
    return (
        f"added text source; extracted {result.source.source_id} ({len(result.source.facts)} facts)"
    )


def _upload_source_id(
    workspace: WikiWorkspace,
    base_source_id: str,
    model_spec: str,
    *,
    allow_duplicate: bool,
) -> str:
    if not allow_duplicate:
        return base_source_id
    return _unique_source_id(
        workspace,
        f"{base_source_id}-{_source_id_suffix(model_spec)}",
    )


def _text_source_id(
    workspace: WikiWorkspace,
    base_source_id: str,
    model_spec: str,
    *,
    allow_duplicate: bool,
) -> str:
    if allow_duplicate:
        base_source_id = f"{base_source_id}-{_source_id_suffix(model_spec)}"
    return _unique_source_id(workspace, base_source_id)


def _source_id_suffix(model_spec: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9._-]+", "-", model_spec).strip(".-_").lower()
    return suffix or "duplicate"


def _unique_source_id(workspace: WikiWorkspace, preferred_source_id: str) -> str:
    candidate = preferred_source_id
    index = 2
    while source_record_exists(workspace, candidate):
        candidate = f"{preferred_source_id}-{index}"
        index += 1
    return candidate
