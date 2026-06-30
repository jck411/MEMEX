#!/usr/bin/env python3
"""Start the MEMEX dashboard after clearing stale local server processes."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.wiki.dashboard_processes import (  # noqa: E402
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    cleanup_targets,
    require_canonical_dashboard_port,
    target_summary,
    terminate_processes,
)

DEFAULT_HOST = DASHBOARD_HOST
DEFAULT_PORT = DASHBOARD_PORT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fresh-start the local MEMEX dashboard server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--port",
        type=_canonical_port,
        default=DEFAULT_PORT,
        help=f"canonical dashboard port; alternate ports are not supported (default: {DEFAULT_PORT})",
    )
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be killed and started without changing processes",
    )
    return parser


def _canonical_port(value: str) -> int:
    port = int(value)
    try:
        return require_canonical_dashboard_port(port)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    targets = cleanup_targets(Path(args.repo_root), args.port)
    if targets:
        print(target_summary("clearing", targets))
    else:
        print("no existing MEMEX dashboard process found")

    command = server_command(
        Path(args.repo_root),
        host=args.host,
        port=args.port,
        env_file=args.env_file,
    )
    if args.dry_run:
        print("would start: " + " ".join(command))
        return 0

    terminate_processes(tuple(targets))
    print(f"starting MEMEX dashboard at http://{args.host}:{args.port}/")
    os.execv(sys.executable, command)
    return 0


def server_command(
    repo_root: Path,
    *,
    host: str,
    port: int,
    env_file: str,
) -> list[str]:
    return [
        sys.executable,
        str(repo_root / "scripts" / "wiki_dev.py"),
        "--repo-root",
        str(repo_root),
        "serve-dashboard",
        "--host",
        host,
        "--port",
        str(port),
        "--env-file",
        env_file,
    ]


if __name__ == "__main__":
    raise SystemExit(main())
