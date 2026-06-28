"""Shared source validation result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceValidationIssue:
    location: str
    message: str


@dataclass(frozen=True)
class SourceValidationReport:
    data_root: Path
    checked_source_count: int
    checked_asset_count: int
    issues: tuple[SourceValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def error_count(self) -> int:
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": self.error_count,
            "checked_source_count": self.checked_source_count,
            "checked_asset_count": self.checked_asset_count,
            "issues": [
                {"location": issue.location, "message": issue.message} for issue in self.issues
            ],
        }
