"""Source, fact, and wiki registry records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .fingerprints import stable_digest


def _require_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class FactRecord:
    fact_id: str
    text: str
    fact_signature: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.fact_id, "fact_id")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if self.fact_signature is not None:
            _require_id(self.fact_signature, "fact_signature")
        object.__setattr__(self, "provenance", dict(self.provenance))

    def signature(self) -> str:
        if self.fact_signature:
            return self.fact_signature
        return stable_digest({"text": self.text, "provenance": self.provenance})

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"fact_id": self.fact_id, "text": self.text}
        if self.fact_signature is not None:
            payload["fact_signature"] = self.fact_signature
        if self.provenance:
            payload["provenance"] = dict(self.provenance)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FactRecord":
        return cls(
            fact_id=payload["fact_id"],
            text=payload.get("text", ""),
            fact_signature=payload.get("fact_signature"),
            provenance=payload.get("provenance", {}),
        )


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    facts: tuple[FactRecord, ...] = ()
    summary: str = ""
    document_date: str | None = None
    source_type: str | None = None
    extraction_issues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_id(self.source_id, "source_id")
        if not isinstance(self.title, str):
            raise ValueError("title must be a string")
        facts = tuple(self.facts)
        fact_ids = [fact.fact_id for fact in facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError(f"source {self.source_id} has duplicate fact ids")
        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "extraction_issues", tuple(self.extraction_issues))

    def fact_by_id(self) -> dict[str, FactRecord]:
        return {fact.fact_id: fact for fact in self.facts}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_id": self.source_id,
            "title": self.title,
            "facts": [fact.to_dict() for fact in self.facts],
        }
        if self.summary:
            payload["summary"] = self.summary
        if self.document_date is not None:
            payload["document_date"] = self.document_date
        if self.source_type is not None:
            payload["source_type"] = self.source_type
        if self.extraction_issues:
            payload["extraction_issues"] = list(self.extraction_issues)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SourceRecord":
        return cls(
            source_id=payload["source_id"],
            title=payload.get("title", ""),
            facts=tuple(FactRecord.from_dict(fact) for fact in payload.get("facts", [])),
            summary=payload.get("summary", ""),
            document_date=payload.get("document_date"),
            source_type=payload.get("source_type"),
            extraction_issues=tuple(payload.get("extraction_issues", ())),
        )


@dataclass(frozen=True)
class WikiRecord:
    wiki_id: str
    title: str
    path: str
    description: str = ""

    def __post_init__(self) -> None:
        _require_id(self.wiki_id, "wiki_id")
        _require_id(self.title, "title")
        _require_id(self.path, "path")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")

    def to_dict(self) -> dict[str, str]:
        payload = {"title": self.title, "path": self.path}
        if self.description:
            payload["description"] = self.description
        return payload

    @classmethod
    def from_dict(cls, wiki_id: str, payload: Mapping[str, Any]) -> "WikiRecord":
        return cls(
            wiki_id=wiki_id,
            title=payload["title"],
            path=payload["path"],
            description=payload.get("description", ""),
        )


@dataclass(frozen=True)
class WikiRegistry:
    wikis: Mapping[str, WikiRecord] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = dict(self.wikis)
        for wiki_id, wiki in normalized.items():
            if wiki_id != wiki.wiki_id:
                raise ValueError(f"registry key {wiki_id!r} does not match wiki_id")
        object.__setattr__(self, "wikis", normalized)

    def active_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.wikis))

    def to_dict(self) -> dict[str, Any]:
        return {"wikis": {wiki_id: self.wikis[wiki_id].to_dict() for wiki_id in sorted(self.wikis)}}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WikiRegistry":
        return cls(
            {
                wiki_id: WikiRecord.from_dict(wiki_id, wiki_payload)
                for wiki_id, wiki_payload in payload.get("wikis", {}).items()
            }
        )


def source_index(
    sources: Mapping[str, SourceRecord] | Iterable[SourceRecord],
) -> dict[str, SourceRecord]:
    if isinstance(sources, Mapping):
        return dict(sources)
    indexed: dict[str, SourceRecord] = {}
    for source in sources:
        if source.source_id in indexed:
            raise ValueError(f"duplicate source_id {source.source_id!r}")
        indexed[source.source_id] = source
    return indexed
