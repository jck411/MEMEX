"""Dashboard source-to-wiki assignment actions."""

from __future__ import annotations

from .dashboard_forms import DashboardForm
from .workflows import WikiWorkspace


def apply_assignment(workspace: WikiWorkspace, form: DashboardForm) -> None:
    wiki_id = form.first("wiki_id")
    source_id = form.first("source_id")
    operation = form.first("operation")
    if operation == "assign":
        workspace.assign_source(wiki_id, source_id)
        return
    if operation == "unassign":
        workspace.unassign_source(wiki_id, source_id)
        return
    raise ValueError(f"unknown assignment operation {operation!r}")
