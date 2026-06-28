"""Workspace wiki build orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .build_guardrails import validate_synthesis_markdown
from .build_packets import build_fact_packet
from .builders import WikiBuildProvider
from .markdown import build_wiki_markdown
from .status import WikiStatus, mark_build_current, status_for_wiki
from .storage import WikiDataStore
from .vault import read_wiki_page, write_wiki_page


@dataclass(frozen=True)
class BuildWorkflowResult:
    path: Path
    status: WikiStatus
    provider: str = ""
    model: str = ""
    summary: str = ""
    usage: Mapping[str, Any] = field(default_factory=dict)


class WorkspaceBuildMixin:
    data_store: WikiDataStore
    vault_root: Path

    def build_wiki(self, wiki_id: str, provider: WikiBuildProvider) -> BuildWorkflowResult:
        wiki = self._load_wiki(wiki_id)
        sources = self.data_store.load_sources()
        ledger = self.data_store.load_ledger()
        status = status_for_wiki(wiki, ledger, sources)
        if status.needs_review:
            raise ValueError(f"wiki {wiki_id!r} has pending fact review")
        existing_markdown = read_wiki_page(self.vault_root, wiki)
        packet = build_fact_packet(wiki, ledger, sources, existing_markdown)
        build_result = provider.build(packet)
        synthesis_markdown = validate_synthesis_markdown(
            packet,
            build_result.synthesis_markdown,
        )
        markdown = build_wiki_markdown(
            wiki,
            ledger,
            sources,
            synthesis_markdown,
            existing_markdown,
        )
        path = write_wiki_page(self.vault_root, wiki, markdown)
        mark_build_current(wiki, ledger, sources)
        self.data_store.save_ledger(ledger)
        return BuildWorkflowResult(
            path=path,
            status=status_for_wiki(wiki, ledger, sources),
            provider=build_result.provider,
            model=build_result.model,
            summary=build_result.summary,
            usage=build_result.usage,
        )
