"""Wiki ledger and registry validation."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .ledger import WikiLedger
from .records import SourceRecord, WikiRegistry
from .source_validation_io import (
    add_issue,
    add_ledger_issue,
    read_optional_json_object,
    reject_unknown_keys,
)
from .source_validation_types import SourceValidationIssue
from .storage import LEDGER_FILENAME, REGISTRY_FILENAME

_REGISTRY_KEYS = {"wikis"}
_LEDGER_KEYS = {"assignments", "decisions", "build_baselines"}


def load_registry(
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> WikiRegistry:
    path = data_root / REGISTRY_FILENAME
    payload = read_optional_json_object(path, data_root, issues)
    if payload is None:
        return WikiRegistry()
    reject_unknown_keys(payload, _REGISTRY_KEYS, data_root, path, "wiki registry", issues)
    try:
        return WikiRegistry.from_dict(payload)
    except Exception as error:
        add_issue(issues, data_root, path, f"invalid wiki registry: {error}")
        return WikiRegistry()


def load_ledger(
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> WikiLedger | None:
    path = data_root / LEDGER_FILENAME
    payload = read_optional_json_object(path, data_root, issues)
    if payload is None:
        return WikiLedger.empty()
    reject_unknown_keys(payload, _LEDGER_KEYS, data_root, path, "wiki ledger", issues)
    try:
        return WikiLedger.from_dict(payload)
    except Exception as error:
        add_issue(issues, data_root, path, f"invalid wiki ledger: {error}")
        return None


def validate_ledger_references(
    ledger: WikiLedger,
    registry: WikiRegistry,
    sources: Mapping[str, SourceRecord],
    issues: list[SourceValidationIssue],
) -> None:
    wiki_ids = set(registry.wikis)
    source_ids = set(sources)
    _validate_assignments(ledger, wiki_ids, source_ids, issues)
    _validate_decisions(ledger, wiki_ids, sources, issues)
    _validate_build_baselines(ledger, wiki_ids, issues)


def _validate_assignments(
    ledger: WikiLedger,
    wiki_ids: set[str],
    source_ids: set[str],
    issues: list[SourceValidationIssue],
) -> None:
    for wiki_id, assigned_source_ids in ledger.assignments.items():
        if wiki_id not in wiki_ids:
            add_ledger_issue(issues, f"assignments.{wiki_id}", f"unknown wiki {wiki_id!r}")
        for source_id in assigned_source_ids:
            if source_id not in source_ids:
                add_ledger_issue(
                    issues,
                    f"assignments.{wiki_id}",
                    f"unknown source {source_id!r}",
                )


def _validate_decisions(
    ledger: WikiLedger,
    wiki_ids: set[str],
    sources: Mapping[str, SourceRecord],
    issues: list[SourceValidationIssue],
) -> None:
    for wiki_id, wiki_decisions in ledger.decisions.items():
        if wiki_id not in wiki_ids:
            add_ledger_issue(issues, f"decisions.{wiki_id}", f"unknown wiki {wiki_id!r}")
        for source_id, source_decisions in wiki_decisions.items():
            source = sources.get(source_id)
            if source is None:
                add_ledger_issue(
                    issues,
                    f"decisions.{wiki_id}.{source_id}",
                    f"unknown source {source_id!r}",
                )
                continue
            fact_ids = source.fact_by_id()
            for fact_id in source_decisions:
                if fact_id not in fact_ids:
                    add_ledger_issue(
                        issues,
                        f"decisions.{wiki_id}.{source_id}.{fact_id}",
                        f"unknown fact {fact_id!r}",
                    )


def _validate_build_baselines(
    ledger: WikiLedger,
    wiki_ids: set[str],
    issues: list[SourceValidationIssue],
) -> None:
    for wiki_id, fingerprint in ledger.build_baselines.items():
        if wiki_id not in wiki_ids:
            add_ledger_issue(
                issues,
                f"build_baselines.{wiki_id}",
                f"unknown wiki {wiki_id!r}",
            )
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            add_ledger_issue(
                issues,
                f"build_baselines.{wiki_id}",
                "build baseline fingerprint must be a non-empty string",
            )
