from datetime import date
import json
import unittest

from document_agent.tools import (
    ToolInputError,
    calculate_date,
    calculate_expression,
    calculator,
    date_tool,
)


class CalculatorTests(unittest.TestCase):
    def test_multiplies_policy_rate(self):
        self.assertEqual(calculate_expression("240 * 3"), "720")

    def test_handles_parentheses_and_decimals(self):
        self.assertEqual(calculate_expression("(80 + 12.50) * 2"), "185")

    def test_rejects_code_and_names(self):
        with self.assertRaisesRegex(ToolInputError, "accepts only"):
            calculate_expression("__import__('os').system('dir')")

    def test_rejects_power_operator(self):
        with self.assertRaisesRegex(ToolInputError, "not allowed"):
            calculate_expression("2 ** 8")

    def test_rejects_division_by_zero(self):
        with self.assertRaisesRegex(ToolInputError, "divide by zero"):
            calculate_expression("10 / 0")

    def test_tool_returns_structured_error(self):
        result = json.loads(calculator.invoke({"expression": "1 / 0"}))

        self.assertEqual(result["status"], "error")
        self.assertIn("divide by zero", result["error"])


class DateToolTests(unittest.TestCase):
    def test_adds_claim_deadline_days(self):
        result = calculate_date(
            "add_days",
            start_date="2026-08-10",
            days=10,
        )

        self.assertEqual(result, "2026-08-20")

    def test_counts_days_between_dates(self):
        result = calculate_date(
            "days_between",
            start_date="2026-08-10",
            end_date="2026-08-20",
        )

        self.assertEqual(result, "10")

    def test_today_can_use_injected_date(self):
        result = calculate_date(
            "today",
            current_date=date(2026, 7, 25),
        )

        self.assertEqual(result, "2026-07-25")

    def test_missing_start_date_is_rejected(self):
        with self.assertRaisesRegex(ToolInputError, "start_date is required"):
            calculate_date("add_days", days=10)

    def test_invalid_iso_date_is_rejected(self):
        with self.assertRaisesRegex(ToolInputError, "YYYY-MM-DD"):
            calculate_date(
                "add_days",
                start_date="10/08/2026",
                days=10,
            )

    def test_date_tool_returns_structured_result(self):
        result = json.loads(
            date_tool.invoke(
                {
                    "operation": "add_days",
                    "start_date": "2026-08-10",
                    "days": 10,
                }
            )
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"], "2026-08-20")


if __name__ == "__main__":
    unittest.main()
