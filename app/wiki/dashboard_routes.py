"""Route handling for the local wiki dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import parse_qs, unquote, urlparse

from .dashboard import SourceDashboardFilter
from .dashboard_forms import DashboardForm
from .dashboard_html import DashboardRenderOptions, render_dashboard_html
from .dashboard_post_routes import dashboard_post_location
from .dashboard_runtime import DashboardRuntime
from .provider_balances import ProviderBalance
from .source_detail_html import render_source_detail_html
from .wiki_facts_html import render_wiki_facts_html
from .wiki_page_html import render_wiki_page_html
from .workspace_queries import (
    dashboard_view,
    duplicate_source_hints,
    wiki_facts_page_view,
    wiki_page_view,
)


@dataclass(frozen=True)
class DashboardResponse:
    status: HTTPStatus
    body: str = ""
    content_type: str = "text/plain; charset=utf-8"
    location: str = ""


def handle_dashboard_get(runtime: DashboardRuntime, target: str) -> DashboardResponse:
    parsed = urlparse(target)
    params = parse_qs(parsed.query)
    if parsed.path in ("", "/", "/dashboard"):
        return _html_response(
            render_dashboard_html(
                dashboard_view(runtime.workspace),
                _dashboard_render_options(runtime, params),
            )
        )
    if parsed.path.startswith("/source/"):
        return _render_source_detail(runtime, parsed.path, params)
    if parsed.path.startswith("/wiki/"):
        if parsed.path.endswith("/facts"):
            return _render_wiki_facts(runtime, parsed.path, params)
        return _render_wiki_page(runtime, parsed.path, params)
    return _text_response(HTTPStatus.NOT_FOUND, "not found")


def handle_dashboard_post(
    runtime: DashboardRuntime,
    target: str,
    content_type: str,
    body: bytes,
) -> DashboardResponse:
    parsed = urlparse(target)
    location = dashboard_post_location(runtime, parsed.path, content_type, body)
    if location is None:
        return _text_response(HTTPStatus.NOT_FOUND, "not found")
    return _redirect_response(location)


def _render_wiki_page(
    runtime: DashboardRuntime,
    path: str,
    params: dict[str, list[str]],
) -> DashboardResponse:
    wiki_id = unquote(path.removeprefix("/wiki/"))
    if not wiki_id:
        return _text_response(HTTPStatus.NOT_FOUND, "not found")
    try:
        page = wiki_page_view(runtime.workspace, wiki_id)
    except KeyError:
        return _text_response(HTTPStatus.NOT_FOUND, "not found")
    return _html_response(
        render_wiki_page_html(
            snapshot=dashboard_view(runtime.workspace),
            wiki=page.wiki,
            status=page.status,
            markdown=page.markdown,
            provider_balances=_safe_provider_balances(runtime.balance_provider),
            message=_first(params, "message"),
            message_type=_first(params, "message_type"),
        )
    )


def _render_wiki_facts(
    runtime: DashboardRuntime,
    path: str,
    params: dict[str, list[str]],
) -> DashboardResponse:
    wiki_id = unquote(path.removeprefix("/wiki/").removesuffix("/facts").rstrip("/"))
    if not wiki_id:
        return _text_response(HTTPStatus.NOT_FOUND, "not found")
    try:
        facts_view = wiki_facts_page_view(runtime.workspace, wiki_id)
    except KeyError:
        return _text_response(HTTPStatus.NOT_FOUND, "not found")
    return _html_response(
        render_wiki_facts_html(
            snapshot=dashboard_view(runtime.workspace),
            facts_view=facts_view,
            provider_balances=_safe_provider_balances(runtime.balance_provider),
            message=_first(params, "message"),
            message_type=_first(params, "message_type"),
        )
    )


def _render_source_detail(
    runtime: DashboardRuntime,
    path: str,
    params: dict[str, list[str]],
) -> DashboardResponse:
    source_id = unquote(path.removeprefix("/source/"))
    if not source_id:
        return _text_response(HTTPStatus.NOT_FOUND, "not found")
    try:
        detail = runtime.workspace.source_detail(source_id)
    except KeyError:
        return _text_response(HTTPStatus.NOT_FOUND, "not found")
    return _html_response(
        render_source_detail_html(
            dashboard_view(runtime.workspace),
            detail,
            _source_render_options(runtime, params),
        )
    )


def _dashboard_render_options(
    runtime: DashboardRuntime,
    params: dict[str, list[str]],
) -> DashboardRenderOptions:
    options = _source_render_options(runtime, params)
    return DashboardRenderOptions(
        source_filter=_filter_from_params(params),
        message=options.message,
        message_type=options.message_type,
        provider_balances=options.provider_balances,
        extraction_enabled=options.extraction_enabled,
        extraction_model_spec=options.extraction_model_spec,
        source_fix_enabled=options.source_fix_enabled,
        source_llm_review_enabled=options.source_llm_review_enabled,
        duplicate_sources=duplicate_source_hints(runtime.workspace),
    )


def _source_render_options(
    runtime: DashboardRuntime,
    params: dict[str, list[str]],
) -> DashboardRenderOptions:
    return DashboardRenderOptions(
        message=_first(params, "message"),
        message_type=_first(params, "message_type"),
        provider_balances=_safe_provider_balances(runtime.balance_provider),
        extraction_enabled=runtime.source_extractor is not None,
        extraction_model_spec=runtime.extraction_model_spec,
        source_fix_enabled=runtime.source_fixer is not None,
        source_llm_review_enabled=runtime.source_reviewer is not None,
    )


def _safe_provider_balances(
    balance_provider,
) -> tuple[ProviderBalance, ...]:
    if balance_provider is None:
        return ()
    try:
        return tuple(balance_provider())
    except Exception as error:  # defensive UI fallback
        return (
            ProviderBalance(
                provider="provider_balances",
                status="error",
                summary="error",
                detail=str(error),
            ),
        )


def _filter_from_params(params: dict[str, list[str]]) -> SourceDashboardFilter:
    form = DashboardForm(
        fields={name: tuple(values) for name, values in params.items()},
        files={},
    )
    return SourceDashboardFilter(
        search=form.first("search"),
        unassigned=form.flag("unassigned"),
        needs_review=form.flag("needs_review"),
        needs_build=form.flag("needs_build"),
        has_issues=form.flag("has_issues"),
    )


def _first(params: dict[str, list[str]], name: str) -> str:
    values = params.get(name)
    return values[0] if values else ""


def _html_response(html: str) -> DashboardResponse:
    return DashboardResponse(
        status=HTTPStatus.OK,
        body=html,
        content_type="text/html; charset=utf-8",
    )


def _text_response(status: HTTPStatus, text: str) -> DashboardResponse:
    return DashboardResponse(status=status, body=text)


def _redirect_response(location: str) -> DashboardResponse:
    return DashboardResponse(status=HTTPStatus.SEE_OTHER, location=location)
