"""Workspace source-to-wiki assignment operations."""

from __future__ import annotations

from .status import WikiStatus, status_for_wiki
from .workspace_base import WorkspaceBaseMixin


class WorkspaceAssignmentMixin(WorkspaceBaseMixin):
    def assign_source(self, wiki_id: str, source_id: str) -> WikiStatus:
        wiki = self._load_wiki(wiki_id)
        source = self.data_store.load_source(source_id)
        ledger = self.data_store.load_ledger()
        ledger.assign_source(wiki_id, source.source_id)
        self.data_store.save_ledger(ledger)
        return status_for_wiki(wiki, ledger, self.data_store.load_sources())

    def unassign_source(self, wiki_id: str, source_id: str) -> WikiStatus:
        wiki = self._load_wiki(wiki_id)
        ledger = self.data_store.load_ledger()
        ledger.unassign_source(wiki_id, source_id)
        sources = self.data_store.load_sources()
        self.data_store.save_ledger(ledger)
        return status_for_wiki(wiki, ledger, sources)
