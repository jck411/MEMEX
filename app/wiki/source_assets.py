"""Original source artifact storage for MEMEX."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from uuid import uuid4

from .atomic_io import write_json_atomic
from .storage import escaped_source_id
from .timestamps import utc_now

SOURCE_ASSETS_DIRNAME = "source-assets"
SOURCE_ASSET_MANIFEST = "manifest.json"
SOURCE_ASSET_ORIGINALS_DIRNAME = "original"
SOURCE_ASSET_STAGING_DIRNAME = ".staging"
SOURCE_ASSET_KINDS = {"file", "local_path", "typed_text"}


@dataclass(frozen=True)
class SourceAssetManifest:
    source_id: str
    source_kind: str
    original_name: str
    stored_path: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: str
    extraction_model: str = ""
    extraction_provider: str = ""
    extracted_at: str = ""
    usage: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _asset_dirname_for_source_id(self.source_id)
        if self.source_kind not in SOURCE_ASSET_KINDS:
            raise ValueError(f"unknown source_kind {self.source_kind!r}")
        _require_text(self.original_name, "original_name")
        _require_relative_path(self.stored_path, "stored_path")
        _require_text(self.mime_type, "mime_type")
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise ValueError("sha256 must be a hex digest")
        _require_text(self.created_at, "created_at")
        for name in ("extraction_model", "extraction_provider", "extracted_at"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be a string")
        object.__setattr__(self, "usage", dict(self.usage))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "original_name": self.original_name,
            "stored_path": self.stored_path,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "extraction_model": self.extraction_model,
            "extraction_provider": self.extraction_provider,
            "extracted_at": self.extracted_at,
        }
        if self.usage:
            payload["usage"] = dict(self.usage)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SourceAssetManifest":
        return cls(
            source_id=payload["source_id"],
            source_kind=payload["source_kind"],
            original_name=payload["original_name"],
            stored_path=payload["stored_path"],
            mime_type=payload["mime_type"],
            size_bytes=payload["size_bytes"],
            sha256=payload["sha256"],
            created_at=payload["created_at"],
            extraction_model=payload.get("extraction_model", ""),
            extraction_provider=payload.get("extraction_provider", ""),
            extracted_at=payload.get("extracted_at", ""),
            usage=payload.get("usage", {}),
        )


@dataclass(frozen=True)
class StagedSourceAsset:
    store: "SourceAssetStore"
    source_id: str
    source_kind: str
    staging_dir: Path
    original_path: Path
    original_name: str
    stored_path: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: str

    def manifest(
        self,
        *,
        extraction_provider: str,
        extraction_model: str,
        extracted_at: str,
        usage: Mapping[str, Any] | None = None,
    ) -> SourceAssetManifest:
        return SourceAssetManifest(
            source_id=self.source_id,
            source_kind=self.source_kind,
            original_name=self.original_name,
            stored_path=self.stored_path,
            mime_type=self.mime_type,
            size_bytes=self.size_bytes,
            sha256=self.sha256,
            created_at=self.created_at,
            extraction_provider=extraction_provider,
            extraction_model=extraction_model,
            extracted_at=extracted_at,
            usage=usage or {},
        )

    def commit(
        self,
        *,
        extraction_provider: str,
        extraction_model: str,
        extracted_at: str,
        usage: Mapping[str, Any] | None = None,
    ) -> SourceAssetManifest:
        manifest = self.manifest(
            extraction_provider=extraction_provider,
            extraction_model=extraction_model,
            extracted_at=extracted_at,
            usage=usage,
        )
        write_json_atomic(self.staging_dir / SOURCE_ASSET_MANIFEST, manifest.to_dict())
        final_dir = self.store.asset_dir(self.source_id)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        rollback_dir = None
        if final_dir.exists():
            rollback_dir = (
                self.store.staging_root
                / f"{_asset_dirname_for_source_id(self.source_id)}-rollback-{uuid4().hex}"
            )
            rollback_dir.parent.mkdir(parents=True, exist_ok=True)
            final_dir.replace(rollback_dir)
        try:
            self.staging_dir.replace(final_dir)
        except Exception:
            if rollback_dir is not None and rollback_dir.exists():
                if final_dir.exists():
                    shutil.rmtree(final_dir)
                rollback_dir.replace(final_dir)
            raise
        if rollback_dir is not None:
            shutil.rmtree(rollback_dir, ignore_errors=True)
        return manifest

    def discard(self) -> None:
        shutil.rmtree(self.staging_dir, ignore_errors=True)


@dataclass(frozen=True)
class StagedSourceAssetDeletion:
    original_dir: Path
    staging_dir: Path

    def rollback(self) -> None:
        if not self.staging_dir.exists():
            return
        self.original_dir.parent.mkdir(parents=True, exist_ok=True)
        self.staging_dir.replace(self.original_dir)

    def discard(self) -> None:
        try:
            shutil.rmtree(self.staging_dir)
        except OSError:
            pass


@dataclass(frozen=True)
class SourceAssetStore:
    data_root: Path | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", Path(self.data_root))

    @property
    def assets_dir(self) -> Path:
        return self.data_root / SOURCE_ASSETS_DIRNAME

    @property
    def staging_root(self) -> Path:
        return self.assets_dir / SOURCE_ASSET_STAGING_DIRNAME

    def asset_dir(self, source_id: str) -> Path:
        return self.assets_dir / _asset_dirname_for_source_id(source_id)

    def manifest_path(self, source_id: str) -> Path:
        return self.asset_dir(source_id) / SOURCE_ASSET_MANIFEST

    def load_manifest(self, source_id: str) -> SourceAssetManifest:
        path = self.manifest_path(source_id)
        if not path.exists():
            raise FileNotFoundError(path)
        return SourceAssetManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def load_manifests(self) -> dict[str, SourceAssetManifest]:
        if not self.assets_dir.exists():
            return {}
        manifests: dict[str, SourceAssetManifest] = {}
        for path in sorted(self.assets_dir.glob(f"*/{SOURCE_ASSET_MANIFEST}")):
            manifest = SourceAssetManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if manifest.source_id in manifests:
                raise ValueError(f"duplicate source asset {manifest.source_id!r}")
            manifests[manifest.source_id] = manifest
        return manifests

    def stage_file(
        self,
        source_id: str,
        path: str | Path,
        *,
        source_kind: str,
        mime_type: str = "",
        created_at: str = "",
    ) -> StagedSourceAsset:
        if source_kind not in SOURCE_ASSET_KINDS:
            raise ValueError(f"unknown source_kind {source_kind!r}")
        asset_dirname = _asset_dirname_for_source_id(source_id)
        source_path = Path(path)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        original_name = safe_original_name(source_path.name)
        staging_dir = self.staging_root / f"{asset_dirname}-{uuid4().hex}"
        stored_path = str(PurePosixPath(SOURCE_ASSET_ORIGINALS_DIRNAME) / original_name)
        original_path = staging_dir / SOURCE_ASSET_ORIGINALS_DIRNAME / original_name
        original_path.parent.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(source_path, original_path)
        return StagedSourceAsset(
            store=self,
            source_id=source_id,
            source_kind=source_kind,
            staging_dir=staging_dir,
            original_path=original_path,
            original_name=original_name,
            stored_path=stored_path,
            mime_type=mime_type or mime_type_for_path(original_path),
            size_bytes=original_path.stat().st_size,
            sha256=sha256_for_path(original_path),
            created_at=created_at or utc_now(),
        )

    def stage_delete(self, source_id: str) -> StagedSourceAssetDeletion | None:
        asset_dirname = _asset_dirname_for_source_id(source_id)
        path = self.asset_dir(source_id)
        if not path.exists():
            return None
        staging_dir = self.staging_root / f"{asset_dirname}-delete-{uuid4().hex}"
        staging_dir.parent.mkdir(parents=True, exist_ok=True)
        path.replace(staging_dir)
        return StagedSourceAssetDeletion(
            original_dir=path,
            staging_dir=staging_dir,
        )

    def duplicate_source_id_for_sha256(
        self,
        sha256: str,
        *,
        exclude_source_id: str = "",
    ) -> str:
        for source_id, manifest in sorted(self.load_manifests().items()):
            if source_id == exclude_source_id:
                continue
            if manifest.sha256 == sha256:
                return source_id
        return ""


def source_asset_dir(data_root: str | Path, source_id: str) -> Path:
    return SourceAssetStore(data_root).asset_dir(source_id)


def sha256_for_path(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_original_name(name: str | None) -> str:
    safe_name = Path((name or "original").replace("\\", "/")).name
    if safe_name in {"", ".", ".."}:
        return "original"
    return safe_name


def mime_type_for_path(path: str | Path) -> str:
    source_path = Path(path)
    if source_path.suffix.lower() == ".md":
        return "text/markdown"
    mime_type, _ = mimetypes.guess_type(source_path.name)
    return mime_type or "application/octet-stream"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _asset_dirname_for_source_id(source_id: str) -> str:
    dirname = escaped_source_id(source_id)
    if dirname in {".", "..", SOURCE_ASSET_STAGING_DIRNAME}:
        raise ValueError(f"source_id {source_id!r} maps to a reserved source asset path")
    return dirname


def _require_relative_path(value: Any, field_name: str) -> None:
    _require_text(value, field_name)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a relative path inside the asset")
