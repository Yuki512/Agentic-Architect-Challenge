import unittest

from support_agent.classifier import classify_email
from support_agent.drafting import draft_grounded_response
from support_agent.subagents import route_to_subagent
from support_agent.tools import PDFSearchResult, pdf_search_tool


class DraftingTests(unittest.TestCase):
    def test_refund_draft_uses_pdf_evidence(self):
        email_case = {
            "customer_name": "Alicia",
            "subject": "Can I return my order?",
            "body": "I received my item 10 days ago and it is unused. Can I get a refund?",
        }
        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        search = pdf_search_tool(
            query=f"{email_case['subject']} {email_case['body']}",
            category=classification.primary_category,
            limit=2,
        )

        draft = draft_grounded_response(email_case, route, search)

        self.assertEqual(draft.status, "drafted")
        self.assertIn("30 calendar days", draft.reply)
        self.assertGreater(len(draft.evidence), 0)

    def test_missing_evidence_routes_to_human_review(self):
        email_case = {
            "customer_name": "Taylor",
            "subject": "Unknown question",
            "body": "Can you answer something not in the FAQ?",
        }
        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        empty_search = PDFSearchResult(
            query="unknown question",
            source_path="docs/nimbus_support_knowledge_base.pdf",
            found=False,
            passages=[],
        )

        draft = draft_grounded_response(email_case, route, empty_search)

        self.assertEqual(draft.status, "needs_human_review")
        self.assertIn("could not find enough information", draft.reply)
        self.assertEqual(draft.evidence, [])

    def test_billing_draft_includes_duplicate_charge_guidance(self):
        email_case = {
            "customer_name": "Marcus",
            "subject": "Charged twice",
            "body": "I was charged twice for the same order.",
        }
        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        search = pdf_search_tool(
            query=f"{email_case['subject']} {email_case['body']}",
            category=classification.primary_category,
            limit=2,
        )

        draft = draft_grounded_response(email_case, route, search)

        self.assertEqual(draft.status, "drafted")
        self.assertIn("duplicate charge", draft.reply.casefold())


if __name__ == "__main__":
    unittest.main()

