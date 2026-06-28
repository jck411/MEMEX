"""OpenRouter-backed per-source fact review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping
from urllib.request import urlopen

from .openrouter_client import (
    OPENROUTER_DEEPSEEK_V4_PRO_MODEL,
    chat_completion_text,
    post_openrouter_chat_completion,
    strip_json_fence,
)
from .review import ReviewFact, WikiReviewContext
from .review_prompts import (
    REVIEW_RESPONSE_SCHEMA,
    parse_review_response,
    render_review_prompt,
)
from .reviewers import ProviderReviewResult

OPENROUTER_REVIEW_MODEL = OPENROUTER_DEEPSEEK_V4_PRO_MODEL

OPENROUTER_REVIEW_SYSTEM_PROMPT = """\
You decide source-to-wiki relevance for MEMEX.

MEMEX turns source material into durable markdown wikis. The wiki is the
product. Review only the supplied facts for the supplied wiki and source.

Use the wiki intention from the user payload as the wiki-specific scope. Do not
use custom hidden assumptions for a wiki. Tick a fact when it should be included
in that wiki's durable knowledge base. Untick a fact when it is irrelevant,
incidental, redundant for that wiki, or too weakly useful for the stated
intention. Keep reasons short and source-grounded.

Return only the requested JSON object.
"""


@dataclass(frozen=True)
class OpenRouterReviewProvider:
    api_key: str
    model: str = OPENROUTER_REVIEW_MODEL
    opener: Callable[..., Any] = urlopen
    max_tokens: int = 2048

    def review(
        self,
        context: WikiReviewContext,
        facts: Iterable[ReviewFact],
    ) -> ProviderReviewResult:
        fact_batch = tuple(facts)
        if not fact_batch:
            return ProviderReviewResult((), provider="openrouter", model=self.model)

        data = post_openrouter_chat_completion(
            self.api_key,
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": OPENROUTER_REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": render_review_prompt(context, fact_batch)},
                ],
                "temperature": 0,
                "max_tokens": self.max_tokens,
                "provider": {"require_parameters": True},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "memex_review_decisions",
                        "strict": True,
                        "schema": REVIEW_RESPONSE_SCHEMA,
                    },
                },
            },
            opener=self.opener,
        )
        decisions = parse_review_response(
            strip_json_fence(chat_completion_text(data, task="review")),
            fact_batch,
        )
        return ProviderReviewResult(
            decisions=decisions,
            provider="openrouter",
            model=self.model,
            usage=_usage(data),
        )


def _usage(data: Mapping[str, Any]) -> Mapping[str, Any]:
    usage = data.get("usage")
    return usage if isinstance(usage, Mapping) else {}
