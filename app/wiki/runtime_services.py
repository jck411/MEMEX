"""Provider-backed runtime wiring for dashboard entrypoints."""

from __future__ import annotations

from pathlib import Path

from .dashboard_action_types import (
    BalanceProvider,
    SourceExtractionRunner,
    SourceFixRunner,
    SourceReviewRunner,
)
from .dashboard_runtime import DashboardRuntime
from .model_profiles import merged_env
from .openrouter_review import OpenRouterReviewProvider
from .provider_balances import provider_balance_snapshot
from .source_extraction import extract_source_to_workspace
from .source_fix import fix_source_extraction
from .workflows import WikiWorkspace
from .workspace_queries import source_record


def dashboard_runtime_from_env(
    workspace: WikiWorkspace,
    *,
    env_file: str | Path = ".env",
    balance_provider: BalanceProvider | None = None,
    source_extractor: SourceExtractionRunner | None = None,
    source_fixer: SourceFixRunner | None = None,
    source_reviewer: SourceReviewRunner | None = None,
) -> DashboardRuntime:
    env_path = Path(env_file)
    return DashboardRuntime(
        workspace=workspace,
        balance_provider=balance_provider
        or (lambda: provider_balance_snapshot(merged_env(env_path))),
        source_extractor=source_extractor
        or (
            lambda job: extract_source_to_workspace(
                workspace,
                job,
                merged_env(env_path),
            )
        ),
        source_fixer=source_fixer
        or (
            lambda source_id, instruction: fix_source_extraction(
                source_record(workspace, source_id),
                instruction,
                merged_env(env_path).get("OPENROUTER_API_KEY", ""),
            )
        ),
        source_reviewer=source_reviewer
        or (
            lambda wiki_id, source_id, review_all: workspace.review_source_with_provider(
                wiki_id,
                source_id,
                OpenRouterReviewProvider(
                    api_key=merged_env(env_path).get("OPENROUTER_API_KEY", ""),
                ),
                review_all=review_all,
            )
        ),
    )
