#!/usr/bin/env python3
"""Fetch provider API cost reports for MEMEX experiments."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.wiki.model_profiles import merged_env  # noqa: E402
from app.wiki.provider_balances import (  # noqa: E402
    format_provider_balance,
    provider_balance_readiness,
    provider_balance_snapshot,
)
from app.wiki.usage_costs import (  # noqa: E402
    fetch_anthropic_costs,
    fetch_openai_costs,
    format_cost_report,
    utc_cost_range,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show API cost reports")
    parser.add_argument("--env-file", default=ROOT / ".env")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument(
        "--provider",
        choices=("all", "openai", "anthropic"),
        default="all",
    )
    parser.add_argument("--line-items", action="store_true")
    parser.add_argument(
        "--balances",
        action="store_true",
        help="show provider balance or balance-capability status",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check credential readiness without calling provider APIs",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    env = merged_env(args.env_file)
    if args.balances:
        balances = provider_balance_readiness(env) if args.check else provider_balance_snapshot(env)
        for balance in balances:
            print(format_provider_balance(balance))
        return 0

    providers = _providers(args.provider)
    if args.check:
        for provider in providers:
            key = _env_key(provider)
            print(f"{provider}: {'configured' if env.get(key) else f'missing {key}'}")
        return 0

    start, end = utc_cost_range(args.days)
    for provider in providers:
        key = _env_key(provider)
        if not env.get(key):
            print(f"{provider}: missing {key}")
            continue
        try:
            report = _fetch(provider, env[key], start, end, args.line_items)
        except Exception as error:
            print(f"{provider}: {error}", file=sys.stderr)
            continue
        print(format_cost_report(report))
    return 0


def _providers(value: str) -> tuple[str, ...]:
    if value == "all":
        return ("openai", "anthropic")
    return (value,)


def _env_key(provider: str) -> str:
    if provider == "openai":
        return "OPENAI_ADMIN_KEY"
    if provider == "anthropic":
        return "ANTHROPIC_ADMIN_API_KEY"
    raise ValueError(f"unknown provider {provider!r}")


def _fetch(provider: str, key: str, start, end, line_items: bool):
    if provider == "openai":
        group_by = ("line_item",) if line_items else ()
        return fetch_openai_costs(key, start, end, group_by=group_by)
    if provider == "anthropic":
        group_by = ("description",) if line_items else ()
        return fetch_anthropic_costs(key, start, end, group_by=group_by)
    raise ValueError(f"unknown provider {provider!r}")


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
