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
from .vault import wiki_page_path
from .wiki_scope import wiki_scope_signature

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
    vault_root: Path | None = None,
) -> None:
    wiki_ids = set(registry.wikis)
    source_ids = set(sources)
    _validate_assignments(ledger, wiki_ids, source_ids, issues)
    _validate_decisions(ledger, registry, sources, issues)
    _validate_build_baselines(ledger, registry, issues, vault_root)


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
    registry: WikiRegistry,
    sources: Mapping[str, SourceRecord],
    issues: list[SourceValidationIssue],
) -> None:
    for wiki_id, wiki_decisions in ledger.decisions.items():
        wiki = registry.wikis.get(wiki_id)
        if wiki is None:
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
            current_scope = wiki_scope_signature(wiki) if wiki is not None else ""
            assigned = source_id in ledger.assigned_sources(wiki_id)
            for fact_id, decision in source_decisions.items():
                fact = fact_ids.get(fact_id)
                if fact is None:
                    add_ledger_issue(
                        issues,
                        f"decisions.{wiki_id}.{source_id}.{fact_id}",
                        f"unknown fact {fact_id!r}",
                    )
                    continue
                if not assigned or wiki is None:
                    continue
                location = f"decisions.{wiki_id}.{source_id}.{fact_id}"
                if decision.fact_signature != fact.signature():
                    add_ledger_issue(
                        issues,
                        location,
                        "stale fact signature for current assigned source fact",
                    )
                if decision.wiki_scope_signature != current_scope:
                    add_ledger_issue(
                        issues,
                        location,
                        "stale wiki scope signature for current wiki description",
                    )


def _validate_build_baselines(
    ledger: WikiLedger,
    registry: WikiRegistry,
    issues: list[SourceValidationIssue],
    vault_root: Path | None,
) -> None:
    for wiki_id, fingerprint in ledger.build_baselines.items():
        wiki = registry.wikis.get(wiki_id)
        if wiki is None:
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
        if vault_root is None or wiki is None:
            continue
        try:
            path = wiki_page_path(vault_root, wiki)
        except ValueError as error:
            add_ledger_issue(
                issues,
                f"build_baselines.{wiki_id}",
                str(error),
            )
            continue
        if not path.is_file():
            add_ledger_issue(
                issues,
                f"build_baselines.{wiki_id}",
                f"built wiki page is missing at {wiki.path}",
            )
