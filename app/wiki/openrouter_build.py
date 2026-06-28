"""OpenRouter-backed wiki synthesis builds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.request import urlopen

from .build_packets import WikiBuildPacket
from .build_prompts import (
    WIKI_BUILD_RESPONSE_SCHEMA,
    WIKI_BUILD_SYSTEM_PROMPT,
    parse_build_response,
    render_build_prompt,
)
from .builders import ProviderWikiBuildResult
from .openrouter_client import (
    OPENROUTER_DEEPSEEK_V4_PRO_MODEL,
    chat_completion_text,
    post_openrouter_chat_completion,
    strip_json_fence,
)

OPENROUTER_WIKI_BUILD_MODEL = OPENROUTER_DEEPSEEK_V4_PRO_MODEL
OPENROUTER_WIKI_BUILD_MAX_TOKENS = 16384


@dataclass(frozen=True)
class OpenRouterWikiBuildProvider:
    api_key: str
    model: str = OPENROUTER_WIKI_BUILD_MODEL
    opener: Callable[..., Any] = urlopen
    max_tokens: int = OPENROUTER_WIKI_BUILD_MAX_TOKENS
    timeout: int = 180

    def build(self, packet: WikiBuildPacket) -> ProviderWikiBuildResult:
        if not packet.accepted_facts:
            return ProviderWikiBuildResult(
                synthesis_markdown=(
                    "## Wiki Brief\n\n"
                    "No accepted facts are currently available for this wiki."
                ),
                summary="No accepted facts available.",
                claims=(),
                provider="openrouter",
                model=self.model,
            )

        data = post_openrouter_chat_completion(
            self.api_key,
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": WIKI_BUILD_SYSTEM_PROMPT},
                    {"role": "user", "content": render_build_prompt(packet)},
                ],
                "temperature": 0,
                "max_tokens": self.max_tokens,
                "provider": {"require_parameters": True},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "memex_wiki_build",
                        "strict": True,
                        "schema": WIKI_BUILD_RESPONSE_SCHEMA,
                    },
                },
            },
            opener=self.opener,
            timeout=self.timeout,
        )
        summary, claims, synthesis = parse_build_response(
            strip_json_fence(chat_completion_text(data, task="wiki-build"))
        )
        return ProviderWikiBuildResult(
            synthesis_markdown=synthesis,
            summary=summary,
            claims=claims,
            provider="openrouter",
            model=self.model,
            usage=_usage(data),
        )


def _usage(data: Mapping[str, Any]) -> Mapping[str, Any]:
    usage = data.get("usage")
    return usage if isinstance(usage, Mapping) else {}
