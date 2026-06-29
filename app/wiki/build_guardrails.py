"""Guardrails for LLM-generated wiki synthesis markdown."""

from __future__ import annotations

import re

from .build_packets import WikiBuildPacket
from .builders import ProviderWikiBuildClaim, ProviderWikiBuildResult
from .language_guardrails import cjk_dominant_previews
from .markdown import FACTS_END, FACTS_START, SYNTHESIS_END, SYNTHESIS_START

_COMPACT_CITATION_RE = re.compile(r"\(S\d+:\d+\)")
_HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
_FORBIDDEN_SECTION_TITLES = {
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
    _validate_claims(packet, build_result.claims)
    return validate_synthesis_markdown(packet, build_result.synthesis_markdown)


def validate_synthesis_markdown(
    packet: WikiBuildPacket,
    markdown: str,
    *,
    allowed_citations: set[str] | None = None,
) -> str:
    body = _strip_markdown_fence(markdown).replace("\r\n", "\n").strip()
    if not body:
        raise ValueError("wiki-build synthesis markdown is empty")
    _reject_managed_scaffold(body)
    _require_wiki_brief(body)
    _require_english_synthesis(body)
    _validate_citations(packet, body, allowed_citations)
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
    forbidden_markers = (SYNTHESIS_START, SYNTHESIS_END, FACTS_START, FACTS_END)
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


def _validate_claims(
    packet: WikiBuildPacket,
    claims: tuple[ProviderWikiBuildClaim, ...],
) -> None:
    allowed = {fact.citation for fact in packet.accepted_facts if fact.citation}
    if not packet.accepted_facts:
        if claims:
            raise ValueError("wiki-build claims were supplied but no accepted facts were supplied")
        return

    for index, claim in enumerate(claims, start=1):
        if not claim.text.strip():
            raise ValueError(f"wiki-build claim {index} text is empty")
        citations = tuple(citation.strip() for citation in claim.citations)
        if not citations:
            raise ValueError(
                f"wiki-build claim {index} must cite at least one accepted fact"
            )
        if any(not citation for citation in citations):
            raise ValueError(f"wiki-build claim {index} has blank citations")
        unknown = sorted(set(citations) - allowed)
        if unknown:
            raise ValueError(
                f"wiki-build claim {index} cited unknown facts: {', '.join(unknown)}"
            )


def _validate_citations(
    packet: WikiBuildPacket,
    markdown: str,
    allowed_citations: set[str] | None,
) -> None:
    allowed = allowed_citations or {
        fact.citation for fact in packet.accepted_facts if fact.citation
    }
    found = set(_COMPACT_CITATION_RE.findall(markdown))
    unknown = sorted(found - allowed)
    if unknown:
        raise ValueError(f"wiki-build synthesis cited unknown facts: {', '.join(unknown)}")
    if not packet.accepted_facts:
        if found:
            raise ValueError("wiki-build synthesis cited facts but no accepted facts were supplied")
        return
    if not found:
        raise ValueError("wiki-build synthesis cited no accepted facts")
    uncited = _uncited_substantive_blocks(markdown)
    if uncited:
        preview = "; ".join(_preview(block) for block in uncited[:3])
        raise ValueError(f"wiki-build synthesis has uncited substantive text: {preview}")


def _uncited_substantive_blocks(markdown: str) -> list[str]:
    uncited: list[str] = []
    for block in _blocks(markdown):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or all(_is_nonclaim_line(line) for line in lines):
            continue
        if _looks_like_table(lines):
            uncited.extend(
                line
                for line in lines
                if not _is_nonclaim_line(line)
                and not _is_table_separator(line)
                and not _COMPACT_CITATION_RE.search(line)
            )
            continue
        list_items = [line for line in lines if _is_list_item(line)]
        if list_items:
            uncited.extend(
                line
                for line in list_items
                if not _is_nonclaim_line(line) and not _COMPACT_CITATION_RE.search(line)
            )
            continue
        if not _COMPACT_CITATION_RE.search(block):
            uncited.append(block)
    return uncited


def _blocks(markdown: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", markdown) if block.strip()]


def _is_nonclaim_line(line: str) -> bool:
    return (
        bool(_HEADING_RE.match(line))
        or line.startswith("<!--")
        or line in {"---", "***"}
        or _is_table_separator(line)
        or _is_structural_list_label(line)
    )


def _looks_like_table(lines: list[str]) -> bool:
    return any(line.startswith("|") and line.endswith("|") for line in lines)


def _is_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|").replace(" ", "")
    return bool(stripped) and set(stripped) <= {"-", ":"}


def _is_list_item(line: str) -> bool:
    return bool(re.match(r"^([-*+]|\d+\.)\s+", line))


def _is_structural_list_label(line: str) -> bool:
    if not _is_list_item(line):
        return False
    label = re.sub(r"^([-*+]|\d+\.)\s+", "", line).strip()
    label = re.sub(r"[*_`~]", "", label).strip()
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 /&()'.,-]{0,80}:", label))


def _preview(text: str) -> str:
    text = " ".join(text.split())
    return text[:117] + "..." if len(text) > 120 else text


def _normalized_heading(value: str) -> str:
    value = re.sub(r"^#+\s*", "", value.strip())
    return re.sub(r"\s+", " ", value).lower()
