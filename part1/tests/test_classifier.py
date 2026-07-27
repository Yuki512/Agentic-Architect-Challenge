import unittest

from support_agent.classifier import classify_email


class ClassifierTests(unittest.TestCase):
    def test_refund_email_routes_to_refund_subagent(self):
        result = classify_email(
            {
                "subject": "Can I return my order?",
                "body": "The item is unused. Can I return it for a refund?",
            }
        )

        self.assertEqual(result.primary_category, "Refund")
        self.assertEqual(result.recommended_subagent, "RefundSubagent")

    def test_billing_email_routes_to_billing_subagent(self):
        result = classify_email(
            {
                "subject": "Charged twice",
                "body": "I see a duplicate payment for the same order.",
            }
        )

        self.assertEqual(result.primary_category, "Billing")
        self.assertEqual(result.recommended_subagent, "BillingSubagent")

    def test_login_email_routes_to_account_subagent(self):
        result = classify_email(
            {
                "subject": "Login issue",
                "body": "I cannot log in with my password.",
            }
        )

        self.assertEqual(result.primary_category, "Account")
        self.assertIn("Account", result.categories)

    def test_shipping_email_routes_to_shipping_subagent(self):
        result = classify_email(
            {
                "subject": "Missing package",
                "body": "The tracking page says delivered but my package is missing.",
            }
        )

        self.assertEqual(result.primary_category, "Shipping")

    def test_unknown_email_routes_to_other_subagent(self):
        result = classify_email(
            {
                "subject": "Partnership question",
                "body": "Who should I contact about a wholesale partnership?",
            }
        )

        self.assertEqual(result.primary_category, "Other")
        self.assertEqual(result.confidence, 0.2)


if __name__ == "__main__":
    unittest.main()

