"""Public source validation facade."""

from __future__ import annotations

from pathlib import Path

from .source_validation_assets import load_asset_manifests, validate_source_asset_links
from .source_validation_ledger import load_ledger, load_registry, validate_ledger_references
from .source_validation_sources import load_sources
from .source_validation_types import SourceValidationIssue, SourceValidationReport


def validate_source_workspace(
    data_root: str | Path,
    vault_root: str | Path | None = None,
) -> SourceValidationReport:
    """Validate SourceRecords, source assets, and ledger references."""

    root = Path(data_root)
    vault = Path(vault_root) if vault_root is not None else None
    issues: list[SourceValidationIssue] = []
    registry = load_registry(root, issues)
    sources = load_sources(root, issues)
    manifests = load_asset_manifests(root, issues)
    validate_source_asset_links(root, sources, manifests, issues)
    ledger = load_ledger(root, issues)
    if ledger is not None:
        validate_ledger_references(ledger, registry, sources, issues, vault)
    return SourceValidationReport(
        data_root=root,
        checked_source_count=len(sources),
        checked_asset_count=len(manifests),
        issues=tuple(issues),
    )


def format_source_validation_report(report: SourceValidationReport) -> str:
    if report.ok:
        return (
            "source validation OK: "
            f"{report.checked_source_count} source(s), "
            f"{report.checked_asset_count} asset manifest(s)"
        )
    lines = [f"source validation found {report.error_count} issue(s):"]
    lines.extend(f"- {issue.location}: {issue.message}" for issue in report.issues)
    return "\n".join(lines)


__all__ = [
    "SourceValidationIssue",
    "SourceValidationReport",
    "format_source_validation_report",
    "validate_source_workspace",
]
