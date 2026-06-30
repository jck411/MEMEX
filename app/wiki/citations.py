"""Text helpers for generated wiki markdown."""

from __future__ import annotations


def plain_inline_text(value: object) -> str:
    text = " ".join(str(value).split())
    return text


def inline_text(value: object) -> str:
    text = plain_inline_text(value)
    return text.replace("[[", r"\[\[").replace("]]", r"\]\]")
