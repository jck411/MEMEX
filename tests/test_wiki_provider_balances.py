import unittest
from decimal import Decimal

from app.wiki.provider_balances import (
    ANTHROPIC_DASHBOARD_URL,
    GOOGLE_AI_STUDIO_BILLING_URL,
    OPENAI_BILLING_URL,
    OPENROUTER_CREDITS_URL,
    OPENROUTER_LOGS_URL,
    OPENROUTER_MGMT_ENV_KEY,
    fetch_openrouter_balance,
    format_provider_balance,
    provider_balance_readiness,
    provider_balance_snapshot,
)
from tests.helpers import JsonResponse


class WikiProviderBalanceTests(unittest.TestCase):
    def test_fetch_openrouter_balance_subtracts_usage_from_credits(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["timeout"] = timeout
            return JsonResponse({"data": {"total_credits": "100.50", "total_usage": "25.25"}})

        balance = fetch_openrouter_balance("secret-openrouter", opener=opener)

        self.assertEqual(OPENROUTER_CREDITS_URL, seen["url"])
        self.assertEqual("Bearer secret-openrouter", seen["auth"])
        self.assertEqual(30, seen["timeout"])
        self.assertEqual("openrouter", balance.provider)
        self.assertEqual(Decimal("75.25"), balance.amount)
        self.assertEqual("usd", balance.unit)
        self.assertEqual(OPENROUTER_LOGS_URL, balance.url)
        self.assertEqual("OpenRouter: $75.2500", format_provider_balance(balance))

    def test_provider_balance_snapshot_is_honest_about_unsupported_balances(self):
        def opener(*_args, **_kwargs):
            raise AssertionError("OpenRouter should not be called without a management key")

        balances = provider_balance_snapshot({}, opener=opener)
        formatted = [format_provider_balance(balance) for balance in balances]

        self.assertEqual(
            [
                "OpenAI: Balance",
                "Anthropic: Balance",
                "Google: Balance",
                "OpenRouter: Balance",
            ],
            formatted,
        )
        self.assertEqual(OPENAI_BILLING_URL, balances[0].url)
        self.assertEqual(ANTHROPIC_DASHBOARD_URL, balances[1].url)
        self.assertEqual(GOOGLE_AI_STUDIO_BILLING_URL, balances[2].url)
        self.assertEqual(OPENROUTER_LOGS_URL, balances[3].url)

    def test_provider_balance_readiness_does_not_print_secret_values(self):
        balances = provider_balance_readiness({OPENROUTER_MGMT_ENV_KEY: "secret-openrouter"})
        formatted = "\n".join(format_provider_balance(balance) for balance in balances)

        self.assertIn("OpenRouter: configured", formatted)
        self.assertNotIn("secret-openrouter", formatted)


if __name__ == "__main__":
    unittest.main()
