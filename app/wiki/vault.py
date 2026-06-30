"""Vault file helpers for wiki markdown pages."""

from __future__ import annotations

from pathlib import Path

from .atomic_io import write_text_atomic
from .records import WikiRecord


def wiki_page_path(vault_root: str | Path, wiki: WikiRecord) -> Path:
    relative_path = Path(wiki.path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("wiki path must stay within the vault root")
    return Path(vault_root) / relative_path


def read_wiki_page(vault_root: str | Path, wiki: WikiRecord) -> str:
    path = wiki_page_path(vault_root, wiki)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_wiki_page(vault_root: str | Path, wiki: WikiRecord, markdown: str) -> Path:
    path = wiki_page_path(vault_root, wiki)
    write_text_atomic(path, markdown)
    return path
