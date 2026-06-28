"""Workspace wiki build orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .markdown import build_wiki_markdown
from .status import WikiStatus, mark_build_current, status_for_wiki
from .storage import WikiDataStore
from .vault import read_wiki_page, write_wiki_page


@dataclass(frozen=True)
class BuildWorkflowResult:
    path: Path
    status: WikiStatus


class WorkspaceBuildMixin:
    data_store: WikiDataStore
    vault_root: Path

    def build_wiki(self, wiki_id: str) -> BuildWorkflowResult:
        wiki = self._load_wiki(wiki_id)
        sources = self.data_store.load_sources()
        ledger = self.data_store.load_ledger()
        status = status_for_wiki(wiki, ledger, sources)
        if status.needs_review:
            raise ValueError(f"wiki {wiki_id!r} has pending fact review")
        existing_markdown = read_wiki_page(self.vault_root, wiki)
        markdown = build_wiki_markdown(wiki, ledger, sources, existing_markdown)
        path = write_wiki_page(self.vault_root, wiki, markdown)
        mark_build_current(wiki, ledger, sources)
        self.data_store.save_ledger(ledger)
        return BuildWorkflowResult(
            path=path,
            status=status_for_wiki(wiki, ledger, sources),
        )
