"""Dashboard source review actions."""

from __future__ import annotations

import json

from .dashboard_action_types import SourceReviewRunner
from .dashboard_action_urls import source_detail_location
from .dashboard_forms import DashboardForm
from .workflows import ReviewWorkflowResult, WikiWorkspace


def apply_source_decisions(workspace: WikiWorkspace, form: DashboardForm) -> None:
    source_id = form.first("source_id").strip()
    accepted = {_decision_pair(value) for value in form.all("accepted_decision")}
    changed = {_decision_pair(value) for value in form.all("changed_decision")}
    for fact_id, wiki_id in sorted(changed):
        workspace.set_fact_decision(
            wiki_id,
            source_id,
            fact_id,
            (fact_id, wiki_id) in accepted,
            reason=form.first("reason").strip(),
        )


def apply_source_llm_review(
    form: DashboardForm,
    source_reviewer: SourceReviewRunner | None,
) -> str:
    if source_reviewer is None:
        raise ValueError("LLM review is not configured")
    source_id = form.first("source_id").strip()
    wiki_id = form.first("wiki_id").strip()
    if not source_id or not wiki_id:
        raise ValueError("source_id and wiki_id are required")
    review_all = form.flag("review_all")
    result = source_reviewer(wiki_id, source_id, review_all)
    return source_detail_location(
        source_id,
        _source_llm_review_message(wiki_id, result, review_all=review_all),
    )


def _source_llm_review_message(
    wiki_id: str,
    result: ReviewWorkflowResult,
    *,
    review_all: bool = False,
) -> str:
    if result.applied_count == 0:
        if review_all:
            return f"no facts available for LLM review for {wiki_id}"
        return f"no pending LLM review facts for {wiki_id}"
    provider = f" via {result.provider}" if result.provider else ""
    model = f" {result.model}" if result.model else ""
    scope = " all" if review_all else ""
    return f"LLM reviewed{scope} {result.applied_count} fact(s) for {wiki_id}{provider}{model}"


def _decision_pair(value: str) -> tuple[str, str]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("invalid decision key") from error
    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or not all(isinstance(item, str) and item.strip() for item in payload)
    ):
        raise ValueError("invalid decision key")
    return payload[0], payload[1]
