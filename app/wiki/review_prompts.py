"""Prompt payloads and strict parsing for fact review decisions."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Iterable, Mapping

from .review import ReviewFact, ReviewResult, WikiReviewContext

REVIEW_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "fact_id": {"type": "string"},
                    "ticked": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["fact_id", "ticked", "reason"],
            },
        }
    },
    "required": ["decisions"],
}


def review_prompt_payload(
    context: WikiReviewContext,
    facts: Iterable[ReviewFact],
) -> dict[str, Any]:
    fact_payload = [
        {
            "source_id": fact.source_id,
            "source_title": fact.source_title,
            "fact_id": fact.fact_id,
            "fact_signature": fact.fact_signature,
            "text": fact.text,
        }
        for fact in facts
    ]
    return {
        "task": "Decide which facts belong in this wiki.",
        "wiki": {
            "wiki_id": context.wiki_id,
            "title": context.wiki_title,
            "intention": context.wiki_intention,
        },
        "source": {
            "source_id": context.source_id,
            "title": context.source_title,
            "summary": context.source_summary,
        },
        "facts": fact_payload,
        "output_schema": {
            "decisions": [
                {
                    "fact_id": "string",
                    "ticked": "boolean",
                    "reason": "short string",
                }
            ]
        },
    }


def render_review_prompt(
    context: WikiReviewContext,
    facts: Iterable[ReviewFact],
) -> str:
    return json.dumps(review_prompt_payload(context, facts), ensure_ascii=True, indent=2)


def parse_review_response(
    response: str | Mapping[str, Any] | Iterable[Mapping[str, Any]],
    expected_facts: Iterable[ReviewFact],
) -> tuple[ReviewResult, ...]:
    if isinstance(response, str):
        payload = json.loads(response)
    else:
        payload = response
    items = payload.get("decisions", payload) if isinstance(payload, Mapping) else payload
    if not isinstance(items, list):
        raise ValueError("review response must be a list or object with decisions")
    results = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("each review decision must be an object")
        results.append(
            ReviewResult(
                fact_id=item["fact_id"],
                ticked=item["ticked"],
                reason=item.get("reason", ""),
            )
        )
    return validate_review_results(expected_facts, results)


def validate_review_results(
    expected_facts: Iterable[ReviewFact],
    results: Iterable[ReviewResult],
) -> tuple[ReviewResult, ...]:
    expected_ids = [fact.fact_id for fact in expected_facts]
    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError("review batches must have unique fact ids")
    result_list = tuple(results)
    result_ids = [result.fact_id for result in result_list]
    result_counts = Counter(result_ids)
    duplicate_ids = sorted(fact_id for fact_id, count in result_counts.items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"duplicate review decisions: {', '.join(duplicate_ids)}")
    missing_ids = sorted(set(expected_ids) - set(result_ids))
    if missing_ids:
        raise ValueError(f"missing review decisions: {', '.join(missing_ids)}")
    extra_ids = sorted(set(result_ids) - set(expected_ids))
    if extra_ids:
        raise ValueError(f"unexpected review decisions: {', '.join(extra_ids)}")
    order = {fact_id: index for index, fact_id in enumerate(expected_ids)}
    return tuple(sorted(result_list, key=lambda result: order[result.fact_id]))
