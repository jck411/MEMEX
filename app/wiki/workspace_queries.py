"""Workspace-backed read queries for UI and service adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .dashboard import WikiDashboardSnapshot, dashboard_snapshot
from .dashboard_ingest_hints import DuplicateSourceHint
from .ledger import WikiLedger
from .records import SourceRecord, WikiRecord, WikiRegistry
from .source_assets import SourceAssetManifest
from .source_detail import SourceDetailView, source_detail_view
from .status import WikiStatus, statuses_for_registry
from .vault import read_wiki_page
from .wiki_facts import WikiFactsView, wiki_facts_view

if TYPE_CHECKING:
    from .workflows import WikiWorkspace


@dataclass(frozen=True)
class WikiPageView:
    wiki: WikiRecord
    status: WikiStatus
    markdown: str


@dataclass(frozen=True)
class WorkspaceReadSnapshot:
    registry: WikiRegistry
    ledger: WikiLedger
    sources: dict[str, SourceRecord]
    source_manifests: dict[str, SourceAssetManifest]
    statuses: dict[str, WikiStatus]
    vault_root: Path


def workspace_read_snapshot(workspace: WikiWorkspace) -> WorkspaceReadSnapshot:
    registry = workspace.data_store.load_registry()
    ledger = workspace.data_store.load_ledger()
    sources = workspace.data_store.load_sources()
    source_manifests = workspace.source_assets().load_manifests()
    return WorkspaceReadSnapshot(
        registry=registry,
        ledger=ledger,
        sources=sources,
        source_manifests=source_manifests,
        statuses=statuses_for_registry(registry, ledger, sources),
        vault_root=Path(workspace.vault_root),
    )


def dashboard_view(workspace: WikiWorkspace) -> WikiDashboardSnapshot:
    return dashboard_view_from_snapshot(workspace_read_snapshot(workspace))


def dashboard_view_from_snapshot(snapshot: WorkspaceReadSnapshot) -> WikiDashboardSnapshot:
    source_created_at = {
        source_id: manifest.created_at
        for source_id, manifest in snapshot.source_manifests.items()
    }
    dashboard = dashboard_snapshot(
        snapshot.registry,
        snapshot.ledger,
        snapshot.sources,
        source_created_at,
        statuses=snapshot.statuses,
    )
    return _with_file_locations(dashboard, snapshot.vault_root)


def _with_file_locations(
    snapshot: WikiDashboardSnapshot,
    vault_root: Path,
) -> WikiDashboardSnapshot:
    return WikiDashboardSnapshot(
        wikis=tuple(
            replace(
                row,
                file_location=str((vault_root / row.path).resolve(strict=False)),
            )
            for row in snapshot.wikis
        ),
        sources=snapshot.sources,
    )


def wiki_page_view(workspace: WikiWorkspace, wiki_id: str) -> WikiPageView:
    return wiki_page_view_from_snapshot(workspace_read_snapshot(workspace), wiki_id)


def wiki_page_view_from_snapshot(
    snapshot: WorkspaceReadSnapshot,
    wiki_id: str,
) -> WikiPageView:
    wiki = _wiki_record(snapshot.registry, wiki_id)
    return WikiPageView(
        wiki=wiki,
        status=snapshot.statuses[wiki_id],
        markdown=read_wiki_page(snapshot.vault_root, wiki),
    )


def wiki_facts_page_view(workspace: WikiWorkspace, wiki_id: str) -> WikiFactsView:
    return wiki_facts_page_view_from_snapshot(workspace_read_snapshot(workspace), wiki_id)


def wiki_facts_page_view_from_snapshot(
    snapshot: WorkspaceReadSnapshot,
    wiki_id: str,
) -> WikiFactsView:
    return wiki_facts_view(
        snapshot.registry,
        snapshot.ledger,
        snapshot.sources,
        wiki_id,
        status=snapshot.statuses.get(wiki_id),
    )


def source_record(workspace: WikiWorkspace, source_id: str) -> SourceRecord:
    return workspace.data_store.load_source(source_id)


def source_record_exists(workspace: WikiWorkspace, source_id: str) -> bool:
    try:
        source_record(workspace, source_id)
    except FileNotFoundError:
        return False
    return True


def duplicate_source_hints(workspace: WikiWorkspace) -> tuple[DuplicateSourceHint, ...]:
    return duplicate_source_hints_from_snapshot(workspace_read_snapshot(workspace))


def source_detail_view_from_snapshot(
    snapshot: WorkspaceReadSnapshot,
    source_id: str,
) -> SourceDetailView:
    return source_detail_view(
        snapshot.registry,
        snapshot.ledger,
        snapshot.sources,
        source_id,
        statuses=snapshot.statuses,
    )


def duplicate_source_hints_from_snapshot(
    snapshot: WorkspaceReadSnapshot,
) -> tuple[DuplicateSourceHint, ...]:
    hints: list[DuplicateSourceHint] = []
    seen_hashes: set[str] = set()
    for source_id, manifest in sorted(snapshot.source_manifests.items()):
        if manifest.sha256 in seen_hashes or source_id not in snapshot.sources:
            continue
        seen_hashes.add(manifest.sha256)
        source = snapshot.sources[source_id]
        hints.append(
            DuplicateSourceHint(
                sha256=manifest.sha256,
                source_id=source_id,
                title=source.title,
            )
        )
    return tuple(hints)


def _wiki_record(registry: WikiRegistry, wiki_id: str) -> WikiRecord:
    wiki = registry.wikis.get(wiki_id)
    if wiki is None:
        raise KeyError(f"unknown wiki_id {wiki_id!r}")
    return wiki
