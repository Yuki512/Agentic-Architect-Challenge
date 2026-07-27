import unittest

from support_agent.critical_detector import check_critical_issue


class CriticalDetectorTests(unittest.TestCase):
    def test_data_loss_routes_to_human(self):
        result = check_critical_issue(
            {
                "subject": "Possible data loss",
                "body": "My saved order details disappeared after the app crash.",
                "contact_count_last_7_days": 1,
            }
        )

        self.assertTrue(result.is_critical)
        self.assertIn("data_loss", result.matched_triggers)
        self.assertEqual(result.recommended_action, "handoff_to_human_agent")

    def test_service_outage_routes_to_human(self):
        result = check_critical_issue(
            {
                "subject": "Service outage",
                "body": "Checkout is unavailable for everyone in my office.",
                "contact_count_last_7_days": 1,
            }
        )

        self.assertTrue(result.is_critical)
        self.assertIn("service_outage", result.matched_triggers)

    def test_security_breach_routes_to_human(self):
        result = check_critical_issue(
            {
                "subject": "Security breach",
                "body": "I think someone hacked my account.",
                "contact_count_last_7_days": 1,
            }
        )

        self.assertTrue(result.is_critical)
        self.assertIn("security_breach", result.matched_triggers)

    def test_repeat_contact_routes_to_human(self):
        result = check_critical_issue(
            {
                "subject": "Still waiting",
                "body": "I need another update about my package.",
                "contact_count_last_7_days": 4,
            }
        )

        self.assertTrue(result.is_critical)
        self.assertIn("repeat_contact_over_3_in_7_days", result.matched_triggers)

    def test_normal_email_continues_to_classification(self):
        result = check_critical_issue(
            {
                "subject": "Refund question",
                "body": "Can I return an unused item after 10 days?",
                "contact_count_last_7_days": 1,
            }
        )

        self.assertFalse(result.is_critical)
        self.assertEqual(result.matched_triggers, [])
        self.assertEqual(result.recommended_action, "continue_to_classification")


if __name__ == "__main__":
    unittest.main()

