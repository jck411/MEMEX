"""Provider account balance and credit helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"
OPENROUTER_MGMT_ENV_KEY = "OPENROUTER_MGMT_KEY"
OPENAI_BILLING_URL = "https://platform.openai.com/settings/organization/billing/overview"
ANTHROPIC_DASHBOARD_URL = "https://platform.claude.com/dashboard"
GOOGLE_AI_STUDIO_BILLING_URL = (
    "https://aistudio.google.com/billing"
    "?project=gen-lang-client-0763207333&billing=015B89-F5B642-205AE1"
)
OPENROUTER_LOGS_URL = "https://openrouter.ai/logs"


@dataclass(frozen=True)
class ProviderBalance:
    provider: str
    status: str
    summary: str
    amount: Decimal | None = None
    unit: str = ""
    detail: str = ""
    url: str = ""


def provider_balance_snapshot(
    env: Mapping[str, str],
    *,
    opener: Callable[..., Any] = urlopen,
) -> tuple[ProviderBalance, ...]:
    balances = [
        openai_balance_status(),
        anthropic_balance_status(),
        google_balance_status(),
    ]
    openrouter_key = env.get(OPENROUTER_MGMT_ENV_KEY, "")
    if not openrouter_key:
        balances.append(
            ProviderBalance(
                provider="openrouter",
                status="missing",
                summary="Balance",
                detail=f"missing {OPENROUTER_MGMT_ENV_KEY}",
                url=OPENROUTER_LOGS_URL,
            )
        )
        return tuple(balances)
    try:
        balances.append(fetch_openrouter_balance(openrouter_key, opener=opener))
    except Exception as error:
        balances.append(
            ProviderBalance(
                provider="openrouter",
                status="error",
                summary="error",
                detail=str(error),
                url=OPENROUTER_LOGS_URL,
            )
        )
    return tuple(balances)


def provider_balance_readiness(env: Mapping[str, str]) -> tuple[ProviderBalance, ...]:
    openrouter_status = (
        ProviderBalance(
            provider="openrouter",
            status="configured",
            summary="configured",
            detail=f"{OPENROUTER_MGMT_ENV_KEY} configured",
            url=OPENROUTER_LOGS_URL,
        )
        if env.get(OPENROUTER_MGMT_ENV_KEY)
        else ProviderBalance(
            provider="openrouter",
            status="missing",
            summary="missing key",
            detail=f"missing {OPENROUTER_MGMT_ENV_KEY}",
            url=OPENROUTER_LOGS_URL,
        )
    )
    return (
        openai_balance_status(),
        anthropic_balance_status(),
        google_balance_status(),
        openrouter_status,
    )


def openai_balance_status() -> ProviderBalance:
    return ProviderBalance(
        provider="openai",
        status="external",
        summary="Balance",
        detail="Open OpenAI billing overview.",
        url=OPENAI_BILLING_URL,
    )


def anthropic_balance_status() -> ProviderBalance:
    return ProviderBalance(
        provider="anthropic",
        status="external",
        summary="Balance",
        detail="Open Anthropic dashboard.",
        url=ANTHROPIC_DASHBOARD_URL,
    )


def google_balance_status() -> ProviderBalance:
    return ProviderBalance(
        provider="google",
        status="external",
        summary="Balance",
        detail="Open Google AI Studio billing.",
        url=GOOGLE_AI_STUDIO_BILLING_URL,
    )


def fetch_openrouter_balance(
    management_key: str,
    *,
    opener: Callable[..., Any] = urlopen,
) -> ProviderBalance:
    payload = _get_json(
        OPENROUTER_CREDITS_URL,
        {"Authorization": f"Bearer {management_key}"},
        opener,
    )
    data = payload.get("data", {})
    if not isinstance(data, Mapping):
        raise ValueError("OpenRouter credits response missing data object")
    total = _decimal(data.get("total_credits"))
    used = _decimal(data.get("total_usage"))
    remaining = total - used
    return ProviderBalance(
        provider="openrouter",
        status="available",
        summary=f"${_money(remaining)}",
        amount=remaining,
        unit="usd",
        detail=(f"Balance: ${_money(remaining)}; total=${_money(total)}; used=${_money(used)}"),
        url=OPENROUTER_LOGS_URL,
    )


def provider_balance_value(balance: ProviderBalance) -> str:
    if balance.amount is not None:
        if balance.unit == "usd":
            return f"${_money(balance.amount)}"
        unit = f" {balance.unit}" if balance.unit else ""
        return f"{_money(balance.amount)}{unit}"
    return balance.summary or balance.status


def format_provider_balance(balance: ProviderBalance) -> str:
    return f"{provider_label(balance.provider)}: {provider_balance_value(balance)}"


def provider_label(provider: str) -> str:
    return {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "openrouter": "OpenRouter",
    }.get(provider, provider.replace("_", " ").title())


def _get_json(
    url: str,
    headers: Mapping[str, str],
    opener: Callable[..., Any],
) -> dict[str, Any]:
    request = Request(
        url,
        headers={"Accept": "application/json", **headers},
        method="GET",
    )
    try:
        with opener(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        message = body.strip() or error.reason
        raise RuntimeError(f"{url} returned HTTP {error.code}: {message}") from error
    except URLError as error:
        raise RuntimeError(f"{url} request failed: {error.reason}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{url} returned a non-object JSON response")
    return payload


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001")))
