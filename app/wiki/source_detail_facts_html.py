"""Fact editing and review controls for source detail pages."""

from __future__ import annotations

from html import escape

from .dashboard_components_html import (
    CLOSE_ICON,
    hidden_input,
    pluralize,
    render_icon_button,
    repair_hidden_fields,
    source_detail_path,
    textarea_rows,
)
from .openrouter_review import OPENROUTER_REVIEW_MODEL
from .source_decision_html import render_fact_acceptance
from .source_detail import SourceDetailView


def render_detail_facts(detail: SourceDetailView, llm_review_enabled: bool) -> str:
    add_fact = _render_add_fact_form(detail.source_id)
    if not detail.facts:
        return f"""
<section class="section" data-testid="source-facts">
  <h2>Facts</h2>
  <p class="empty">No facts extracted.</p>
  {add_fact}
</section>
"""
    decision_form_id = "source-decisions-form"
    facts = "\n".join(_render_detail_fact(detail, fact, decision_form_id) for fact in detail.facts)
    detail_path = source_detail_path(detail.source_id)
    tools = _render_decision_tools(detail, decision_form_id, llm_review_enabled)
    return f"""
<section class="section" data-testid="source-facts">
  <h2>Facts</h2>
  <form method="post" action="/source-decisions" class="source-decisions-form" id="{decision_form_id}">
    {hidden_input("source_id", detail.source_id)}
    {hidden_input("reason", "Manual dashboard decision.")}
    {hidden_input("return_to", detail_path)}
  </form>
  {tools}
  <div class="fact-list">{facts}</div>
  {add_fact}
</section>
"""


def _render_add_fact_form(source_id: str) -> str:
    return f"""
<details class="add-fact-inline">
  <summary class="button decision-action">Add Fact</summary>
  <form method="post" action="/source-repair" class="inline-repair-form">
    {repair_hidden_fields(source_id)}
    <textarea name="new_fact_text" aria-label="New fact text"></textarea>
    <button type="submit" class="button button-save">Save Fact</button>
  </form>
</details>
"""


def _render_decision_tools(
    detail: SourceDetailView,
    form_id: str,
    llm_review_enabled: bool,
) -> str:
    wiki_titles: dict[str, str] = {}
    pending_counts: dict[str, int] = {}
    for fact in detail.facts:
        for decision in fact.decisions:
            wiki_titles.setdefault(decision.wiki_id, decision.title or decision.wiki_id)
            if decision.state == "pending" or decision.stale:
                pending_counts[decision.wiki_id] = pending_counts.get(decision.wiki_id, 0) + 1
    if not wiki_titles:
        return ""
    groups = "\n".join(
        _render_decision_tool_group(
            detail.source_id,
            wiki_id,
            title,
            form_id,
            pending_counts.get(wiki_id, 0),
            llm_review_enabled,
        )
        for wiki_id, title in wiki_titles.items()
    )
    return f'<div class="decision-tools">{groups}</div>'


def _render_decision_tool_group(
    source_id: str,
    wiki_id: str,
    title: str,
    form_id: str,
    pending_count: int,
    llm_review_enabled: bool,
) -> str:
    llm_review = (
        _render_llm_review_form(source_id, wiki_id, pending_count) if llm_review_enabled else ""
    )
    return f"""
<div class="decision-tool-group">
  <span class="muted">{escape(title)}</span>
  <button type="button" class="button decision-action" data-decision-form="{escape(form_id)}" data-decision-wiki="{escape(wiki_id)}" data-decision-checked="true">Select all</button>
  <button type="button" class="button decision-action" data-decision-form="{escape(form_id)}" data-decision-wiki="{escape(wiki_id)}" data-decision-checked="false">Clear all</button>
  {llm_review}
</div>
"""


def _render_llm_review_form(source_id: str, wiki_id: str, pending_count: int) -> str:
    detail_path = source_detail_path(source_id)
    review_all = pending_count == 0
    review_all_value = "1" if review_all else "0"
    label = "LLM Review All" if review_all else "LLM Review"
    title = (
        f"OpenRouter {escape(OPENROUTER_REVIEW_MODEL)}; review all facts"
        if review_all
        else f"OpenRouter {escape(OPENROUTER_REVIEW_MODEL)}; {pluralize(pending_count, 'pending fact')}"
    )
    return f"""
<form method="post" action="/source-llm-review" class="llm-review-inline" data-pending-count="{pending_count}">
  {hidden_input("source_id", source_id)}
  {hidden_input("wiki_id", wiki_id)}
  {hidden_input("return_to", detail_path)}
  {hidden_input("review_all", review_all_value)}
  <button type="submit" class="button decision-action" title="{title}">{label}</button>
</form>
"""


def _render_detail_fact(detail: SourceDetailView, fact, decision_form_id: str) -> str:
    metadata = _render_fact_metadata(fact)
    evidence = _render_fact_evidence(fact)
    acceptance = render_fact_acceptance(fact, decision_form_id)
    text_editor = _render_fact_text_editor(detail.source_id, fact)
    tools = _render_fact_row_tools(detail.source_id, fact)
    return f"""
<article class="fact-row" data-fact-id="{escape(fact.fact_id, quote=True)}">
  <div class="fact-heading">
    <div>
      <span class="fact-id">{escape(fact.fact_id)}</span>
      <span class="muted">{escape(fact.fact_signature[:12])}</span>
    </div>
    {tools}
  </div>
  {text_editor}
  {acceptance}
  {evidence}
  {metadata}
</article>
"""


def _render_fact_text_editor(source_id: str, fact) -> str:
    rows = textarea_rows(fact.text, minimum=2, maximum=8)
    return f"""
<form method="post" action="/source-repair" class="editable-text-form fact-text-form">
  {repair_hidden_fields(source_id)}
  {hidden_input("fact_id", fact.fact_id)}
  <textarea class="editable-textarea fact-text-editor" name="fact_text" rows="{rows}" aria-label="Fact text">{escape(fact.text)}</textarea>
  {render_icon_button("Save fact", icon="✓", variant="save")}
</form>
"""


def _render_fact_row_tools(source_id: str, fact) -> str:
    return f"""
<div class="row-tools">
  <form method="post" action="/source-repair" class="inline-action-form">
    {repair_hidden_fields(source_id)}
    {render_icon_button("Delete fact", icon=CLOSE_ICON, name="delete_fact", value=fact.fact_id, variant="danger", raw=True)}
  </form>
</div>
"""


def _render_fact_evidence(fact) -> str:
    if not fact.evidence:
        return '<p class="empty">No evidence captured.</p>'
    items = "\n".join(_render_evidence_item(item) for item in fact.evidence)
    return f'<div class="evidence-list">{items}</div>'


def _render_evidence_item(item) -> str:
    meta = " · ".join(
        value
        for value in (
            item.evidence_id,
            item.source_channel,
            f"page {item.page}" if item.page else "",
            item.locator,
        )
        if value
    )
    quote_html = f"<blockquote>{escape(item.quote)}</blockquote>" if item.quote else ""
    return f"""
<div class="evidence-item">
  <div class="muted">{escape(meta)}</div>
  {quote_html}
</div>
"""


def _render_fact_metadata(fact) -> str:
    if not fact.metadata:
        return ""
    items = "\n".join(
        f"<span>{escape(key)}: {escape(value)}</span>" for key, value in fact.metadata
    )
    return f'<div class="metadata-list">{items}</div>'
