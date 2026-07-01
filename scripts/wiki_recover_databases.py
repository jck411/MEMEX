#!/usr/bin/env python3
"""Recover old Proxmox app databases into MEMEX source-draft markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.wiki.database_recovery import run_recovery  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export old app databases into data/source-drafts markdown files."
    )
    parser.add_argument(
        "--out-dir",
        default=ROOT / "data" / "source-drafts" / "recovered-databases",
        type=Path,
    )
    parser.add_argument("--ssh-host", default="proxmox-tunnel")
    parser.add_argument(
        "--skip-librechat",
        action="store_true",
        help="skip the LibreChat MongoDB export",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    written = run_recovery(
        args.out_dir,
        ssh_host=args.ssh_host,
        include_librechat=not args.skip_librechat,
    )
    print(f"wrote {len(written)} markdown drafts under {args.out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
