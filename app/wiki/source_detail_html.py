"""HTML rendering for source detail dashboard pages."""

from __future__ import annotations

from html import escape

from .dashboard import WikiDashboardSnapshot
from .dashboard_components_html import (
    CLOSE_ICON,
    hidden_input,
    pluralize,
    render_dashboard_page,
    render_delete_source_form,
    render_icon_button,
    render_source_assignment_bubble,
    repair_hidden_fields,
    source_detail_path,
    textarea_rows,
)
from .dashboard_html import DashboardRenderOptions
from .source_detail import SourceDetailView
from .source_detail_facts_html import render_detail_facts
from .source_detail_scripts import source_detail_script
from .source_repair_html import render_source_repair


def render_source_detail_html(
    snapshot: WikiDashboardSnapshot,
    source_detail: SourceDetailView,
    options: DashboardRenderOptions | None = None,
) -> str:
    if options is None:
        options = DashboardRenderOptions()
    body = _render_source_detail(
        source_detail,
        fix_enabled=options.source_fix_enabled,
        llm_review_enabled=options.source_llm_review_enabled,
    )
    return render_dashboard_page(
        document_title=f"{source_detail.title or source_detail.source_id} - MEMEX Wiki",
        page_heading="Source Detail",
        snapshot=snapshot,
        provider_balances=options.provider_balances,
        message=options.message,
        message_type=options.message_type,
        body=body,
        scripts=source_detail_script(),
        back_href="/",
    )


def _render_source_detail(
    detail: SourceDetailView,
    *,
    fix_enabled: bool,
    llm_review_enabled: bool,
) -> str:
    meta = " · ".join(
        item
        for item in (
            detail.source_id,
            pluralize(detail.fact_count, "fact") if detail.fact_count else "",
            pluralize(detail.extraction_issue_count, "issue")
            if detail.extraction_issue_count
            else "",
        )
        if item
    )
    detail_path = source_detail_path(detail.source_id)
    bubbles = "\n".join(
        render_source_assignment_bubble(detail.source_id, bubble, return_to=detail_path)
        for bubble in detail.wiki_bubbles
    )
    title = detail.title or detail.source_id
    return f"""
<section class="section detail-hero" data-testid="source-detail-hero">
  <div class="detail-heading">
    <div>
      <p class="eyebrow">Source</p>
      <h2 class="detail-title">{escape(title)}</h2>
      <div class="muted">{escape(meta)}</div>
    </div>
    <div class="detail-actions">
      <div class="bubbles">{bubbles}</div>
    </div>
  </div>
</section>
{render_source_repair(detail, fix_enabled)}
{_render_detail_issues(detail)}
{render_detail_facts(detail, llm_review_enabled)}
{_render_source_actions(detail.source_id)}
"""


def _render_source_actions(source_id: str) -> str:
    return f"""
<section class="section source-actions" data-testid="source-actions">
  <h2>Source Actions</h2>
  <div class="source-actions-row">
    {render_delete_source_form(source_id)}
  </div>
</section>
"""


def _render_detail_issues(detail: SourceDetailView) -> str:
    if not detail.extraction_issues:
        return '<section class="section" data-testid="source-issues"><h2>Issues</h2><p class="empty">No extraction issues.</p></section>'
    issues = "\n".join(
        _render_detail_issue(detail.source_id, index, issue)
        for index, issue in enumerate(detail.extraction_issues)
    )
    return (
        f'<section class="section" data-testid="source-issues"><h2>Issues</h2><div class="issue-list">{issues}</div></section>'
    )


def _render_detail_issue(source_id: str, index: int, issue: str) -> str:
    rows = textarea_rows(issue, minimum=2, maximum=6)
    return f"""
<article class="issue-row" data-issue-index="{index}">
  <form method="post" action="/source-repair" class="editable-text-form issue-text-form">
    {repair_hidden_fields(source_id)}
    {hidden_input("issue_index", str(index))}
    <textarea class="editable-textarea" name="issue_text" rows="{rows}" aria-label="Issue text">{escape(issue)}</textarea>
    {render_icon_button("Save issue", icon="✓", variant="save")}
  </form>
  <div class="row-tools">
    <form method="post" action="/source-repair" class="inline-action-form">
      {repair_hidden_fields(source_id)}
      {render_icon_button("Remove issue", icon=CLOSE_ICON, name="delete_issue", value=str(index), variant="danger", raw=True)}
    </form>
  </div>
</article>
"""
