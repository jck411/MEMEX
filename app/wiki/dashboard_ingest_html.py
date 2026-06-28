"""HTML rendering for dashboard source ingestion forms."""

from __future__ import annotations

from html import escape

from .dashboard_components_html import render_busy_overlay
from .dashboard_ingest_hints import DuplicateSourceHint
from .dashboard_ingest_scripts import render_ingest_script
from .model_profiles import (
    DEFAULT_EXTRACTION_PROFILE_ID,
    ExtractionModelProfile,
    enabled_extraction_model_profiles,
)


def render_ingest_forms(
    *,
    extraction_enabled: bool,
    extraction_model_spec: str,
    duplicate_sources: tuple[DuplicateSourceHint, ...] = (),
) -> str:
    if not extraction_enabled:
        return ""
    return f"""
<section class="ingest-band" data-testid="ingest-section">
  <div class="ingest-heading">
    <h2>Add Source</h2>
    {_render_model_select(extraction_model_spec)}
  </div>
  <div class="ingest-forms">
    {_render_upload_form(extraction_model_spec)}
    {_render_text_form(extraction_model_spec)}
  </div>
  {_render_duplicate_dialog()}
  {render_busy_overlay(title="Uploading source", detail="Extracting durable facts with the selected model.")}
</section>
{render_ingest_script(duplicate_sources)}
"""


def _render_upload_form(extraction_model_spec: str) -> str:
    return _render_source_form(
        action="/upload",
        class_name="upload-form",
        fields="""
  <label class="file-picker">
    <input type="file" name="source_file" accept=".txt,.md,.markdown,.pdf,image/*" required>
    <span class="file-picker-btn">Choose File</span>
    <span class="file-picker-name">No file chosen</span>
  </label>
""",
        button="Upload",
        extraction_model_spec=extraction_model_spec,
        multipart=True,
    )


def _render_text_form(extraction_model_spec: str) -> str:
    return _render_source_form(
        action="/text-source",
        class_name="text-source-form",
        fields="""
  <input type="text" name="text_title" placeholder="Title">
  <textarea name="source_text" rows="2" placeholder="Paste text" required></textarea>
""",
        button="Add Text",
        extraction_model_spec=extraction_model_spec,
    )


def _render_source_form(
    *,
    action: str,
    class_name: str,
    fields: str,
    button: str,
    extraction_model_spec: str,
    multipart: bool = False,
) -> str:
    enctype = ' enctype="multipart/form-data"' if multipart else ""
    return f"""
<form method="post" action="{action}"{enctype} class="extract-form {class_name}">
  {_render_model_hidden(extraction_model_spec)}
{fields.rstrip()}
  <input type="hidden" name="allow_duplicate" value="">
  <button type="submit" class="button">{button}</button>
</form>
"""


def _render_model_select(extraction_model_spec: str) -> str:
    profiles = enabled_extraction_model_profiles()
    selected = _selected_profile_id(extraction_model_spec, profiles)
    options = "\n".join(_render_model_option(profile, selected) for profile in profiles)
    return f"""
  <label class="model-select">
    <span>Model</span>
    <select id="source-model-select" name="model_spec">{options}</select>
  </label>
"""


def _render_model_hidden(extraction_model_spec: str) -> str:
    selected = _selected_profile_id(
        extraction_model_spec,
        enabled_extraction_model_profiles(),
    )
    return f'<input type="hidden" name="model_spec" value="{escape(selected, quote=True)}">'


def _render_model_option(profile: ExtractionModelProfile, selected: str) -> str:
    selected_attr = " selected" if profile.profile_id == selected else ""
    label = f"{_provider_label(profile.provider)} {profile.model}"
    return f'<option value="{escape(profile.profile_id)}"{selected_attr}>{escape(label)}</option>'


def _selected_profile_id(
    requested: str,
    profiles: tuple[ExtractionModelProfile, ...],
) -> str:
    profile_ids = tuple(profile.profile_id for profile in profiles)
    if requested in profile_ids:
        return requested
    if DEFAULT_EXTRACTION_PROFILE_ID in profile_ids:
        return DEFAULT_EXTRACTION_PROFILE_ID
    return profile_ids[0] if profile_ids else requested


def _provider_label(provider: str) -> str:
    return {"openai": "OpenAI", "anthropic": "Anthropic"}.get(
        provider,
        provider.title(),
    )


def _render_duplicate_dialog() -> str:
    return """
<dialog class="duplicate-dialog" id="duplicate-upload-dialog">
  <h2>Duplicate source</h2>
  <p>
    This source already exists as
    <strong data-duplicate-source-label></strong>.
  </p>
  <div class="dialog-actions">
    <button type="button" class="button button-muted clear" data-duplicate-cancel>Cancel</button>
    <button type="button" class="button" data-duplicate-keep>Keep Duplicate</button>
  </div>
</dialog>
"""
