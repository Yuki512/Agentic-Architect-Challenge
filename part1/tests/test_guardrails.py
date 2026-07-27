import unittest

from support_agent.classifier import classify_email
from support_agent.drafting import draft_grounded_response
from support_agent.guardrails import apply_refund_guardrail
from support_agent.subagents import route_to_subagent
from support_agent.tools import pdf_search_tool


class RefundGuardrailTests(unittest.TestCase):
    def test_supported_refund_window_passes(self):
        email_case = {
            "customer_name": "Alicia",
            "subject": "Can I return my order after 10 days?",
            "body": "The item is unused and still in original packaging. Can I get a refund?",
        }
        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        search = pdf_search_tool(
            query=f"{email_case['subject']} {email_case['body']}",
            category=classification.primary_category,
            limit=2,
        )
        draft = draft_grounded_response(email_case, route, search)

        guardrail = apply_refund_guardrail(email_case, classification.primary_category, draft)

        self.assertTrue(guardrail.passed)
        self.assertEqual(guardrail.final_draft.status, "drafted")

    def test_unsupported_90_day_refund_question_is_blocked(self):
        email_case = {
            "customer_name": "Ethan",
            "subject": "Refund after 90 days?",
            "body": "Can I get a refund after 90 days if I used the product only once?",
        }
        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        search = pdf_search_tool(
            query=f"{email_case['subject']} {email_case['body']}",
            category=classification.primary_category,
            limit=2,
        )
        draft = draft_grounded_response(email_case, route, search)

        guardrail = apply_refund_guardrail(email_case, classification.primary_category, draft)

        self.assertFalse(guardrail.passed)
        self.assertEqual(guardrail.final_draft.status, "needs_human_review")
        self.assertIn("instead of guessing", guardrail.final_draft.reply)

    def test_non_refund_case_does_not_apply_refund_guardrail(self):
        email_case = {
            "customer_name": "Marcus",
            "subject": "Charged twice",
            "body": "I was charged twice for one order.",
        }
        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        search = pdf_search_tool(
            query=f"{email_case['subject']} {email_case['body']}",
            category=classification.primary_category,
            limit=2,
        )
        draft = draft_grounded_response(email_case, route, search)

        guardrail = apply_refund_guardrail(email_case, classification.primary_category, draft)

        self.assertTrue(guardrail.passed)
        self.assertEqual(guardrail.status, "not_applicable")


if __name__ == "__main__":
    unittest.main()

