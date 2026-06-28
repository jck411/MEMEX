"""Wiki scope helpers shared by review and build state."""

from __future__ import annotations

from .fingerprints import stable_digest
from .records import WikiRecord


def wiki_description(wiki: WikiRecord) -> str:
    return wiki.description.strip()


def wiki_intention_text(wiki: WikiRecord) -> str:
    description = wiki_description(wiki)
    if description:
        return description
    return (
        f"Maintain the {wiki.title} wiki at {wiki.path}. Accept only facts "
        "that clearly belong in this wiki."
    )


def wiki_scope_signature(wiki: WikiRecord) -> str:
    return stable_digest(
        {
            "version": 1,
            "kind": "wiki_scope",
            "wiki_id": wiki.wiki_id,
            "title": wiki.title,
            "path": wiki.path,
            "description": wiki_description(wiki),
        }
    )
