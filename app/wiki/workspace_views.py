"""Workspace read/query operations."""

from __future__ import annotations

from .dashboard import WikiDashboardSnapshot, dashboard_snapshot
from .source_detail import SourceDetailView, source_detail_view
from .status import WikiStatus, status_for_wiki
from .storage import WikiDataStore


class WorkspaceViewMixin:
    data_store: WikiDataStore

    def status(self, wiki_id: str) -> WikiStatus:
        wiki = self._load_wiki(wiki_id)
        return status_for_wiki(
            wiki,
            self.data_store.load_ledger(),
            self.data_store.load_sources(),
        )

    def dashboard(self) -> WikiDashboardSnapshot:
        source_created_at = {
            source_id: manifest.created_at
            for source_id, manifest in self.source_assets().load_manifests().items()
        }
        return dashboard_snapshot(
            self.data_store.load_registry(),
            self.data_store.load_ledger(),
            self.data_store.load_sources(),
            source_created_at,
        )

    def source_detail(self, source_id: str) -> SourceDetailView:
        return source_detail_view(
            self.data_store.load_registry(),
            self.data_store.load_ledger(),
            self.data_store.load_sources(),
            source_id,
        )
