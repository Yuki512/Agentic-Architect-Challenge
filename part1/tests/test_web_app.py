import unittest

from support_agent.classifier import classify_email
from support_agent.drafting import draft_grounded_response
from support_agent.semantic_critical import skip_semantic_critical_check
from support_agent.web_app import load_example_emails, process_email_payload


class WebAppTests(unittest.TestCase):
    def test_load_example_emails(self):
        examples = load_example_emails()

        self.assertGreaterEqual(len(examples), 6)
        self.assertIn("subject", examples[0])

    def test_process_payload_returns_serialized_result(self):
        result = process_email_payload(
            {
                "customer_name": "Alicia",
                "subject": "Can I return my order after 10 days?",
                "body": "The item is unused and still in original packaging. Can I get a refund?",
                "contact_count_last_7_days": 1,
            },
            classifier=classify_email,
            drafter=draft_grounded_response,
            semantic_checker=skip_semantic_critical_check,
        )

        self.assertEqual(result["status"], "drafted")
        self.assertEqual(result["classification"]["primary_category"], "Refund")
        self.assertEqual(
            result["semantic_critical_check"]["status"],
            "skipped",
        )

    def test_process_payload_requires_subject_or_body(self):
        with self.assertRaises(ValueError):
            process_email_payload({"subject": "", "body": ""})

    def test_process_payload_uses_single_human_review_status(self):
        result = process_email_payload(
            {
                "customer_name": "Ethan",
                "subject": "Refund after 90 days?",
                "body": "Can I get a refund after 90 days if I used the product only once?",
                "contact_count_last_7_days": 1,
            },
            classifier=classify_email,
            drafter=draft_grounded_response,
            semantic_checker=skip_semantic_critical_check,
        )

        self.assertEqual(result["status"], "human_review")


if __name__ == "__main__":
    unittest.main()
