"""Source asset manifest validation."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Mapping

from .records import SourceRecord
from .source_assets import (
    SOURCE_ASSET_MANIFEST,
    SOURCE_ASSET_ORIGINALS_DIRNAME,
    SOURCE_ASSET_STAGING_DIRNAME,
    SOURCE_ASSETS_DIRNAME,
    SourceAssetManifest,
    SourceAssetStore,
    sha256_for_path,
)
from .source_validation_io import (
    add_issue,
    location,
    read_required_json_object,
    reject_unknown_keys,
)
from .source_validation_types import SourceValidationIssue
from .storage import source_record_path

_MANIFEST_KEYS = {
    "source_id",
    "source_kind",
    "original_name",
    "stored_path",
    "mime_type",
    "size_bytes",
    "sha256",
    "created_at",
    "extraction_model",
    "extraction_provider",
    "extracted_at",
    "usage",
}


def load_asset_manifests(
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> dict[str, SourceAssetManifest]:
    assets_dir = data_root / SOURCE_ASSETS_DIRNAME
    if not assets_dir.exists():
        return {}
    manifests: dict[str, SourceAssetManifest] = {}
    manifest_locations: dict[str, Path] = {}
    store = SourceAssetStore(data_root)
    for path in sorted(assets_dir.glob(f"*/{SOURCE_ASSET_MANIFEST}")):
        if SOURCE_ASSET_STAGING_DIRNAME in path.parts:
            continue
        payload = read_required_json_object(path, data_root, issues)
        if payload is None:
            continue
        reject_unknown_keys(payload, _MANIFEST_KEYS, data_root, path, "manifest", issues)
        try:
            manifest = SourceAssetManifest.from_dict(payload)
        except Exception as error:
            add_issue(issues, data_root, path, f"invalid source asset manifest: {error}")
            continue
        _validate_manifest_path(manifest, path, store, data_root, issues)
        if manifest.source_id in manifests:
            add_issue(
                issues,
                data_root,
                path,
                f"duplicate source asset for {manifest.source_id!r}; "
                f"first seen in {location(manifest_locations[manifest.source_id], data_root)}",
            )
            continue
        manifests[manifest.source_id] = manifest
        manifest_locations[manifest.source_id] = path
        _validate_asset_manifest(manifest, path, data_root, issues)
    return manifests


def validate_source_asset_links(
    data_root: Path,
    sources: Mapping[str, SourceRecord],
    manifests: Mapping[str, SourceAssetManifest],
    issues: list[SourceValidationIssue],
) -> None:
    for source_id in sorted(sources):
        if source_id not in manifests:
            add_issue(
                issues,
                data_root,
                source_record_path(data_root, source_id),
                f"missing source asset manifest for {source_id!r}",
            )
    store = SourceAssetStore(data_root)
    for source_id in sorted(manifests):
        if source_id not in sources:
            add_issue(
                issues,
                data_root,
                store.manifest_path(source_id),
                f"missing source record for asset {source_id!r}",
            )


def _validate_manifest_path(
    manifest: SourceAssetManifest,
    path: Path,
    store: SourceAssetStore,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    expected_dir = store.asset_dir(manifest.source_id)
    if path.parent != expected_dir:
        add_issue(
            issues,
            data_root,
            path,
            f"manifest source_id {manifest.source_id!r} belongs in {expected_dir.name}",
        )


def _validate_asset_manifest(
    manifest: SourceAssetManifest,
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    if not _is_lower_sha256(manifest.sha256):
        add_issue(
            issues,
            data_root,
            path,
            "sha256 must be a lowercase hex digest",
        )

    stored_path = PurePosixPath(manifest.stored_path)
    if not stored_path.parts or stored_path.parts[0] != SOURCE_ASSET_ORIGINALS_DIRNAME:
        add_issue(
            issues,
            data_root,
            path,
            f"stored_path must point inside {SOURCE_ASSET_ORIGINALS_DIRNAME}/",
        )
        return

    original_path = path.parent.joinpath(*stored_path.parts)
    if not original_path.is_file():
        add_issue(
            issues,
            data_root,
            path,
            f"stored original is missing at {manifest.stored_path}",
        )
        return

    _validate_original_bytes(manifest, original_path, path, data_root, issues)


def _validate_original_bytes(
    manifest: SourceAssetManifest,
    original_path: Path,
    manifest_path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> None:
    actual_size = original_path.stat().st_size
    if actual_size != manifest.size_bytes:
        add_issue(
            issues,
            data_root,
            manifest_path,
            f"size_bytes is {manifest.size_bytes}, but original is {actual_size} bytes",
        )
    if sha256_for_path(original_path) != manifest.sha256:
        add_issue(
            issues,
            data_root,
            manifest_path,
            "sha256 does not match stored original",
        )


def _is_lower_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
