"""Workspace wiki registry lifecycle operations."""

from __future__ import annotations

from pathlib import Path

from .records import WikiRecord, WikiRegistry
from .storage import WikiDataStore
from .vault import wiki_page_path


class WorkspaceWikiMixin:
    data_store: WikiDataStore
    vault_root: Path

    def add_wiki(
        self,
        wiki_id: str,
        title: str,
        path: str,
        *,
        description: str = "",
    ) -> WikiRecord:
        registry = self.data_store.load_registry()
        wikis = dict(registry.wikis)
        if wiki_id in wikis:
            raise ValueError(f"wiki {wiki_id!r} already exists")
        wiki = WikiRecord(
            wiki_id=wiki_id,
            title=title,
            path=path,
            description=description,
        )
        page_path = wiki_page_path(self.vault_root, wiki)
        for existing in wikis.values():
            if wiki_page_path(self.vault_root, existing) == page_path:
                raise ValueError(f"wiki path {path!r} is already registered")
        wikis[wiki_id] = wiki
        self.data_store.save_registry(WikiRegistry(wikis))
        return wiki

    def delete_wiki(self, wiki_id: str) -> WikiRecord:
        registry = self.data_store.load_registry()
        wiki = registry.wikis.get(wiki_id)
        if wiki is None:
            raise KeyError(f"unknown wiki_id {wiki_id!r}")
        path = wiki_page_path(self.vault_root, wiki)
        if path.exists() and path.is_dir():
            raise ValueError(f"wiki path is a directory: {path}")

        wikis = dict(registry.wikis)
        del wikis[wiki_id]
        updated_registry = WikiRegistry(wikis)

        original_ledger = self.data_store.load_ledger()
        updated_ledger = type(original_ledger).from_dict(original_ledger.to_dict())
        updated_ledger.remove_wiki(wiki_id)

        self.data_store.save_ledger(updated_ledger)
        try:
            self.data_store.save_registry(updated_registry)
        except Exception:
            self.data_store.save_ledger(original_ledger)
            raise

        # add_wiki prevents shared paths; this preserves hand-edited registries safely.
        still_referenced = any(
            wiki_page_path(self.vault_root, remaining) == path
            for remaining in updated_registry.wikis.values()
        )
        if not still_referenced:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return wiki

    def update_wiki_description(self, wiki_id: str, description: str) -> WikiRecord:
        registry = self.data_store.load_registry()
        current = registry.wikis.get(wiki_id)
        if current is None:
            raise KeyError(f"unknown wiki_id {wiki_id!r}")
        updated = WikiRecord(
            wiki_id=current.wiki_id,
            title=current.title,
            path=current.path,
            description=description.strip(),
        )
        wikis = dict(registry.wikis)
        wikis[wiki_id] = updated
        self.data_store.save_registry(WikiRegistry(wikis))
        return updated

    def _load_wiki(self, wiki_id: str) -> WikiRecord:
        registry = self.data_store.load_registry()
        wiki = registry.wikis.get(wiki_id)
        if wiki is None:
            raise KeyError(f"unknown wiki_id {wiki_id!r}")
        return wiki
