"""Tests for dashboard route helpers."""

import unittest

from app.wiki.dashboard_routes import _safe_provider_balances
from app.wiki.provider_balances import ProviderBalance


class SafeProviderBalancesTests(unittest.TestCase):
    def test_none_balance_provider_returns_empty_tuple(self):
        self.assertEqual((), _safe_provider_balances(None))

    def test_balance_provider_values_are_returned_as_tuple(self):
        balances = (
            ProviderBalance("openai", "external", "Balance"),
            ProviderBalance("anthropic", "external", "Balance"),
        )

        def provider():
            return balances

        result = _safe_provider_balances(provider)
        self.assertEqual(tuple(balances), result)

    def test_balance_provider_raising_returns_error_balance(self):
        def provider():
            raise RuntimeError("upstream timeout")

        result = _safe_provider_balances(provider)

        self.assertEqual(1, len(result))
        balance = result[0]
        self.assertEqual("provider_balances", balance.provider)
        self.assertEqual("error", balance.status)
        self.assertEqual("error", balance.summary)
        self.assertEqual("upstream timeout", balance.detail)


if __name__ == "__main__":
    unittest.main()