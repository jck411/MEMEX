"""JSON persistence for V2 wiki data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from .atomic_io import write_json_atomic
from .ledger import WikiLedger
from .records import SourceRecord, WikiRegistry

LEDGER_FILENAME = "wiki-ledger.json"
REGISTRY_FILENAME = "wiki-registry.json"
SOURCES_DIRNAME = "sources"


def escaped_source_id(source_id: str) -> str:
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id must be a non-empty string")
    return quote(source_id, safe="")


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def source_record_path(data_root: str | Path, source_id: str) -> Path:
    filename = escaped_source_id(source_id) + ".json"
    return Path(data_root) / SOURCES_DIRNAME / filename


@dataclass(frozen=True)
class WikiDataStore:
    data_root: Path

    def __init__(self, data_root: str | Path) -> None:
        object.__setattr__(self, "data_root", Path(data_root))

    @property
    def ledger_path(self) -> Path:
        return self.data_root / LEDGER_FILENAME

    @property
    def registry_path(self) -> Path:
        return self.data_root / REGISTRY_FILENAME

    @property
    def sources_dir(self) -> Path:
        return self.data_root / SOURCES_DIRNAME

    def load_ledger(self) -> WikiLedger:
        return WikiLedger.from_dict(_read_json(self.ledger_path, {}))

    def save_ledger(self, ledger: WikiLedger) -> None:
        write_json_atomic(self.ledger_path, ledger.to_dict())

    def load_registry(self) -> WikiRegistry:
        return WikiRegistry.from_dict(_read_json(self.registry_path, {}))

    def save_registry(self, registry: WikiRegistry) -> None:
        write_json_atomic(self.registry_path, registry.to_dict())

    def load_source(self, source_id: str) -> SourceRecord:
        path = source_record_path(self.data_root, source_id)
        if not path.exists():
            raise FileNotFoundError(path)
        return SourceRecord.from_dict(_read_json(path, {}))

    def save_source(self, source: SourceRecord) -> None:
        write_json_atomic(source_record_path(self.data_root, source.source_id), source.to_dict())

    def delete_source(self, source_id: str) -> bool:
        path = source_record_path(self.data_root, source_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def load_sources(self) -> dict[str, SourceRecord]:
        if not self.sources_dir.exists():
            return {}
        sources: dict[str, SourceRecord] = {}
        for path in sorted(self.sources_dir.glob("*.json")):
            source = SourceRecord.from_dict(_read_json(path, {}))
            if source.source_id in sources:
                raise ValueError(f"duplicate source_id {source.source_id!r}")
            sources[source.source_id] = source
        return sources

    def save_sources(self, sources: Iterable[SourceRecord]) -> None:
        for source in sources:
            self.save_source(source)
