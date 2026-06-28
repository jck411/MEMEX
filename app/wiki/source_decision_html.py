"""Inline source fact acceptance controls."""

from __future__ import annotations

import json
from html import escape

from .dashboard_components_html import css_token, display_label
from .source_detail import SourceFactDetail


def render_fact_acceptance(
    fact: SourceFactDetail,
    form_id: str = "",
) -> str:
    if not fact.decisions:
        return '<span class="empty">No assigned wikis.</span>'
    controls = "\n".join(
        _decision_checkbox(fact.fact_id, decision, form_id) for decision in fact.decisions
    )
    return f"""
<div class="acceptance-group">
  <div class="acceptance-list">{controls}</div>
</div>
"""


def _decision_checkbox(fact_id: str, decision, form_id: str) -> str:
    checked = " checked" if decision.ticked is True and not decision.stale else ""
    title = decision.title or decision.wiki_id
    reviewed = f" · {decision.reviewed_at}" if decision.reviewed_at else ""
    key = _decision_key(fact_id, decision.wiki_id)
    form_attr = _form_attr(form_id)
    reason = _decision_reason(decision)
    return f"""
<label class="acceptance-option">
  <span class="acceptance-line">
    <input type="checkbox" name="accepted_decision" value="{escape(key)}" data-decision-key="{escape(key)}" data-wiki-id="{escape(decision.wiki_id)}"{checked}{form_attr}>
    <span>{escape(title)}</span>
    <span class="decision-pill decision-{css_token(decision.state)}">{escape(display_label(decision.state))}</span>
    <span class="muted">{escape(decision.wiki_id + reviewed)}</span>
  </span>
  {reason}
</label>
"""


def _decision_reason(decision) -> str:
    if not decision.reason:
        return ""
    return f'<span class="decision-reason">{escape(decision.reason)}</span>'


def _decision_key(fact_id: str, wiki_id: str) -> str:
    return json.dumps([fact_id, wiki_id], separators=(",", ":"))


def _form_attr(form_id: str) -> str:
    return f' form="{escape(form_id)}"' if form_id else ""
