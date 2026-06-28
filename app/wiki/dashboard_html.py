"""HTML rendering for the local wiki dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from urllib.parse import urlencode

from .dashboard import (
    SourceDashboardFilter,
    WikiDashboardSnapshot,
    filter_sources,
)
from .dashboard_components_html import (
    pluralize,
    render_dashboard_page,
    render_delete_source_form,
    render_source_assignment_bubble,
    source_detail_path,
)
from .dashboard_ingest_hints import DuplicateSourceHint
from .dashboard_ingest_html import render_ingest_forms
from .dashboard_scripts import dashboard_script
from .dashboard_wikis_html import render_wikis
from .provider_balances import ProviderBalance


@dataclass(frozen=True)
class DashboardRenderOptions:
    source_filter: SourceDashboardFilter = field(default_factory=SourceDashboardFilter)
    message: str = ""
    provider_balances: tuple[ProviderBalance, ...] = ()
    extraction_enabled: bool = False
    extraction_model_spec: str = ""
    duplicate_sources: tuple[DuplicateSourceHint, ...] = ()
    source_fix_enabled: bool = False
    source_llm_review_enabled: bool = False


def render_dashboard_html(
    snapshot: WikiDashboardSnapshot,
    options: DashboardRenderOptions | None = None,
) -> str:
    if options is None:
        options = DashboardRenderOptions()
    rows = filter_sources(snapshot.sources, options.source_filter)
    body = "\n".join(
        (
            render_wikis(snapshot),
            render_ingest_forms(
                extraction_enabled=options.extraction_enabled,
                extraction_model_spec=options.extraction_model_spec,
                duplicate_sources=options.duplicate_sources,
            ),
            _render_filters(options.source_filter),
            _render_sources(rows, options.source_filter),
        )
    )
    return render_dashboard_page(
        document_title="MEMEX Wiki",
        page_heading="Wiki Dashboard",
        snapshot=snapshot,
        provider_balances=options.provider_balances,
        message=options.message,
        body=body,
        scripts=dashboard_script(),
    )


def _render_filters(source_filter: SourceDashboardFilter) -> str:
    return f"""
<section class="filter-band" id="source-search" data-testid="source-filters">
  <h2>Search Sources</h2>
  <form method="get" action="/#source-search" class="filters">
    <input type="search" name="search" placeholder="Search sources" value="{escape(source_filter.search)}">
    <div class="filter-controls">
      {_checkbox("unassigned", "Unassigned", source_filter.unassigned)}
      {_checkbox("needs_review", "Fact Review", source_filter.needs_review)}
      {_checkbox("needs_build", "Wiki Build", source_filter.needs_build)}
      {_checkbox("has_issues", "Issues", source_filter.has_issues)}
      <button type="submit" class="button">Filter</button>
      <a class="button button-muted clear" href="/#source-search">Clear</a>
    </div>
  </form>
</section>
"""


def _render_sources(
    rows,
    source_filter: SourceDashboardFilter,
) -> str:
    if not rows:
        return '<section class="section" data-testid="sources-section"><h2>Sources</h2><p class="empty">No matching sources.</p></section>'
    query = _filter_query(source_filter)
    rendered = "\n".join(_render_source(row, query) for row in rows)
    return f'<section class="section" data-testid="sources-section"><h2>Sources</h2><div class="source-list">{rendered}</div></section>'


def _render_source(row, query: str) -> str:
    bubbles = "\n".join(
        render_source_assignment_bubble(row.source_id, bubble, query) for bubble in row.wiki_bubbles
    )
    actions = "\n".join(
        (bubbles, render_delete_source_form(row.source_id, "Delete source", icon=True))
    )
    summary = f'<p class="summary">{escape(row.summary)}</p>' if row.summary else ""
    meta = " · ".join(
        item
        for item in (
            row.source_type,
            row.document_date,
            pluralize(row.fact_count, "fact") if row.fact_count else "",
            pluralize(row.extraction_issue_count, "issue") if row.extraction_issue_count else "",
        )
        if item
    )
    href = source_detail_path(row.source_id)
    return f"""
<article class="source-row" data-testid="source-row" data-source-id="{escape(row.source_id, quote=True)}">
  <a class="source-link" href="{escape(href)}">
    <div class="row-title">{escape(row.title or row.source_id)}</div>
    <div class="muted">{escape(row.source_id)} · {escape(meta)}</div>
    {summary}
  </a>
  <div class="bubbles">{actions}</div>
</article>
"""


def _checkbox(name: str, label: str, checked: bool) -> str:
    checked_attr = " checked" if checked else ""
    return f'<label class="check-control"><input type="checkbox" name="{name}" value="1"{checked_attr}> {label}</label>'


def _filter_query(source_filter: SourceDashboardFilter) -> str:
    params: list[tuple[str, str]] = []
    if source_filter.search:
        params.append(("search", source_filter.search))
    for name in ("unassigned", "needs_review", "needs_build", "has_issues"):
        if getattr(source_filter, name):
            params.append((name, "1"))
    return urlencode(params)
