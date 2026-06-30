"""HTTP form parsing helpers for the local dashboard server."""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class UploadedFormFile:
    field_name: str
    file_name: str
    content_type: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class DashboardForm:
    fields: dict[str, tuple[str, ...]]
    files: dict[str, UploadedFormFile]

    def first(self, name: str) -> str:
        values = self.fields.get(name)
        return values[0] if values else ""

    def all(self, name: str) -> tuple[str, ...]:
        return self.fields.get(name, ())

    def flag(self, name: str) -> bool:
        return self.first(name) in {"1", "true", "on"}

    def file(self, name: str) -> UploadedFormFile | None:
        return self.files.get(name)


def parse_urlencoded_form(body: bytes) -> DashboardForm:
    fields = {
        name: tuple(values)
        for name, values in parse_qs(
            body.decode("utf-8"),
            keep_blank_values=True,
        ).items()
    }
    return DashboardForm(fields=fields, files={})


def parse_multipart_form(content_type: str, body: bytes) -> DashboardForm:
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("multipart/form-data content type is required")
    message = cast(
        EmailMessage,
        BytesParser(policy=default).parsebytes(
            b"Content-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + body
        ),
    )
    if not message.is_multipart():
        raise ValueError("multipart form body is required")

    fields: dict[str, list[str]] = {}
    files: dict[str, UploadedFormFile] = {}
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        field_name = _parameter_text(name)
        if not field_name:
            continue
        payload = _payload_bytes(part)
        filename = part.get_filename()
        if filename is None:
            charset = part.get_content_charset() or "utf-8"
            fields.setdefault(field_name, []).append(payload.decode(charset, errors="replace"))
            continue
        files[field_name] = UploadedFormFile(
            field_name=field_name,
            file_name=safe_upload_filename(filename),
            content_type=part.get_content_type(),
            data=payload,
        )
    return DashboardForm(
        fields={name: tuple(values) for name, values in fields.items()},
        files=files,
    )


def _parameter_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, tuple) and len(value) == 3 and isinstance(value[2], str):
        return value[2]
    return ""


def _payload_bytes(part: EmailMessage) -> bytes:
    payload = part.get_payload(decode=True)
    if payload is None:
        return b""
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        charset = part.get_content_charset() or "utf-8"
        return payload.encode(charset, errors="replace")
    raise ValueError("multipart form part payload must be bytes")


def safe_return_to(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return "/"
    return value if value.startswith("/") else "/"


def safe_upload_filename(filename: str | None) -> str:
    safe_name = Path((filename or "upload").replace("\\", "/")).name
    if safe_name in {"", ".", ".."}:
        return "upload"
    return safe_name


def source_id_from_filename(filename: str) -> str:
    stem = Path(filename).stem or "upload"
    return _source_id_from_text(stem, fallback="upload")


def source_id_from_text(title: str, text: str) -> str:
    words = re.findall(r"[A-Za-z0-9._-]+", text)
    stem = title.strip() or " ".join(words[:8])
    return _source_id_from_text(stem, fallback="typed-text")


def _source_id_from_text(value: str, *, fallback: str) -> str:
    source_id = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_").lower()
    return source_id[:80].strip(".-_") or fallback
