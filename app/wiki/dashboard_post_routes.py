"""POST route handling for the local wiki dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .dashboard_assignment_actions import apply_assignment
from .dashboard_forms import (
    DashboardForm,
    parse_multipart_form,
    parse_urlencoded_form,
    quote_message,
    safe_return_to,
)
from .dashboard_review_actions import apply_source_decisions, apply_source_llm_review
from .dashboard_runtime import DashboardRuntime
from .dashboard_source_actions import (
    apply_source_delete,
    apply_source_fix,
    apply_source_repair,
)
from .dashboard_source_ingest_actions import apply_text_source, apply_upload
from .dashboard_wiki_actions import (
    apply_add_wiki,
    apply_wiki_delete,
    apply_wiki_description,
)

PostHandler = Callable[[DashboardRuntime, DashboardForm], str]


def dashboard_post_location(
    runtime: DashboardRuntime,
    path: str,
    content_type: str,
    body: bytes,
) -> str | None:
    route = _POST_ROUTES.get(path)
    if route is None:
        return None
    try:
        form = route.parse(content_type, body)
        return route.handle(runtime, form)
    except Exception as error:  # pragma: no cover - surfaced in UI
        return f"/?message={quote_message(str(error))}"


@dataclass(frozen=True)
class _PostRoute:
    handle: PostHandler
    multipart: bool = False

    def parse(self, content_type: str, body: bytes) -> DashboardForm:
        if self.multipart:
            return parse_multipart_form(content_type, body)
        return parse_urlencoded_form(body)


def _post_add_wiki(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_add_wiki(runtime.workspace, form)


def _post_assign(runtime: DashboardRuntime, form: DashboardForm) -> str:
    apply_assignment(runtime.workspace, form)
    return safe_return_to(form.first("return_to"))


def _post_upload(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_upload(
        runtime.workspace,
        form,
        runtime.source_extractor,
        runtime.extraction_model_spec,
    )


def _post_text_source(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_text_source(
        runtime.workspace,
        form,
        runtime.source_extractor,
        runtime.extraction_model_spec,
    )


def _post_source_decisions(runtime: DashboardRuntime, form: DashboardForm) -> str:
    apply_source_decisions(runtime.workspace, form)
    return safe_return_to(form.first("return_to"))


def _post_source_repair(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_source_repair(runtime.workspace, form)


def _post_source_llm_review(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_source_llm_review(form, runtime.source_reviewer)


def _post_source_fix(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_source_fix(runtime.workspace, form, runtime.source_fixer)


def _post_delete_source(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_source_delete(runtime.workspace, form)


def _post_delete_wiki(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_wiki_delete(runtime.workspace, form)


def _post_build(runtime: DashboardRuntime, form: DashboardForm) -> str:
    wiki_id = form.first("wiki_id")
    runtime.workspace.build_wiki(wiki_id)
    return f"/?message=built+{wiki_id}"


def _post_wiki_description(runtime: DashboardRuntime, form: DashboardForm) -> str:
    return apply_wiki_description(runtime.workspace, form)


_POST_ROUTES = {
    "/add-wiki": _PostRoute(_post_add_wiki),
    "/assign": _PostRoute(_post_assign),
    "/upload": _PostRoute(_post_upload, multipart=True),
    "/text-source": _PostRoute(_post_text_source),
    "/source-decisions": _PostRoute(_post_source_decisions),
    "/source-repair": _PostRoute(_post_source_repair),
    "/source-llm-review": _PostRoute(_post_source_llm_review),
    "/source-fix": _PostRoute(_post_source_fix),
    "/delete-source": _PostRoute(_post_delete_source),
    "/delete-wiki": _PostRoute(_post_delete_wiki),
    "/build": _PostRoute(_post_build),
    "/wiki-description": _PostRoute(_post_wiki_description),
}
