"""Guardrails for LLM-generated wiki synthesis markdown."""

from __future__ import annotations

import re

from .build_packets import WikiBuildPacket
from .builders import ProviderWikiBuildResult
from .language_guardrails import cjk_dominant_previews
from .markdown import (
    FACTS_END,
    FACTS_START,
    REFERENCES_END,
    REFERENCES_START,
    SYNTHESIS_END,
    SYNTHESIS_START,
)

_HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
_FORBIDDEN_SECTION_TITLES = {
    "source fact decisions",
    "accepted facts",
    "references",
    "default conversation context",
    "restricted accepted facts",
    "general accepted facts",
    "llm context",
}


def validate_wiki_build(
    packet: WikiBuildPacket,
    build_result: ProviderWikiBuildResult,
) -> str:
    return validate_synthesis_markdown(packet, build_result.synthesis_markdown)


def validate_synthesis_markdown(
    packet: WikiBuildPacket,
    markdown: str,
) -> str:
    body = _strip_markdown_fence(markdown).replace("\r\n", "\n").strip()
    if not body:
        raise ValueError("wiki-build synthesis markdown is empty")
    _reject_managed_scaffold(body)
    _require_wiki_brief(body)
    _require_english_synthesis(body)
    return re.sub(r"\n{3,}", "\n\n", body).rstrip()


def _strip_markdown_fence(markdown: str) -> str:
    stripped = markdown.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _reject_managed_scaffold(markdown: str) -> None:
    forbidden_markers = (
        SYNTHESIS_START,
        SYNTHESIS_END,
        FACTS_START,
        FACTS_END,
        REFERENCES_START,
        REFERENCES_END,
    )
    if any(marker in markdown for marker in forbidden_markers):
        raise ValueError("wiki-build synthesis must not include MEMEX managed markers")
    for line in markdown.splitlines():
        match = _HEADING_RE.match(line.strip())
        if not match:
            continue
        level = len(match.group("level"))
        title = _normalized_heading(match.group("title"))
        if level == 1:
            raise ValueError("wiki-build synthesis must not include a page title")
        if title in _FORBIDDEN_SECTION_TITLES:
            raise ValueError(f"wiki-build synthesis must not include {match.group('title')!r}")


def _require_wiki_brief(markdown: str) -> None:
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            _normalized_heading(stripped.removeprefix("##")) == "wiki brief"
            and stripped.startswith("## ")
        ):
            return
        raise ValueError("wiki-build synthesis must start with ## Wiki Brief")
    raise ValueError("wiki-build synthesis must start with ## Wiki Brief")


def _require_english_synthesis(markdown: str) -> None:
    previews = cjk_dominant_previews(markdown)
    if previews:
        preview = "; ".join(previews)
        raise ValueError(
            "wiki-build synthesis must be English; detected CJK-dominant text: "
            f"{preview}"
        )


def _normalized_heading(value: str) -> str:
    value = re.sub(r"^#+\s*", "", value.strip())
    return re.sub(r"\s+", " ", value).lower()
