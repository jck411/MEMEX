"""Language heuristics for provider-generated wiki prose."""

from __future__ import annotations

import re

_CJK_RE = re.compile(
    "["
    "\u3040-\u30ff"
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "\uac00-\ud7af"
    "]"
)
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
_COMPACT_CITATION_RE = re.compile(r"\(S\d+:\d+\)")
_NOISE_RE = re.compile(r"[#*_`>|.,;:!?()\[\]{}0-9/\\-]+")

MIN_CJK_DOMINANT_CHARS = 4
MIN_CJK_DOMINANT_RATIO = 0.25
MIN_CJK_CONTEXT_CHARS = 20


def cjk_dominant_previews(markdown: str, *, limit: int = 3) -> tuple[str, ...]:
    previews: list[str] = []
    for unit in _text_units(markdown):
        if _is_cjk_dominant(unit):
            previews.append(_preview(unit))
            if len(previews) >= limit:
                break
    return tuple(previews)


def remove_cjk_dominant_blocks(markdown: str) -> str:
    if not markdown.strip():
        return markdown
    kept = [
        block
        for block in re.split(r"\n\s*\n", markdown.strip())
        if not cjk_dominant_previews(block, limit=1)
    ]
    return "\n\n".join(kept).strip() + ("\n" if kept else "")


def _text_units(markdown: str) -> tuple[str, ...]:
    lines = tuple(line.strip() for line in markdown.splitlines() if line.strip())
    blocks = tuple(block.strip() for block in re.split(r"\n\s*\n", markdown) if block.strip())
    return lines + blocks + ((markdown.strip(),) if markdown.strip() else ())


def _is_cjk_dominant(text: str) -> bool:
    normalized = _visible_text(text)
    cjk_count = len(_CJK_RE.findall(normalized))
    if cjk_count < MIN_CJK_DOMINANT_CHARS:
        return False
    visible_chars = [char for char in normalized if not char.isspace()]
    if not visible_chars:
        return False
    return (
        cjk_count / len(visible_chars) >= MIN_CJK_DOMINANT_RATIO
        or cjk_count >= MIN_CJK_CONTEXT_CHARS
    )


def _visible_text(text: str) -> str:
    text = _MARKDOWN_LINK_RE.sub("", text)
    text = _COMPACT_CITATION_RE.sub("", text)
    return _NOISE_RE.sub("", text)


def _preview(text: str) -> str:
    text = " ".join(text.split())
    return text[:117] + "..." if len(text) > 120 else text
