#!/usr/bin/env python3
"""Validate MEMEX V2 source persistence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.wiki.source_validation import (  # noqa: E402
    format_source_validation_report,
    validate_source_workspace,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate V2 source records, source assets, ledger references, and builds"
    )
    parser.add_argument("--repo-root", default=ROOT, help="repository root")
    parser.add_argument("--data-dir", default="data", help="data directory under repo root")
    parser.add_argument("--vault-dir", default="vault", help="vault directory under repo root")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root)
    data_root = repo_root / args.data_dir
    vault_root = repo_root / args.vault_dir
    report = validate_source_workspace(data_root, vault_root=vault_root)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(format_source_validation_report(report))
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
