"""HTML rendering for dashboard wiki rows."""

from __future__ import annotations

from html import escape

from .dashboard import WikiDashboardRow, WikiDashboardSnapshot
from .dashboard_components_html import (
    pluralize,
    render_delete_wiki_form,
    render_status_pill,
    wiki_detail_path,
    wiki_facts_path,
)


def render_wikis(snapshot: WikiDashboardSnapshot) -> str:
    heading = _render_wiki_heading()
    if not snapshot.wikis:
        return f'<section class="section" data-testid="wikis-section">{heading}<p class="empty">No wikis yet.</p></section>'
    rows = "\n".join(_render_wiki(row) for row in snapshot.wikis)
    return f'<section class="section" data-testid="wikis-section">{heading}<div class="wiki-grid">{rows}</div></section>'


def _render_wiki_heading() -> str:
    return """
<details class="wiki-create">
  <summary class="section-heading wiki-heading">
    <h2>Wikis</h2>
    <span class="button wiki-create-open-label">Add Wiki</span>
    <span class="button button-danger wiki-create-close-label">Cancel</span>
  </summary>
  <form method="post" action="/add-wiki" class="wiki-create-form">
    <div class="wiki-create-fields">
      <label class="wiki-create-field wiki-create-field-wide">
        <span class="field-label">Name</span>
        <input type="text" name="title" placeholder="Research" aria-label="Wiki name" required>
        <small class="field-help">MEMEX creates the internal id and Obsidian file automatically from this name, like <code>research.md</code>.</small>
      </label>
      <label class="wiki-create-field wiki-create-field-wide">
        <span class="field-label">Description</span>
        <textarea name="description" rows="4" placeholder="What facts belong in this wiki?" aria-label="Wiki description"></textarea>
        <small class="field-help">Scope instructions the LLM uses when reviewing facts for this wiki.</small>
      </label>
    </div>
    <div class="wiki-create-actions">
      <button type="submit" class="button button-save">Create Wiki</button>
    </div>
  </form>
</details>
"""


def _render_wiki(row: WikiDashboardRow) -> str:
    build = ""
    if row.state == "needs_build":
        build = f"""
      <form method="post" action="/build" class="wiki-build-form">
        <input type="hidden" name="wiki_id" value="{escape(row.wiki_id)}">
        <button type="submit" class="button button-build build-button">Build</button>
      </form>
"""
    delete = render_delete_wiki_form(row.wiki_id, row.title)
    controls = f"""
  <div class="wiki-controls">
    <div class="wiki-actions">
      {build}
      {delete}
    </div>
    <div class="wiki-stats">
      {render_status_pill(row.state)}
      <span class="wiki-stat">{pluralize(row.assigned_source_count, "source")}</span>
      <span class="wiki-stat">{pluralize(row.review_delta_count, "review")}</span>
      <span class="wiki-stat">{row.accepted_fact_count} accepted</span>
    </div>
  </div>"""
    return f"""
<article class="wiki-row" data-testid="wiki-row" data-wiki-id="{escape(row.wiki_id, quote=True)}">
  <div class="wiki-main">
    <div class="row-title">{escape(row.title)}</div>
    <a class="wiki-link" href="{wiki_detail_path(row.wiki_id)}">
      {escape(_wiki_file_location(row))}
    </a>
    <div class="wiki-row-links">
      <a href="{wiki_facts_path(row.wiki_id)}">Facts used</a>
    </div>
  </div>
  {controls}
  {_render_description_form(row)}
</article>
"""


def _wiki_file_location(row: WikiDashboardRow) -> str:
    return row.file_location or row.path


def _render_description_form(row: WikiDashboardRow) -> str:
    rows = min(8, max(3, len(row.description.splitlines()) + 1))
    label = escape(f"{row.title} description")
    return f"""
<details class="wiki-description-edit">
  <summary>Description</summary>
  <form method="post" action="/wiki-description" class="wiki-description-form">
    <input type="hidden" name="wiki_id" value="{escape(row.wiki_id)}">
    <div class="wiki-description-field">
      <textarea name="description" rows="{rows}" aria-label="{label}">{escape(row.description)}</textarea>
      <div class="wiki-description-save">
        <button type="submit" class="button button-save">Save</button>
      </div>
    </div>
  </form>
</details>
"""
