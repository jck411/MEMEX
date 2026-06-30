"""Dashboard source maintenance actions."""

from __future__ import annotations

from .dashboard_action_types import SourceFixRunner
from .dashboard_action_urls import dashboard_location, source_detail_location
from .dashboard_forms import DashboardForm
from .records import SourceRecord
from .source_fix_html import render_fix_result_message
from .source_repair import repair_source_record
from .workflows import WikiWorkspace
from .workspace_queries import source_record


def source_record_from_repair_form(source: SourceRecord, form: DashboardForm) -> SourceRecord:
    partial_repair = form.flag("partial_repair")
    submitted_fact_texts = _paired_form_values(
        form.all("fact_id"),
        form.all("fact_text"),
        "fact",
    )
    current_fact_ids = {fact.fact_id for fact in source.facts}
    submitted_fact_ids = set(submitted_fact_texts)
    fact_texts = {
        fact_id: text
        for fact_id, text in submitted_fact_texts.items()
        if fact_id in current_fact_ids
    }
    added_fact_texts = [
        text for fact_id, text in submitted_fact_texts.items() if fact_id not in current_fact_ids
    ]
    added_fact_texts.extend(form.all("new_fact_text"))

    issue_texts = {
        int(index): text
        for index, text in _paired_form_values(
            form.all("issue_index"),
            form.all("issue_text"),
            "issue",
        ).items()
    }
    submitted_issue_indexes = set(issue_texts)
    deleted_fact_ids = set(form.all("delete_fact"))
    deleted_issue_indexes = {int(value) for value in form.all("delete_issue") if value.strip()}
    if not partial_repair:
        deleted_fact_ids |= current_fact_ids - submitted_fact_ids
        deleted_issue_indexes |= set(range(len(source.extraction_issues))) - submitted_issue_indexes
    return repair_source_record(
        source,
        title=_form_text(form, "title", source.title),
        summary=_form_text(form, "summary", source.summary),
        document_date=_form_optional_text(form, "document_date", source.document_date),
        source_type=_form_optional_text(form, "source_type", source.source_type),
        fact_texts=fact_texts,
        deleted_fact_ids=tuple(deleted_fact_ids),
        added_fact_texts=added_fact_texts,
        added_fact_provenance={"repair": "dashboard"},
        issue_texts=issue_texts,
        deleted_issue_indexes=tuple(deleted_issue_indexes),
    )


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


def _paired_form_values(
    keys: tuple[str, ...],
    values: tuple[str, ...],
    label: str,
) -> dict[str, str]:
    if len(keys) != len(values):
        raise ValueError(f"{label} form values are incomplete")
    return {key: value for key, value in zip(keys, values, strict=True) if key.strip()}


def _optional_text(value: str) -> str | None:
    value = value.strip()
    return value or None


def _form_text(form: DashboardForm, name: str, default: str) -> str:
    if name not in form.fields:
        return default
    return form.first(name).strip()


def _form_optional_text(
    form: DashboardForm,
    name: str,
    default: str | None,
) -> str | None:
    if name not in form.fields:
        return default
    return _optional_text(form.first(name))
