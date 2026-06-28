"""Shared dashboard action runner types."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .provider_balances import ProviderBalance
    from .source_extraction import SourceExtractionJob, SourceExtractionWorkflowResult
    from .source_fix import SourceFixResult
    from .workflows import ReviewWorkflowResult
else:
    ProviderBalance = Any
    SourceExtractionJob = Any
    SourceExtractionWorkflowResult = Any
    SourceFixResult = Any
    ReviewWorkflowResult = Any

BalanceProvider = Callable[[], tuple[ProviderBalance, ...]]
SourceExtractionRunner = Callable[[SourceExtractionJob], SourceExtractionWorkflowResult]
SourceFixRunner = Callable[[str, str], SourceFixResult]
SourceReviewRunner = Callable[[str, str, bool], ReviewWorkflowResult]
