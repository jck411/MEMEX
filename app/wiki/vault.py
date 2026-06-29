"""Vault file helpers for wiki markdown pages."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

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
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(markdown)
            temp_path = Path(temp_file.name)
        temp_path.replace(path)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
    return path
