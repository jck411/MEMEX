"""Workspace-backed read queries for UI and service adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .dashboard import WikiDashboardSnapshot
from .dashboard_ingest_hints import DuplicateSourceHint
from .records import SourceRecord, WikiRecord
from .status import WikiStatus
from .vault import read_wiki_page

if TYPE_CHECKING:
    from .workflows import WikiWorkspace


@dataclass(frozen=True)
class WikiPageView:
    wiki: WikiRecord
    status: WikiStatus
    markdown: str


def dashboard_view(workspace: WikiWorkspace) -> WikiDashboardSnapshot:
    snapshot = workspace.dashboard()
    vault_root = Path(workspace.vault_root)
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
    wiki = _wiki_record(workspace, wiki_id)
    return WikiPageView(
        wiki=wiki,
        status=workspace.status(wiki_id),
        markdown=read_wiki_page(workspace.vault_root, wiki),
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
    sources = workspace.data_store.load_sources()
    hints: list[DuplicateSourceHint] = []
    seen_hashes: set[str] = set()
    for source_id, manifest in sorted(workspace.source_assets().load_manifests().items()):
        if manifest.sha256 in seen_hashes or source_id not in sources:
            continue
        seen_hashes.add(manifest.sha256)
        source = sources[source_id]
        hints.append(
            DuplicateSourceHint(
                sha256=manifest.sha256,
                source_id=source_id,
                title=source.title,
            )
        )
    return tuple(hints)


def _wiki_record(workspace: WikiWorkspace, wiki_id: str) -> WikiRecord:
    wiki = workspace.data_store.load_registry().wikis.get(wiki_id)
    if wiki is None:
        raise KeyError(f"unknown wiki_id {wiki_id!r}")
    return wiki
