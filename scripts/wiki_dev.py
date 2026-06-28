#!/usr/bin/env python3
"""Developer CLI for the MEMEX V2 wiki slice."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.wiki.dashboard import (  # noqa: E402
    SourceDashboardFilter,
    filter_sources,
    status_label,
)
from app.wiki.dashboard_server import run_dashboard_server  # noqa: E402
from app.wiki.model_profiles import (  # noqa: E402
    extraction_model_readiness,
    extraction_routes_for_profile,
    merged_env,
)
from app.wiki.openrouter_build import (  # noqa: E402
    OPENROUTER_WIKI_BUILD_MODEL,
    OpenRouterWikiBuildProvider,
)
from app.wiki.openrouter_review import (  # noqa: E402
    OPENROUTER_REVIEW_MODEL,
    OpenRouterReviewProvider,
)
from app.wiki.records import SourceRecord  # noqa: E402
from app.wiki.review import ReviewResult  # noqa: E402
from app.wiki.builders import FixtureWikiBuildProvider  # noqa: E402
from app.wiki.reviewers import FixtureReviewProvider  # noqa: E402
from app.wiki.workflows import WikiWorkspace, workspace_for_repo  # noqa: E402


def _load_source(path: str) -> SourceRecord:
    return SourceRecord.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _load_review_results(path: str) -> list[ReviewResult]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("decisions", payload) if isinstance(payload, dict) else payload
    return [
        ReviewResult(
            fact_id=item["fact_id"],
            ticked=item["ticked"],
            reason=item.get("reason", ""),
        )
        for item in items
    ]


def _load_fixture_provider(path: str) -> FixtureReviewProvider:
    return FixtureReviewProvider.from_payload(json.loads(Path(path).read_text(encoding="utf-8")))


def _status_text(status) -> str:
    return f"{status.wiki_id}: {status_label(status)}"


def _bubble_text(bubble) -> str:
    mark = "x" if bubble.assigned else " "
    return f"[{mark} {bubble.wiki_id}:{bubble.state}]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MEMEX V2 wiki developer workflow")
    parser.add_argument("--repo-root", default=ROOT, help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_wiki = subparsers.add_parser("add-wiki", help="register a wiki")
    add_wiki.add_argument("wiki_id")
    add_wiki.add_argument("title")
    add_wiki.add_argument("path")
    add_wiki.add_argument("--description", default="")

    delete_wiki = subparsers.add_parser("delete-wiki", help="delete a wiki")
    delete_wiki.add_argument("wiki_id")

    import_source = subparsers.add_parser("import-source", help="import a source JSON file")
    import_source.add_argument("source_json")

    extract_text = subparsers.add_parser(
        "extract-text",
        help="extract and import a local text or markdown source",
    )
    extract_text.add_argument("source_id")
    extract_text.add_argument("text_path")
    extract_text.add_argument("--title", default="")
    extract_text.add_argument("--document-date", default=None)
    extract_text.add_argument("--source-type", default="")

    assign = subparsers.add_parser("assign", help="assign a source to a wiki")
    assign.add_argument("wiki_id")
    assign.add_argument("source_id")

    unassign = subparsers.add_parser("unassign", help="unassign a source from a wiki")
    unassign.add_argument("wiki_id")
    unassign.add_argument("source_id")

    status = subparsers.add_parser("status", help="show wiki status")
    status.add_argument("wiki_id")

    dashboard = subparsers.add_parser("dashboard", help="show wiki/source dashboard")
    dashboard.add_argument("--search", default="")
    dashboard.add_argument("--unassigned", action="store_true")
    dashboard.add_argument("--needs-review", action="store_true")
    dashboard.add_argument("--needs-build", action="store_true")
    dashboard.add_argument("--has-issues", action="store_true")

    serve_dashboard = subparsers.add_parser(
        "serve-dashboard",
        help="serve the local wiki dashboard",
    )
    serve_dashboard.add_argument("--host", default="127.0.0.1")
    serve_dashboard.add_argument("--port", type=int, default=8765)
    serve_dashboard.add_argument("--env-file", default=None)

    model_profiles = subparsers.add_parser(
        "model-profiles", help="show direct extraction model candidates"
    )
    model_profiles.add_argument("--env-file", default=".env")

    delta = subparsers.add_parser("review-delta", help="show facts needing review")
    delta.add_argument("wiki_id")

    review = subparsers.add_parser("review", help="apply review decisions for one source")
    review.add_argument("wiki_id")
    review.add_argument("source_id")
    review.add_argument("decisions_json")
    review.add_argument("--reviewed-at", default="")

    fixture = subparsers.add_parser(
        "review-fixture",
        help="review pending source facts with a fixture decision JSON file",
    )
    fixture.add_argument("wiki_id")
    fixture.add_argument("source_id")
    fixture.add_argument("decisions_json")
    fixture.add_argument("--reviewed-at", default="")

    llm_review = subparsers.add_parser(
        "review-llm",
        help="review pending source facts with the configured LLM provider",
    )
    llm_review.add_argument("wiki_id")
    llm_review.add_argument("source_id")
    llm_review.add_argument("--env-file", default=".env")
    llm_review.add_argument("--model", default=OPENROUTER_REVIEW_MODEL)
    llm_review.add_argument("--max-tokens", type=int, default=2048)
    llm_review.add_argument("--reviewed-at", default="")

    build = subparsers.add_parser("build", help="build a wiki markdown page with the LLM")
    build.add_argument("wiki_id")
    build.add_argument("--env-file", default=".env")
    build.add_argument("--model", default=OPENROUTER_WIKI_BUILD_MODEL)
    build.add_argument("--max-tokens", type=int, default=8192)
    build.add_argument(
        "--fixture",
        action="store_true",
        help="use deterministic fixture synthesis instead of OpenRouter",
    )

    return parser


CommandHandler = Callable[[argparse.Namespace, WikiWorkspace], int]


def _run_add_wiki(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    wiki = workspace.add_wiki(
        args.wiki_id,
        args.title,
        args.path,
        description=args.description,
    )
    print(f"added wiki {wiki.wiki_id} -> {wiki.path}")
    return 0


def _run_delete_wiki(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    wiki = workspace.delete_wiki(args.wiki_id)
    print(f"deleted wiki {wiki.wiki_id} -> {wiki.path}")
    return 0


def _run_import_source(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    source = workspace.import_source(_load_source(args.source_json))
    print(f"imported source {source.source_id} ({len(source.facts)} facts)")
    return 0


def _run_extract_text(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    result = workspace.import_text_source(
        args.text_path,
        args.source_id,
        title=args.title,
        document_date=args.document_date,
        source_type=args.source_type,
    )
    source = result.source
    if result.duplicate:
        print(f"duplicate source {args.source_id}; showing existing {source.source_id}")
        return 0
    issue_text = f"; issues={len(source.extraction_issues)}" if source.extraction_issues else ""
    print(f"extracted source {source.source_id} ({len(source.facts)} facts){issue_text}")
    return 0


def _run_assign(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    print(_status_text(workspace.assign_source(args.wiki_id, args.source_id)))
    return 0


def _run_unassign(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    print(_status_text(workspace.unassign_source(args.wiki_id, args.source_id)))
    return 0


def _run_status(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    print(_status_text(workspace.status(args.wiki_id)))
    return 0


def _run_dashboard(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    snapshot = workspace.dashboard()
    print("Wikis")
    for wiki in snapshot.wikis:
        print(
            f"{wiki.wiki_id}\t{wiki.state}\t"
            f"assigned={wiki.assigned_source_count}\t"
            f"review_delta={wiki.review_delta_count}\t"
            f"accepted={wiki.accepted_fact_count}\t"
            f"{wiki.title}\t{wiki.path}"
        )
    print("")
    print("Sources")
    source_filter = SourceDashboardFilter(
        search=args.search,
        unassigned=args.unassigned,
        needs_review=args.needs_review,
        needs_build=args.needs_build,
        has_issues=args.has_issues,
    )
    for source in filter_sources(snapshot.sources, source_filter):
        bubbles = " ".join(_bubble_text(bubble) for bubble in source.wiki_bubbles)
        print(
            f"{source.source_id}\t{source.title}\t"
            f"facts={source.fact_count}\t"
            f"issues={source.extraction_issue_count}\t"
            f"{bubbles}"
        )
    return 0


def _run_serve_dashboard(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    env_file = Path(args.env_file) if args.env_file else Path(args.repo_root) / ".env"
    run_dashboard_server(
        workspace,
        host=args.host,
        port=args.port,
        env_file=env_file,
    )
    return 0


def _run_model_profiles(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    del workspace
    for readiness in extraction_model_readiness(merged_env(args.env_file)):
        profile = readiness.profile
        configured = "yes" if readiness.configured else f"missing {profile.env_key}"
        enabled = "yes" if profile.enabled else "no"
        strict = "yes" if profile.schema_strict else "no"
        routes = ", ".join(
            route.format_family for route in extraction_routes_for_profile(profile.profile_id)
        )
        print(f"{profile.profile_id}\tconfigured={configured}\tenabled={enabled}")
        print(f"  model: {profile.model}")
        print(f"  formats: {', '.join(profile.input_formats)}")
        print(f"  structured: {profile.structured_output}")
        print(f"  schema: {profile.schema_name} strict={strict}")
        print(f"  default routes: {routes or 'none'}")
        print(f"  parameters: {', '.join(profile.parameter_notes)}")
    return 0


def _run_review_delta(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    for fact in workspace.review_delta(args.wiki_id):
        print(f"{fact.source_id}\t{fact.fact_id}\t{fact.text}")
    return 0


def _print_review_summary(result) -> None:
    print(
        f"applied {result.applied_count}; "
        f"remaining_review={result.remaining_review_count}; "
        f"{_status_text(result.status)}"
    )


def _run_review(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    result = workspace.review_source(
        args.wiki_id,
        args.source_id,
        _load_review_results(args.decisions_json),
        reviewed_at=args.reviewed_at,
    )
    _print_review_summary(result)
    return 0


def _run_review_fixture(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    result = workspace.review_source_with_provider(
        args.wiki_id,
        args.source_id,
        _load_fixture_provider(args.decisions_json),
        reviewed_at=args.reviewed_at,
    )
    _print_review_summary(result)
    return 0


def _run_review_llm(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = Path(args.repo_root) / env_file
    result = workspace.review_source_with_provider(
        args.wiki_id,
        args.source_id,
        OpenRouterReviewProvider(
            api_key=merged_env(env_file).get("OPENROUTER_API_KEY", ""),
            model=args.model,
            max_tokens=args.max_tokens,
        ),
        reviewed_at=args.reviewed_at,
    )
    _print_review_summary(result)
    return 0


def _run_build(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    if args.fixture:
        result = workspace.build_wiki(args.wiki_id, FixtureWikiBuildProvider())
        print(f"built {result.path}; {_status_text(result.status)}")
        return 0
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = Path(args.repo_root) / env_file
    result = workspace.build_wiki(
        args.wiki_id,
        OpenRouterWikiBuildProvider(
            api_key=merged_env(env_file).get("OPENROUTER_API_KEY", ""),
            model=args.model,
            max_tokens=args.max_tokens,
        ),
    )
    print(f"built {result.path}; {_status_text(result.status)}")
    return 0


_COMMAND_HANDLERS: dict[str, CommandHandler] = {
    "add-wiki": _run_add_wiki,
    "assign": _run_assign,
    "build": _run_build,
    "dashboard": _run_dashboard,
    "delete-wiki": _run_delete_wiki,
    "extract-text": _run_extract_text,
    "import-source": _run_import_source,
    "model-profiles": _run_model_profiles,
    "review": _run_review,
    "review-delta": _run_review_delta,
    "review-fixture": _run_review_fixture,
    "review-llm": _run_review_llm,
    "serve-dashboard": _run_serve_dashboard,
    "status": _run_status,
    "unassign": _run_unassign,
}


def run(args: argparse.Namespace, workspace: WikiWorkspace) -> int:
    try:
        handler = _COMMAND_HANDLERS[args.command]
    except KeyError as exc:
        raise ValueError(f"unknown command {args.command!r}") from exc
    return handler(args, workspace)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args, workspace_for_repo(args.repo_root))


if __name__ == "__main__":
    raise SystemExit(main())
