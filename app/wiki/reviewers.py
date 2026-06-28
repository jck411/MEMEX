"""Review provider interfaces and deterministic fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol

from .review import ReviewFact, ReviewResult, WikiReviewContext
from .review_prompts import validate_review_results


@dataclass(frozen=True)
class ProviderReviewResult:
    decisions: tuple[ReviewResult, ...]
    provider: str = ""
    model: str = ""
    usage: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decisions", tuple(self.decisions))
        object.__setattr__(self, "usage", dict(self.usage))


class ReviewProvider(Protocol):
    def review(
        self,
        context: WikiReviewContext,
        facts: Iterable[ReviewFact],
    ) -> ProviderReviewResult:
        """Return one decision for each fact in the provided batch."""


@dataclass(frozen=True)
class FixtureReviewProvider:
    decisions: Mapping[str, ReviewResult] = field(default_factory=dict)
    default_ticked: bool | None = None
    default_reason: str = ""

    def review(
        self,
        context: WikiReviewContext,
        facts: Iterable[ReviewFact],
    ) -> ProviderReviewResult:
        del context
        fact_list = tuple(facts)
        results = []
        for fact in fact_list:
            decision = self.decisions.get(fact.fact_id)
            if decision is None:
                if self.default_ticked is None:
                    raise KeyError(f"no fixture decision for fact_id {fact.fact_id!r}")
                decision = ReviewResult(
                    fact_id=fact.fact_id,
                    ticked=self.default_ticked,
                    reason=self.default_reason,
                )
            results.append(decision)
        return ProviderReviewResult(
            decisions=validate_review_results(fact_list, results),
            provider="fixture",
            model="fixture",
        )

    @classmethod
    def from_payload(cls, payload: Any) -> "FixtureReviewProvider":
        if isinstance(payload, Mapping):
            items = payload.get("decisions", [])
            default_ticked = payload.get("default_ticked")
            default_reason = payload.get("default_reason", "")
        else:
            items = payload
            default_ticked = None
            default_reason = ""
        if not isinstance(items, list):
            raise ValueError("fixture decisions must be a list")
        item_ids = [item["fact_id"] for item in items]
        duplicate_ids = sorted({fact_id for fact_id in item_ids if item_ids.count(fact_id) > 1})
        if duplicate_ids:
            raise ValueError(f"duplicate fixture decisions: {', '.join(duplicate_ids)}")
        if default_ticked is not None and not isinstance(default_ticked, bool):
            raise ValueError("default_ticked must be a bool when provided")
        if not isinstance(default_reason, str):
            raise ValueError("default_reason must be a string")
        decisions = {
            item["fact_id"]: ReviewResult(
                fact_id=item["fact_id"],
                ticked=item["ticked"],
                reason=item.get("reason", ""),
            )
            for item in items
        }
        return cls(
            decisions=decisions,
            default_ticked=default_ticked,
            default_reason=default_reason,
        )
