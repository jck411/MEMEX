"""Deterministic local text extraction fixtures."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .citations import plain_inline_text
from .fingerprints import stable_digest
from .records import FactRecord, SourceRecord

EXTRACTOR_VERSION = "text-v1"

_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<text>.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_RULE_RE = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")


@dataclass(frozen=True)
class ExtractedTextFact:
    text: str
    line_start: int
    line_end: int


def _strip_quote_marker(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith(">"):
        return stripped.lstrip(">").strip()
    return stripped


def _title_from_text(text: str) -> str:
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            return plain_inline_text(match.group("title"))
    return ""


def _fact_id_for_text(text: str) -> str:
    digest = stable_digest({"version": 1, "kind": "extracted_text_fact_id", "text": text})
    return f"fact-{digest[:12]}"


def _fact_signature_for_text(text: str) -> str:
    return stable_digest(
        {
            "version": 1,
            "kind": "extracted_text_fact_signature",
            "extractor": EXTRACTOR_VERSION,
            "text": text,
        }
    )


def extract_text_facts(text: str) -> tuple[ExtractedTextFact, ...]:
    """Split text/Markdown into deterministic fact candidates."""

    if not isinstance(text, str):
        raise ValueError("text must be a string")

    facts: list[ExtractedTextFact] = []
    paragraph: list[tuple[int, str]] = []
    in_code = False

    def flush_paragraph() -> None:
        if not paragraph:
            return
        fact_text = plain_inline_text(" ".join(line for _, line in paragraph))
        if fact_text:
            facts.append(
                ExtractedTextFact(
                    text=fact_text,
                    line_start=paragraph[0][0],
                    line_end=paragraph[-1][0],
                )
            )
        paragraph.clear()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if _FENCE_RE.match(raw_line):
            flush_paragraph()
            in_code = not in_code
            continue
        if in_code or not stripped:
            flush_paragraph()
            continue
        if _HEADING_RE.match(raw_line) or _RULE_RE.match(raw_line):
            flush_paragraph()
            continue

        bullet = _BULLET_RE.match(raw_line)
        if bullet:
            flush_paragraph()
            fact_text = plain_inline_text(bullet.group("text"))
            if fact_text:
                facts.append(
                    ExtractedTextFact(
                        text=fact_text,
                        line_start=line_number,
                        line_end=line_number,
                    )
                )
            continue

        paragraph.append((line_number, _strip_quote_marker(raw_line)))

    flush_paragraph()
    return tuple(facts)


def extract_source_from_text(
    source_id: str,
    text: str,
    *,
    title: str = "",
    document_date: str | None = None,
    source_type: str = "text",
    origin: str = "",
) -> SourceRecord:
    """Create a SourceRecord from local text without assigning it to any wiki."""

    facts: list[FactRecord] = []
    issues: list[str] = []
    seen_texts: set[str] = set()
    duplicate_count = 0
    for extracted in extract_text_facts(text):
        if extracted.text in seen_texts:
            duplicate_count += 1
            continue
        seen_texts.add(extracted.text)
        provenance: dict[str, object] = {
            "extractor": EXTRACTOR_VERSION,
            "line_start": extracted.line_start,
            "line_end": extracted.line_end,
        }
        if origin:
            provenance["origin"] = origin
        facts.append(
            FactRecord(
                fact_id=_fact_id_for_text(extracted.text),
                text=extracted.text,
                fact_signature=_fact_signature_for_text(extracted.text),
                provenance=provenance,
            )
        )

    if duplicate_count:
        issues.append(f"Skipped {duplicate_count} duplicate fact candidate(s).")
    if not facts:
        issues.append("No fact-like text extracted.")

    resolved_title = title or _title_from_text(text)
    summary = facts[0].text if facts else ""
    return SourceRecord(
        source_id=source_id,
        title=resolved_title,
        facts=tuple(facts),
        summary=summary,
        document_date=document_date,
        source_type=source_type,
        extraction_issues=tuple(issues),
    )


def extract_source_from_path(
    path: str | Path,
    source_id: str,
    *,
    title: str = "",
    document_date: str | None = None,
    source_type: str = "",
    origin: str = "",
) -> SourceRecord:
    """Read a local text/Markdown file and create a SourceRecord."""

    source_path = Path(path)
    text = source_path.read_text(encoding="utf-8")
    resolved_type = source_type
    if not resolved_type:
        markdown_suffixes = {".md", ".markdown"}
        resolved_type = "markdown" if source_path.suffix.lower() in markdown_suffixes else "text"
    resolved_title = title or _title_from_text(text) or source_path.stem
    return extract_source_from_text(
        source_id,
        text,
        title=resolved_title,
        document_date=document_date,
        source_type=resolved_type,
        origin=origin or str(source_path),
    )
