"""Central wiki ledger primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _require_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class ReviewDecision:
    ticked: bool
    fact_signature: str
    wiki_scope_signature: str
    reason: str = ""
    reviewed_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.ticked, bool):
            raise ValueError("ticked must be a bool")
        _require_id(self.fact_signature, "fact_signature")
        _require_id(self.wiki_scope_signature, "wiki_scope_signature")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")
        if not isinstance(self.reviewed_at, str):
            raise ValueError("reviewed_at must be a string")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ticked": self.ticked,
            "fact_signature": self.fact_signature,
            "wiki_scope_signature": self.wiki_scope_signature,
        }
        if self.reason:
            payload["reason"] = self.reason
        if self.reviewed_at:
            payload["reviewed_at"] = self.reviewed_at
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReviewDecision":
        return cls(
            ticked=payload["ticked"],
            fact_signature=payload["fact_signature"],
            wiki_scope_signature=payload["wiki_scope_signature"],
            reason=payload.get("reason", ""),
            reviewed_at=payload.get("reviewed_at", ""),
        )


@dataclass
class WikiLedger:
    assignments: dict[str, tuple[str, ...]] = field(default_factory=dict)
    decisions: dict[str, dict[str, dict[str, ReviewDecision]]] = field(default_factory=dict)
    build_baselines: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.assignments = {
            wiki_id: tuple(sorted(set(source_ids)))
            for wiki_id, source_ids in self.assignments.items()
            if source_ids
        }
        decisions: dict[str, dict[str, dict[str, ReviewDecision]]] = {}
        for wiki_id, wiki_decisions in self.decisions.items():
            normalized_sources = {
                source_id: {
                    fact_id: decision
                    if isinstance(decision, ReviewDecision)
                    else ReviewDecision.from_dict(decision)
                    for fact_id, decision in source_decisions.items()
                }
                for source_id, source_decisions in wiki_decisions.items()
                if source_decisions
            }
            if normalized_sources:
                decisions[wiki_id] = normalized_sources
        self.decisions = decisions
        self.build_baselines = dict(self.build_baselines)

    @classmethod
    def empty(cls) -> "WikiLedger":
        return cls()

    def assigned_sources(self, wiki_id: str) -> tuple[str, ...]:
        return self.assignments.get(wiki_id, ())

    def assign_source(self, wiki_id: str, source_id: str) -> None:
        _require_id(wiki_id, "wiki_id")
        _require_id(source_id, "source_id")
        source_ids = set(self.assignments.get(wiki_id, ()))
        source_ids.add(source_id)
        self.assignments[wiki_id] = tuple(sorted(source_ids))

    def unassign_source(self, wiki_id: str, source_id: str) -> None:
        source_ids = set(self.assignments.get(wiki_id, ()))
        source_ids.discard(source_id)
        if source_ids:
            self.assignments[wiki_id] = tuple(sorted(source_ids))
        else:
            self.assignments.pop(wiki_id, None)

    def remove_source(self, source_id: str) -> None:
        _require_id(source_id, "source_id")
        for wiki_id in tuple(self.assignments):
            self.unassign_source(wiki_id, source_id)
        for wiki_id in tuple(self.decisions):
            self.decisions[wiki_id].pop(source_id, None)
            if not self.decisions[wiki_id]:
                self.decisions.pop(wiki_id, None)

    def remove_wiki(self, wiki_id: str) -> None:
        _require_id(wiki_id, "wiki_id")
        self.assignments.pop(wiki_id, None)
        self.decisions.pop(wiki_id, None)
        self.build_baselines.pop(wiki_id, None)

    def prune_source_facts(self, source_id: str, fact_ids: set[str]) -> None:
        _require_id(source_id, "source_id")
        for fact_id in fact_ids:
            _require_id(fact_id, "fact_id")
        for wiki_id in tuple(self.decisions):
            source_decisions = self.decisions[wiki_id].get(source_id)
            if not source_decisions:
                continue
            for fact_id in tuple(source_decisions):
                if fact_id not in fact_ids:
                    source_decisions.pop(fact_id, None)
            if not source_decisions:
                self.decisions[wiki_id].pop(source_id, None)
            if not self.decisions[wiki_id]:
                self.decisions.pop(wiki_id, None)

    def decision_for(self, wiki_id: str, source_id: str, fact_id: str) -> ReviewDecision | None:
        return self.decisions.get(wiki_id, {}).get(source_id, {}).get(fact_id)

    def set_decision(
        self,
        wiki_id: str,
        source_id: str,
        fact_id: str,
        decision: ReviewDecision,
    ) -> None:
        _require_id(wiki_id, "wiki_id")
        _require_id(source_id, "source_id")
        _require_id(fact_id, "fact_id")
        self.decisions.setdefault(wiki_id, {}).setdefault(source_id, {})[fact_id] = decision

    def clear_decision(self, wiki_id: str, source_id: str, fact_id: str) -> None:
        source_decisions = self.decisions.get(wiki_id, {}).get(source_id)
        if not source_decisions:
            return
        source_decisions.pop(fact_id, None)
        if not source_decisions:
            self.decisions.get(wiki_id, {}).pop(source_id, None)
        if not self.decisions.get(wiki_id):
            self.decisions.pop(wiki_id, None)

    def set_build_baseline(self, wiki_id: str, fingerprint: str) -> None:
        _require_id(wiki_id, "wiki_id")
        _require_id(fingerprint, "fingerprint")
        self.build_baselines[wiki_id] = fingerprint

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignments": {
                wiki_id: list(self.assignments[wiki_id]) for wiki_id in sorted(self.assignments)
            },
            "decisions": {
                wiki_id: {
                    source_id: {fact_id: facts[fact_id].to_dict() for fact_id in sorted(facts)}
                    for source_id, facts in sorted(sources.items())
                }
                for wiki_id, sources in sorted(self.decisions.items())
            },
            "build_baselines": dict(sorted(self.build_baselines.items())),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WikiLedger":
        return cls(
            assignments={
                wiki_id: tuple(source_ids)
                for wiki_id, source_ids in payload.get("assignments", {}).items()
            },
            decisions={
                wiki_id: {
                    source_id: {
                        fact_id: ReviewDecision.from_dict(decision)
                        for fact_id, decision in fact_decisions.items()
                    }
                    for source_id, fact_decisions in source_decisions.items()
                }
                for wiki_id, source_decisions in payload.get("decisions", {}).items()
            },
            build_baselines=dict(payload.get("build_baselines", {})),
        )
