"""Shared accessors for composed workspace workflow mixins."""

from __future__ import annotations

from .records import WikiRecord
from .source_assets import SourceAssetStore
from .storage import WikiDataStore


class WorkspaceBaseMixin:
    data_store: WikiDataStore

    def _load_wiki(self, wiki_id: str) -> WikiRecord:
        registry = self.data_store.load_registry()
        wiki = registry.wikis.get(wiki_id)
        if wiki is None:
            raise KeyError(f"unknown wiki_id {wiki_id!r}")
        return wiki

    def source_assets(self) -> SourceAssetStore:
        return SourceAssetStore(self.data_store.data_root)
