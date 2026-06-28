"""Dashboard source maintenance actions."""

from __future__ import annotations

from .dashboard_action_types import SourceFixRunner
from .dashboard_action_urls import dashboard_location, source_detail_location
from .dashboard_forms import DashboardForm
from .source_fix_html import render_fix_result_message
from .source_repair import source_record_from_repair_form
from .workflows import WikiWorkspace
from .workspace_queries import source_record


def apply_source_delete(workspace: WikiWorkspace, form: DashboardForm) -> str:
    source = workspace.delete_source(form.first("source_id").strip())
    return dashboard_location(f"deleted source {source.source_id}")


def apply_source_repair(workspace: WikiWorkspace, form: DashboardForm) -> str:
    source_id = form.first("source_id").strip()
    source = source_record(workspace, source_id)
    repaired = source_record_from_repair_form(source, form)
    workspace.repair_source(source_id, repaired)
    return source_detail_location(source_id, f"repaired source {source_id}")


def apply_source_fix(
    workspace: WikiWorkspace,
    form: DashboardForm,
    source_fixer: SourceFixRunner | None,
) -> str:
    if source_fixer is None:
        raise ValueError("source fix is not configured")
    source_id = form.first("source_id").strip()
    instruction = form.first("instruction").strip()
    if not instruction:
        raise ValueError("fix instructions are required")
    result = source_fixer(source_id, instruction)
    if result.source.source_id != source_id:
        raise ValueError("source_id cannot be changed during source fix")
    workspace.repair_source(source_id, result.source)
    message = render_fix_result_message(result)
    return source_detail_location(
        source_id,
        f"fixed source {source_id}: {message}",
    )
