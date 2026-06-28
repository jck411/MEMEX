import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.wiki.usage_costs import (
    CostReport,
    format_cost_report,
    parse_anthropic_cost_lines,
    parse_openai_cost_lines,
    utc_cost_range,
)


class WikiUsageCostTests(unittest.TestCase):
    def test_openai_cost_parser_accepts_numeric_and_string_amounts(self):
        lines = parse_openai_cost_lines(
            {
                "data": [
                    {
                        "start_time": 10,
                        "end_time": 20,
                        "results": [
                            {
                                "amount": {"value": "1.25", "currency": "usd"},
                                "line_item": "Text tokens",
                            },
                            {
                                "amount": {"value": 0.5, "currency": "usd"},
                                "line_item": "Images",
                            },
                        ],
                    }
                ]
            }
        )

        self.assertEqual(Decimal("1.75"), sum(line.amount_usd for line in lines))
        self.assertEqual("line_item=Text tokens", lines[0].label)

    def test_anthropic_cost_parser_converts_cents_to_usd(self):
        lines = parse_anthropic_cost_lines(
            {
                "data": [
                    {
                        "starting_at": "2026-06-01T00:00:00Z",
                        "ending_at": "2026-06-02T00:00:00Z",
                        "amount": "123.45",
                        "description": "Claude Sonnet 4.6 input",
                    },
                    {"cost_cents": "5"},
                ]
            }
        )

        self.assertEqual(Decimal("1.2845"), sum(line.amount_usd for line in lines))
        self.assertEqual("description=Claude Sonnet 4.6 input", lines[0].label)

    def test_utc_cost_range_uses_utc_and_positive_days(self):
        start, end = utc_cost_range(
            7,
            datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
        )

        self.assertEqual(datetime(2026, 6, 15, 12, 0, tzinfo=UTC), start)
        self.assertEqual(datetime(2026, 6, 22, 12, 0, tzinfo=UTC), end)
        with self.assertRaises(ValueError):
            utc_cost_range(0)

    def test_format_cost_report_prints_total_and_line_items(self):
        report = CostReport(
            provider="openai",
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 2, tzinfo=UTC),
            lines=parse_openai_cost_lines(
                {
                    "data": [
                        {
                            "start_time": 10,
                            "end_time": 20,
                            "results": [
                                {
                                    "amount": {"value": "1.25"},
                                    "line_item": "Text tokens",
                                }
                            ],
                        }
                    ]
                }
            ),
        )

        self.assertIn("openai: $1.2500 USD", format_cost_report(report))

    def test_cost_script_check_reports_readiness_without_secret_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "OPENAI_ADMIN_KEY=secret-openai\nANTHROPIC_ADMIN_API_KEY=secret-anthropic\n",
                encoding="utf-8",
            )
            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_costs.py"

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--env-file",
                    str(env_path),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            self.assertIn("openai: configured", result.stdout)
            self.assertIn("anthropic: configured", result.stdout)
            self.assertNotIn("secret-openai", result.stdout)
            self.assertNotIn("secret-anthropic", result.stdout)

    def test_cost_script_balance_check_reports_readiness_without_secret_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "OPENROUTER_MGMT_KEY=secret-openrouter\n",
                encoding="utf-8",
            )
            script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_costs.py"

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--env-file",
                    str(env_path),
                    "--balances",
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            self.assertIn("OpenAI: Balance", result.stdout)
            self.assertIn("Anthropic: Balance", result.stdout)
            self.assertIn("Google: Balance", result.stdout)
            self.assertIn("OpenRouter: configured", result.stdout)
            self.assertNotIn("secret-openrouter", result.stdout)


if __name__ == "__main__":
    unittest.main()
