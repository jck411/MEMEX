"""HTML controls for SourceRecord repair."""

from __future__ import annotations

from html import escape

from .dashboard_components_html import (
    CLOSE_ICON,
    hidden_input,
    render_icon_button,
    repair_hidden_fields,
    textarea_rows,
)
from .source_detail import SourceDetailView
from .source_fix_html import render_source_fix_form


def render_source_repair(
    detail: SourceDetailView,
    fix_enabled: bool,
) -> str:
    fix_form = render_source_fix_form(detail, fix_enabled)
    metadata = _render_extraction_metadata(detail)
    return f"""
<section class="section source-repair compact-source-repair" data-testid="source-repair">
  {fix_form}
  {metadata}
</section>
"""


def _render_extraction_metadata(detail: SourceDetailView) -> str:
    rows = "\n".join(
        (
            _render_metadata_text_field(
                detail.source_id,
                field_name="title",
                label="Title",
                value=detail.title,
                multiline=False,
                clearable=False,
            ),
            _render_metadata_text_field(
                detail.source_id,
                field_name="summary",
                label="Summary",
                value=detail.summary,
                multiline=True,
                clearable=True,
            ),
            _render_metadata_text_field(
                detail.source_id,
                field_name="document_date",
                label="Document date",
                value=detail.document_date,
                multiline=False,
                clearable=True,
            ),
            _render_metadata_text_field(
                detail.source_id,
                field_name="source_type",
                label="Source type",
                value=detail.source_type,
                multiline=False,
                clearable=True,
            ),
        )
    )
    return f"""
<div class="metadata-edit-list">
  {rows}
</div>
"""


def _render_metadata_text_field(
    source_id: str,
    *,
    field_name: str,
    label: str,
    value: str,
    multiline: bool,
    clearable: bool,
) -> str:
    field = (
        f'<textarea class="editable-textarea metadata-editor" name="{field_name}" '
        f'rows="{textarea_rows(value, minimum=2, maximum=5)}" '
        f'aria-label="{escape(label)}">{escape(value)}</textarea>'
        if multiline
        else (
            f'<input class="editable-textarea metadata-editor" type="text" '
            f'name="{field_name}" value="{escape(value)}" aria-label="{escape(label)}">'
        )
    )
    clear = _render_clear_metadata_form(source_id, field_name, label) if clearable else ""
    return f"""
<article class="metadata-row">
  <div class="fact-heading">
    <span class="field-label">{escape(label)}</span>
    {clear}
  </div>
  <form method="post" action="/source-repair" class="editable-text-form metadata-text-form">
    {repair_hidden_fields(source_id)}
    {field}
    {render_icon_button(f"Save {label.lower()}", icon="✓", variant="save")}
  </form>
</article>
"""


def _render_clear_metadata_form(source_id: str, field_name: str, label: str) -> str:
    label_text = label.lower()
    return f"""
<form method="post" action="/source-repair" class="inline-action-form">
  {repair_hidden_fields(source_id)}
  {hidden_input(field_name, "")}
  {render_icon_button(f"Clear {label_text}", icon=CLOSE_ICON, variant="danger", raw=True)}
</form>
"""
