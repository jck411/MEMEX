"""Duplicate source hints for dashboard source ingestion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DuplicateSourceHint:
    sha256: str
    source_id: str
    title: str = ""
