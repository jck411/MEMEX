"""HTML rendering for wiki fact provenance pages."""

from __future__ import annotations

from html import escape

from .dashboard import WikiDashboardSnapshot
from .dashboard_components_html import (
    css_token,
    display_label,
    pluralize,
    render_dashboard_page,
    render_status_pill,
    source_detail_path,
    wiki_detail_path,
)
from .provider_balances import ProviderBalance
from .wiki_facts import WikiFactDetail, WikiFactSourceGroup, WikiFactsView


def render_wiki_facts_html(
    *,
    snapshot: WikiDashboardSnapshot,
    facts_view: WikiFactsView,
    provider_balances: tuple[ProviderBalance, ...] = (),
    message: str = "",
    message_type: str = "",
) -> str:
    wiki = facts_view.wiki
    state = render_status_pill(_status_state(facts_view.status))
    meta = " · ".join(
        (
            wiki.wiki_id,
            wiki.path,
            pluralize(facts_view.accepted_count, "accepted fact"),
            pluralize(facts_view.not_used_count, "not-used fact"),
        )
    )
    body = f"""
<section class="section wiki-facts-view">
  <div class="wiki-view-heading">
    <div>
      <p class="eyebrow">Wiki Facts</p>
      <h2>{escape(wiki.title)}</h2>
      <p class="muted">{escape(meta)}</p>
    </div>
    <div class="wiki-view-actions">
      {state}
      <a class="button" href="{wiki_detail_path(wiki.wiki_id)}">Open Wiki</a>
    </div>
  </div>
</section>
{_render_fact_section("Accepted Facts", facts_view.groups, accepted=True)}
{_render_fact_section("Not Used", facts_view.groups, accepted=False)}
"""
    return render_dashboard_page(
        document_title=f"{wiki.title} Facts - MEMEX Wiki",
        page_heading="Wiki Facts",
        snapshot=snapshot,
        provider_balances=provider_balances,
        message=message,
        message_type=message_type,
        body=body,
        back_href="/",
    )


def _status_state(status) -> str:
    if status.needs_review:
        return "needs_review"
    if status.needs_build:
        return "needs_build"
    return "current"


def _render_fact_section(
    title: str,
    groups: tuple[WikiFactSourceGroup, ...],
    *,
    accepted: bool,
) -> str:
    rendered_groups = tuple(
        _render_source_group(group, accepted=accepted)
        for group in groups
        if _group_facts(group, accepted=accepted)
    )
    if not rendered_groups:
        return f"""
<section class="section" data-testid="{_section_testid(accepted)}">
  <h2>{escape(title)}</h2>
  <p class="empty">No {escape(title.lower())}.</p>
</section>
"""
    return f"""
<section class="section" data-testid="{_section_testid(accepted)}">
  <h2>{escape(title)}</h2>
  <div class="wiki-fact-source-list">{"".join(rendered_groups)}</div>
</section>
"""


def _render_source_group(group: WikiFactSourceGroup, *, accepted: bool) -> str:
    facts = _group_facts(group, accepted=accepted)
    rendered = "\n".join(_render_fact(fact) for fact in facts)
    href = source_detail_path(group.source_id)
    return f"""
<article class="wiki-fact-source">
  <div class="wiki-fact-source-heading">
    <div>
      <h3><a href="{href}">{escape(group.source_title)}</a></h3>
      <p class="muted">{escape(group.source_id)}</p>
    </div>
    <span class="wiki-stat">{pluralize(len(facts), "fact")}</span>
  </div>
  <div class="fact-list">{rendered}</div>
</article>
"""


def _render_fact(fact: WikiFactDetail) -> str:
    reason = f'<p class="decision-reason">{escape(fact.reason)}</p>' if fact.reason else ""
    reviewed = f" · {fact.reviewed_at}" if fact.reviewed_at else ""
    return f"""
<article class="fact-row wiki-fact-row" data-fact-id="{escape(fact.fact_id, quote=True)}">
  <div class="fact-heading">
    <div>
      <span class="fact-id">{escape(fact.fact_id)}</span>
      <span class="decision-pill decision-{css_token(fact.state)}">{escape(display_label(fact.state))}</span>
      <span class="muted">{escape(reviewed.lstrip())}</span>
    </div>
  </div>
  <p>{escape(fact.text)}</p>
  {reason}
</article>
"""


def _group_facts(
    group: WikiFactSourceGroup,
    *,
    accepted: bool,
) -> tuple[WikiFactDetail, ...]:
    return group.accepted if accepted else group.not_used


def _section_testid(accepted: bool) -> str:
    return "wiki-accepted-facts" if accepted else "wiki-not-used-facts"
