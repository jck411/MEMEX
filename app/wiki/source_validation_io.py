"""Small I/O helpers for source validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .source_validation_types import SourceValidationIssue
from .storage import LEDGER_FILENAME


def read_optional_json_object(
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> Mapping[str, Any] | None:
    if not path.exists():
        return {}
    return read_required_json_object(path, data_root, issues)


def read_required_json_object(
    path: Path,
    data_root: Path,
    issues: list[SourceValidationIssue],
) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        add_issue(issues, data_root, path, f"invalid JSON: {error}")
        return None
    if not isinstance(payload, Mapping):
        add_issue(issues, data_root, path, "JSON payload must be an object")
        return None
    return payload


def string_sequence(
    value: Any,
    data_root: Path,
    path: Path,
    label: str,
    issues: list[SourceValidationIssue],
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        add_issue(issues, data_root, path, f"{label} must be an array")
        return ()
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            add_issue(
                issues,
                data_root,
                path,
                f"{label}[{index}] must be a non-empty string",
            )
            continue
        items.append(item)
    return tuple(items)


def reject_unknown_keys(
    payload: Mapping[str, Any],
    allowed_keys: set[str],
    data_root: Path,
    path: Path,
    label: str,
    issues: list[SourceValidationIssue],
) -> None:
    unknown = sorted(set(payload) - allowed_keys)
    if unknown:
        add_issue(
            issues,
            data_root,
            path,
            f"{label} has unknown key(s): {', '.join(unknown)}",
        )


def add_issue(
    issues: list[SourceValidationIssue],
    data_root: Path,
    path: Path,
    message: str,
) -> None:
    issues.append(SourceValidationIssue(location(path, data_root), message))


def add_ledger_issue(
    issues: list[SourceValidationIssue],
    location_suffix: str,
    message: str,
) -> None:
    issues.append(SourceValidationIssue(f"{LEDGER_FILENAME}:{location_suffix}", message))


def location(path: Path, data_root: Path) -> str:
    try:
        return str(path.relative_to(data_root).as_posix())
    except ValueError:
        return str(path)
