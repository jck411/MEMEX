"""Dashboard wiki lifecycle actions."""

from __future__ import annotations

import re

from .dashboard_action_urls import dashboard_location
from .dashboard_forms import DashboardForm
from .workflows import WikiWorkspace


def apply_add_wiki(workspace: WikiWorkspace, form: DashboardForm) -> str:
    title = form.first("title").strip()
    if not title:
        raise ValueError("wiki name is required")
    wiki_id = _wiki_id_from_title(title)
    wiki = workspace.add_wiki(
        wiki_id,
        title,
        f"{wiki_id}.md",
        description=form.first("description").strip(),
    )
    return dashboard_location(f"added wiki {wiki.wiki_id}")


def apply_wiki_delete(workspace: WikiWorkspace, form: DashboardForm) -> str:
    wiki = workspace.delete_wiki(form.first("wiki_id").strip())
    return dashboard_location(f"deleted wiki {wiki.wiki_id}")


def apply_wiki_description(workspace: WikiWorkspace, form: DashboardForm) -> str:
    wiki_id = form.first("wiki_id").strip()
    if not wiki_id:
        raise ValueError("wiki_id is required")
    workspace.update_wiki_description(wiki_id, form.first("description"))
    return dashboard_location(f"updated wiki description for {wiki_id}")


def _wiki_id_from_title(title: str) -> str:
    wiki_id = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip(".-_").lower()
    return wiki_id[:80].strip(".-_") or "wiki"
