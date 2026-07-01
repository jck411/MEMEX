#!/usr/bin/env python3
"""Run direct-provider LLM extraction into MEMEX source records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.wiki.model_profiles import merged_env  # noqa: E402
from app.wiki.source_extraction import (  # noqa: E402
    SourceExtractionJob,
    extract_source_to_workspace,
)
from app.wiki.workflows import workspace_for_repo  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract one source with the default LLM")
    parser.add_argument("source_id")
    parser.add_argument("path")
    parser.add_argument("--repo-root", default=ROOT)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--model", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--source-type", default="")
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="extract even when the original matches an existing source",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    env_file = Path(args.env_file) if args.env_file else Path(args.repo_root) / ".env"
    try:
        result = extract_source_to_workspace(
            workspace_for_repo(args.repo_root),
            SourceExtractionJob(
                source_id=args.source_id,
                path=args.path,
                title=args.title,
                source_type=args.source_type,
                model_spec=args.model,
                allow_duplicate=args.allow_duplicate,
            ),
            merged_env(env_file),
        )
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 2
    if result.duplicate:
        print(f"duplicate source {args.source_id}; showing existing {result.source.source_id}")
    else:
        print(
            f"extracted source {result.source.source_id} "
            f"({len(result.source.facts)} facts; model={result.model_spec})"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
