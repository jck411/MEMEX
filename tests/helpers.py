from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.wiki.ledger import ReviewDecision
from app.wiki.records import FactRecord, SourceRecord, WikiRecord, WikiRegistry
from app.wiki.review import ReviewResult
from app.wiki.reviewers import FixtureReviewProvider
from app.wiki.storage import WikiDataStore
from app.wiki.wiki_scope import wiki_scope_signature
from app.wiki.workflows import WikiWorkspace

DEFAULT_FACT_TEXT = "Alice joined Example Co."
CAREER_WIKI = WikiRecord("career", "Career", "career.md")


class JsonResponse:
    def __init__(self, payload: Mapping[str, Any]):
        self.payload = payload

    def __enter__(self) -> "JsonResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class RawResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self) -> "RawResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


def fact_record(
    fact_id: str = "fact-1",
    text: str = DEFAULT_FACT_TEXT,
    fact_signature: str | None = None,
    *,
    provenance: Mapping[str, Any] | None = None,
) -> FactRecord:
    return FactRecord(
        fact_id,
        text,
        fact_signature=fact_signature,
        provenance=provenance or {},
    )


def source_record(
    source_id: str = "source-1",
    *facts: FactRecord,
    title: str = "Profile",
    summary: str = "",
    document_date: str | None = None,
    source_type: str | None = None,
    extraction_issues: Iterable[str] = (),
) -> SourceRecord:
    return SourceRecord(
        source_id,
        title,
        facts=tuple(facts),
        summary=summary,
        document_date=document_date,
        source_type=source_type,
        extraction_issues=tuple(extraction_issues),
    )


def profile_source_record(source_id: str = "source-1") -> SourceRecord:
    return source_record(
        source_id,
        fact_record("fact-1", "Alice joined Example Co."),
        fact_record("fact-2", "Alice lives in Boston."),
    )


def wiki_record(
    wiki_id: str = "career",
    title: str = "Career",
    path: str | None = None,
    *,
    description: str = "",
) -> WikiRecord:
    return WikiRecord(wiki_id, title, path or f"{wiki_id}.md", description=description)


def wiki_registry(*wikis: WikiRecord) -> WikiRegistry:
    return WikiRegistry({wiki.wiki_id: wiki for wiki in wikis})


def wiki_workspace(root: str | Path, *wikis: WikiRecord) -> WikiWorkspace:
    root_path = Path(root)
    workspace = WikiWorkspace(
        data_store=WikiDataStore(root_path / "data"),
        vault_root=root_path / "vault",
    )
    for wiki in wikis:
        workspace.add_wiki(
            wiki.wiki_id,
            wiki.title,
            wiki.path,
            description=wiki.description,
        )
    return workspace


def review_decision_for_fact(
    fact: FactRecord,
    *,
    wiki: WikiRecord = CAREER_WIKI,
    ticked: bool = False,
    reason: str = "",
    reviewed_at: str = "",
) -> ReviewDecision:
    return ReviewDecision(
        ticked=ticked,
        fact_signature=fact.signature(),
        wiki_scope_signature=wiki_scope_signature(wiki),
        reason=reason,
        reviewed_at=reviewed_at,
    )


def fixture_review_provider(
    *results: ReviewResult,
    default_ticked: bool | None = None,
    default_reason: str = "",
) -> FixtureReviewProvider:
    payload: dict[str, Any] = {
        "decisions": [
            {"fact_id": result.fact_id, "ticked": result.ticked, "reason": result.reason}
            for result in results
        ],
    }
    if default_ticked is not None:
        payload["default_ticked"] = default_ticked
        payload["default_reason"] = default_reason
    return FixtureReviewProvider.from_payload(payload)


def write_text_source(
    root: str | Path,
    name: str = "note.md",
    text: str = DEFAULT_FACT_TEXT,
) -> Path:
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def extraction_packet(
    source_id: str = "source-1",
    *,
    title: str = "Profile",
    source_type: str = "text",
    date: str = "unknown",
    summary: str = DEFAULT_FACT_TEXT,
    fact_id: str = "fact_joined",
    fact_text: str = DEFAULT_FACT_TEXT,
    evidence_id: str = "ev_joined",
    source_channel: str = "document_visible",
    page: int = 1,
    locator: str = "paragraph 1",
    issues: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "document": {
            "title": title,
            "type": source_type,
            "date": date,
            "language": "en",
        },
        "summary": summary,
        "facts": [
            {
                "id": fact_id,
                "text": fact_text,
                "evidence_ids": [evidence_id],
            }
        ],
        "evidence": [
            {
                "id": evidence_id,
                "quote": fact_text,
                "source_channel": source_channel,
                "page": page,
                "locator": locator,
            }
        ],
        "issues": list(issues),
    }
