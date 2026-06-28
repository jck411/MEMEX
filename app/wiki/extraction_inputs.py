"""Source input loading for LLM extraction adapters."""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from .extraction_packets import ExtractionPacketError

TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".html",
    ".htm",
    ".xml",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
}
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@dataclass(frozen=True)
class ExtractionAttachment:
    file_name: str
    mime_type: str
    data: str


@dataclass(frozen=True)
class ExtractionInput:
    source_id: str
    source_text: str = ""
    title: str = ""
    source_type: str = ""
    origin: str = ""
    operator_instructions: str = ""
    attachments: tuple[ExtractionAttachment, ...] = ()


def extraction_input_from_path(
    path: str | Path,
    source_id: str,
    *,
    title: str = "",
    source_type: str = "",
    operator_instructions: str = "",
) -> ExtractionInput:
    source_path = Path(path)
    resolved_type = source_type or _source_type_for_path(source_path)
    mime_type = _mime_type(source_path)
    if _is_text_path(source_path, mime_type):
        return ExtractionInput(
            source_id=source_id,
            source_text=source_path.read_text(encoding="utf-8"),
            title=title or source_path.stem,
            source_type=resolved_type,
            origin=str(source_path),
            operator_instructions=operator_instructions.strip(),
        )
    if mime_type == "application/pdf" or mime_type in IMAGE_MIME_TYPES:
        return ExtractionInput(
            source_id=source_id,
            title=title or source_path.stem,
            source_type=resolved_type,
            origin=str(source_path),
            operator_instructions=operator_instructions.strip(),
            attachments=(
                ExtractionAttachment(
                    file_name=source_path.name,
                    mime_type=mime_type,
                    data=base64.b64encode(source_path.read_bytes()).decode("ascii"),
                ),
            ),
        )
    raise ExtractionPacketError(
        f"unsupported source file type for direct extraction: {source_path.suffix or source_path.name}"
    )


def _source_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"md", "markdown"}:
        return "markdown"
    if suffix in {"jpg", "jpeg", "png", "gif", "webp"}:
        return "image"
    return suffix or "unknown"


def _mime_type(path: Path) -> str:
    if path.suffix.lower() == ".md":
        return "text/markdown"
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type or "application/octet-stream"


def _is_text_path(path: Path, mime_type: str) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or mime_type.startswith("text/")
