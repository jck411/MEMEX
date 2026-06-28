"""Provider usage and cost reporting helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OPENAI_COSTS_URL = "https://api.openai.com/v1/organization/costs"
ANTHROPIC_COSTS_URL = "https://api.anthropic.com/v1/organizations/cost_report"
ANTHROPIC_USAGE_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"
ANTHROPIC_VERSION = "2023-06-01"


@dataclass(frozen=True)
class CostLine:
    provider: str
    start: str
    end: str
    amount_usd: Decimal
    label: str = ""


@dataclass(frozen=True)
class CostReport:
    provider: str
    start: datetime
    end: datetime
    lines: tuple[CostLine, ...]

    @property
    def total_usd(self) -> Decimal:
        return sum((line.amount_usd for line in self.lines), Decimal("0"))


def utc_cost_range(days: int, now: datetime | None = None) -> tuple[datetime, datetime]:
    if days <= 0:
        raise ValueError("days must be positive")
    end = now or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    end = end.astimezone(UTC)
    return end - timedelta(days=days), end


def fetch_openai_costs(
    admin_key: str,
    start: datetime,
    end: datetime,
    *,
    group_by: tuple[str, ...] = (),
    opener: Callable[..., Any] = urlopen,
) -> CostReport:
    payload = _get_json(
        OPENAI_COSTS_URL,
        {
            "start_time": str(_unix_seconds(start)),
            "end_time": str(_unix_seconds(end)),
            "bucket_width": "1d",
            "limit": "180",
            "group_by": list(group_by),
        },
        {"Authorization": f"Bearer {admin_key}"},
        opener,
    )
    return CostReport(
        provider="openai",
        start=start,
        end=end,
        lines=parse_openai_cost_lines(payload),
    )


def fetch_anthropic_costs(
    admin_key: str,
    start: datetime,
    end: datetime,
    *,
    group_by: tuple[str, ...] = (),
    opener: Callable[..., Any] = urlopen,
) -> CostReport:
    params: dict[str, Any] = {
        "starting_at": _iso_utc(start),
        "ending_at": _iso_utc(end),
    }
    if group_by:
        params["group_by[]"] = list(group_by)
    payload = _get_json(
        ANTHROPIC_COSTS_URL,
        params,
        {
            "anthropic-version": ANTHROPIC_VERSION,
            "x-api-key": admin_key,
            "User-Agent": "MEMEX/0.1",
        },
        opener,
    )
    return CostReport(
        provider="anthropic",
        start=start,
        end=end,
        lines=parse_anthropic_cost_lines(payload),
    )


def parse_openai_cost_lines(payload: Mapping[str, Any]) -> tuple[CostLine, ...]:
    lines: list[CostLine] = []
    for bucket in payload.get("data", ()):
        start = str(bucket.get("start_time", ""))
        end = str(bucket.get("end_time", ""))
        for result in bucket.get("results", ()):
            amount = result.get("amount") or {}
            lines.append(
                CostLine(
                    provider="openai",
                    start=start,
                    end=end,
                    amount_usd=_decimal(amount.get("value", "0")),
                    label=_openai_label(result),
                )
            )
    return tuple(lines)


def parse_anthropic_cost_lines(payload: Mapping[str, Any]) -> tuple[CostLine, ...]:
    rows = payload.get("data", payload.get("results", ()))
    lines: list[CostLine] = []
    for row in rows:
        amount_cents = _first_decimal(row, ("amount", "cost", "price", "list_price"))
        if amount_cents is None:
            amount_cents = _first_decimal(
                row,
                ("amount_cents", "cost_cents", "price_cents", "list_price_cents"),
            )
        if amount_cents is None:
            continue
        lines.append(
            CostLine(
                provider="anthropic",
                start=str(row.get("starting_at", row.get("start_time", ""))),
                end=str(row.get("ending_at", row.get("end_time", ""))),
                amount_usd=amount_cents / Decimal("100"),
                label=_anthropic_label(row),
            )
        )
    return tuple(lines)


def format_cost_report(report: CostReport) -> str:
    lines = [f"{report.provider}: ${_money(report.total_usd)} USD"]
    for line in report.lines:
        label = f" {line.label}" if line.label else ""
        lines.append(f"  ${_money(line.amount_usd)} USD{label}")
    return "\n".join(lines)


def _get_json(
    url: str,
    params: Mapping[str, Any],
    headers: Mapping[str, str],
    opener: Callable[..., Any],
) -> dict[str, Any]:
    query = urlencode(
        [(key, value) for key, value in _query_items(params) if value not in ("", None)]
    )
    request = Request(
        f"{url}?{query}",
        headers={"Accept": "application/json", **headers},
        method="GET",
    )
    try:
        with opener(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        message = body.strip() or error.reason
        raise RuntimeError(f"{url} returned HTTP {error.code}: {message}") from error


def _query_items(params: Mapping[str, Any]):
    for key, value in params.items():
        if isinstance(value, (list, tuple)):
            for item in value:
                yield key, item
        else:
            yield key, value


def _unix_seconds(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp())


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _first_decimal(row: Mapping[str, Any], names: tuple[str, ...]) -> Decimal | None:
    for name in names:
        if name not in row:
            continue
        value = row[name]
        if isinstance(value, Mapping):
            value = value.get("value")
        if value is not None:
            return _decimal(value)
    return None


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001")))


def _openai_label(result: Mapping[str, Any]) -> str:
    parts = []
    for key in ("line_item", "project_id", "api_key_id"):
        value = result.get(key)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _anthropic_label(row: Mapping[str, Any]) -> str:
    parts = []
    for key in ("description", "model", "workspace_id", "api_key_id"):
        value = row.get(key)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts)
