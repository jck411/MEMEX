"""Wiki build provider interfaces and deterministic test fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .build_packets import WikiBuildPacket


@dataclass(frozen=True)
class ProviderWikiBuildResult:
    synthesis_markdown: str
    summary: str = ""
    provider: str = ""
    model: str = ""
    usage: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "usage", dict(self.usage))


class WikiBuildProvider(Protocol):
    def build(self, packet: WikiBuildPacket) -> ProviderWikiBuildResult:
        """Return synthesis markdown for the supplied current accepted fact packet."""


@dataclass(frozen=True)
class FixtureWikiBuildProvider:
    synthesis_markdown: str = ""

    def build(self, packet: WikiBuildPacket) -> ProviderWikiBuildResult:
        markdown = self.synthesis_markdown.strip() or _default_fixture_markdown(packet)
        return ProviderWikiBuildResult(
            synthesis_markdown=markdown,
            summary="Fixture wiki build.",
            provider="fixture",
            model="fixture",
        )


def _default_fixture_markdown(packet: WikiBuildPacket) -> str:
    lines = ["## Wiki Brief", ""]
    if not packet.accepted_facts:
        lines.append("No accepted facts are currently available for this wiki.")
        return "\n".join(lines)

    for fact in packet.accepted_facts:
        lines.append(f"- {fact.text} {fact.citation}".rstrip())
    return "\n".join(lines)
