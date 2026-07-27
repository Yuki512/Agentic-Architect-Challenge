import unittest

from support_agent.critical_detector import check_critical_issue
from support_agent.tools import audit_logging_tool, human_handoff_tool, pdf_search_tool


class ToolTests(unittest.TestCase):
    def test_pdf_search_finds_refund_window(self):
        result = pdf_search_tool("Can I return an unused item for a refund?", category="Refund", limit=2)

        self.assertTrue(result.found)
        joined_text = " ".join(passage.text for passage in result.passages)
        self.assertIn("30 calendar days", joined_text)

    def test_pdf_search_finds_billing_duplicate_charge_info(self):
        result = pdf_search_tool("I was charged twice for one order", category="Billing", limit=2)

        self.assertTrue(result.found)
        joined_text = " ".join(passage.text for passage in result.passages).casefold()
        self.assertIn("duplicate charge", joined_text)

    def test_human_handoff_tool_creates_ticket_payload(self):
        email_case = {
            "case_id": "CASE-2001",
            "customer_id": "CUST-200",
            "customer_name": "Test Customer",
            "customer_email": "test@example.com",
            "subject": "Possible data loss",
            "body": "My order history disappeared and I think this is data loss.",
            "contact_count_last_7_days": 1,
            "metadata": {"app_version": "4.8.1"},
        }
        critical_result = check_critical_issue(email_case)

        ticket = human_handoff_tool(email_case, critical_result)

        self.assertEqual(ticket.ticket_id, "HANDOFF-CASE-2001")
        self.assertEqual(ticket.priority, "high")
        self.assertIn("data_loss", ticket.matched_triggers)
        self.assertEqual(ticket.customer_context["customer_id"], "CUST-200")

    def test_audit_logging_tool_returns_structured_entry(self):
        entry = audit_logging_tool(
            case_id="CASE-1",
            event_type="pdf_search",
            status="success",
            details={"passages": 2},
        )

        self.assertEqual(entry.case_id, "CASE-1")
        self.assertEqual(entry.details["passages"], 2)


if __name__ == "__main__":
    unittest.main()

