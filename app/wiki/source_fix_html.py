"""HTML rendering for the LLM fix extraction form and diff results."""

from __future__ import annotations

from html import escape

from .source_detail import SourceDetailView
from .source_fix import SOURCE_FIX_MODEL, SourceFixResult


def render_source_fix_form(detail: SourceDetailView, fix_enabled: bool) -> str:
    fix_form = _render_fix_form(detail.source_id) if fix_enabled else ""
    return fix_form


def render_fix_result_message(result: SourceFixResult) -> str:
    if not result.changed:
        return f"no changes needed; model {result.model}"
    parts: list[str] = []
    if result.fact_diffs:
        parts.append(f"{len(result.fact_diffs)} fact(s) fixed")
    if result.metadata_diffs:
        fields = ", ".join(diff.field for diff in result.metadata_diffs)
        parts.append(f"metadata updated ({fields})")
    if result.issue_diffs:
        parts.append(f"{len(result.issue_diffs)} issue(s) fixed")
    parts.append(f"model {result.model}")
    return "; ".join(parts)


def _render_fix_form(source_id: str) -> str:
    return f"""\
<form method="post" action="/source-fix" class="fix-form">
  <input type="hidden" name="source_id" value="{escape(source_id)}">
  <h3>Fix Extraction</h3>
  <div class="muted">Model <code>{escape(SOURCE_FIX_MODEL)}</code></div>
  <div class="fix-instruction">
    <textarea name="instruction" placeholder="e.g. Change all dates to YYYY-MM-DD format, fix the spelling of Khrushchev"></textarea>
    <div class="source-save-bar">
      <button type="submit" class="button decision-action">Fix</button>
    </div>
  </div>
</form>
"""
