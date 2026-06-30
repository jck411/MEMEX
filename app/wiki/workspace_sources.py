"""Workspace source record and asset lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .extraction import EXTRACTOR_VERSION, extract_source_from_path
from .records import SourceRecord
from .source_assets import SourceAssetStore
from .storage import WikiDataStore
from .timestamps import utc_now


@dataclass(frozen=True)
class SourceImportResult:
    source: SourceRecord
    duplicate_source_id: str = ""
    sha256: str = ""

    @property
    def duplicate(self) -> bool:
        return bool(self.duplicate_source_id)

    @property
    def created(self) -> bool:
        return not self.duplicate


class WorkspaceSourceMixin:
    data_store: WikiDataStore

    def save_source(self, source: SourceRecord) -> SourceRecord:
        self.data_store.save_source(source)
        return source

    def repair_source(self, source_id: str, source: SourceRecord) -> SourceRecord:
        current = self.data_store.load_source(source_id)
        if source.source_id != current.source_id:
            raise ValueError("source_id cannot be changed during source repair")
        self.data_store.save_source(source)
        ledger = self.data_store.load_ledger()
        ledger.prune_source_facts(
            source.source_id,
            {fact.fact_id for fact in source.facts},
        )
        self.data_store.save_ledger(ledger)
        return source

    def source_assets(self) -> SourceAssetStore:
        return SourceAssetStore(self.data_store.data_root)

    def delete_source(self, source_id: str) -> SourceRecord:
        source = self.data_store.load_source(source_id)
        original_ledger = self.data_store.load_ledger()
        updated_ledger = type(original_ledger).from_dict(original_ledger.to_dict())
        updated_ledger.remove_source(source_id)
        staged_asset_deletion = self.source_assets().stage_delete(source_id)
        ledger_saved = False
        source_deleted = False
        try:
            self.data_store.save_ledger(updated_ledger)
            ledger_saved = True
            if not self.data_store.delete_source(source_id):
                raise FileNotFoundError(source_id)
            source_deleted = True
        except Exception:
            if staged_asset_deletion is not None:
                staged_asset_deletion.rollback()
            if source_deleted:
                self.data_store.save_source(source)
            if ledger_saved:
                self.data_store.save_ledger(original_ledger)
            raise
        if staged_asset_deletion is not None:
            staged_asset_deletion.discard()
        return source

    def import_source(self, source: SourceRecord) -> SourceRecord:
        return self.save_source(source)

    def import_text_source(
        self,
        path: str | Path,
        source_id: str,
        *,
        title: str = "",
        document_date: str | None = None,
        source_type: str = "",
    ) -> SourceImportResult:
        asset_store = self.source_assets()
        staged_asset = asset_store.stage_file(
            source_id,
            path,
            source_kind="local_path",
        )
        try:
            duplicate_source_id = asset_store.duplicate_source_id_for_sha256(staged_asset.sha256)
            if duplicate_source_id:
                source = self.data_store.load_source(duplicate_source_id)
                staged_asset.discard()
                return SourceImportResult(
                    source=source,
                    duplicate_source_id=duplicate_source_id,
                    sha256=staged_asset.sha256,
                )

            source = extract_source_from_path(
                staged_asset.original_path,
                source_id,
                title=title,
                document_date=document_date,
                source_type=source_type,
                origin=str(Path(path)),
            )
            self.save_source(source)
            staged_asset.commit(
                extraction_provider="local",
                extraction_model=EXTRACTOR_VERSION,
                extracted_at=utc_now(),
            )
            return SourceImportResult(
                source=source,
                sha256=staged_asset.sha256,
            )
        except Exception:
            staged_asset.discard()
            raise
