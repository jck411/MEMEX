"""Runtime service contract for the local wiki dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from .dashboard_action_types import (
    BalanceProvider,
    SourceExtractionRunner,
    SourceFixRunner,
    SourceReviewRunner,
    WikiBuildRunner,
)
from .model_profiles import DEFAULT_EXTRACTION_PROFILE_ID
from .workflows import WikiWorkspace


@dataclass(frozen=True)
class DashboardRuntime:
    workspace: WikiWorkspace
    balance_provider: BalanceProvider | None = None
    source_extractor: SourceExtractionRunner | None = None
    extraction_model_spec: str = DEFAULT_EXTRACTION_PROFILE_ID
    source_fixer: SourceFixRunner | None = None
    source_reviewer: SourceReviewRunner | None = None
    wiki_builder: WikiBuildRunner | None = None
