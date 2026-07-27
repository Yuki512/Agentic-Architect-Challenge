import unittest

from support_agent.drafting import draft_grounded_response
from support_agent.orchestrator import (
    build_email_workflow,
    process_email,
    process_email_as_dict,
)
from support_agent.semantic_critical import (
    SemanticCriticalResult,
    skip_semantic_critical_check,
)


class OrchestratorTests(unittest.TestCase):
    def test_langgraph_contains_expected_workflow_nodes(self):
        graph = build_email_workflow(
            drafter=draft_grounded_response,
            semantic_checker=skip_semantic_critical_check,
        )

        self.assertTrue(
            {
                "router_agent",
                "critical_keyword_check",
                "critical_semantic_check",
                "human_handoff",
                "specialist_routing",
                "pdf_search",
                "draft_response",
                "refund_guardrail",
            }.issubset(graph.get_graph().nodes)
        )

    def test_normal_refund_email_returns_draft(self):
        result = process_email(
            {
                "case_id": "CASE-3001",
                "customer_id": "CUST-3001",
                "customer_name": "Alicia",
                "customer_email": "alicia@example.com",
                "subject": "Can I return my order after 10 days?",
                "body": "The item is unused and still in original packaging. Can I get a refund?",
                "contact_count_last_7_days": 1,
                "metadata": {},
            },
            drafter=draft_grounded_response,
            semantic_checker=skip_semantic_critical_check,
        )

        self.assertEqual(result.status, "drafted")
        self.assertFalse(result.critical_check.is_critical)
        self.assertEqual(result.classification.primary_category, "Refund")
        self.assertEqual(result.route.selected_subagent, "RefundSubagent")
        self.assertEqual(result.guardrail.status, "passed")
        self.assertIn("30 calendar days", result.final_draft.reply)

    def test_critical_email_returns_handoff_without_draft(self):
        result = process_email(
            {
                "case_id": "CASE-3002",
                "customer_id": "CUST-3002",
                "customer_name": "Daniel",
                "customer_email": "daniel@example.com",
                "subject": "Possible data loss after app crash",
                "body": "The app crashed and my saved order details disappeared. I am worried this is data loss.",
                "contact_count_last_7_days": 1,
                "metadata": {},
            },
            drafter=draft_grounded_response,
            semantic_checker=skip_semantic_critical_check,
        )

        self.assertEqual(result.status, "human_review")
        self.assertTrue(result.critical_check.is_critical)
        self.assertEqual(result.classification.primary_category, "Technical")
        self.assertIsNone(result.final_draft)
        self.assertEqual(result.handoff_ticket.ticket_id, "HANDOFF-CASE-3002")

    def test_unknown_refund_window_is_blocked_by_guardrail(self):
        result = process_email(
            {
                "case_id": "CASE-3003",
                "customer_id": "CUST-3003",
                "customer_name": "Ethan",
                "customer_email": "ethan@example.com",
                "subject": "Refund after 90 days?",
                "body": "Can I get a refund after 90 days if I used the product only once?",
                "contact_count_last_7_days": 1,
                "metadata": {},
            },
            drafter=draft_grounded_response,
            semantic_checker=skip_semantic_critical_check,
        )

        self.assertEqual(result.status, "human_review")
        self.assertEqual(result.classification.primary_category, "Refund")
        self.assertEqual(result.guardrail.status, "blocked")
        self.assertIn("instead of guessing", result.final_draft.reply)
        self.assertIn("HumanReviewSkill", result.skill_plan.execution_order)

    def test_process_email_as_dict_serializes_pipeline_result(self):
        result = process_email_as_dict(
            {
                "case_id": "CASE-3004",
                "customer_id": "CUST-3004",
                "customer_name": "Marcus",
                "customer_email": "marcus@example.com",
                "subject": "Charged twice",
                "body": "I was charged twice for one order.",
                "contact_count_last_7_days": 1,
                "metadata": {},
            },
            drafter=draft_grounded_response,
            semantic_checker=skip_semantic_critical_check,
        )

        self.assertEqual(result["status"], "drafted")
        self.assertEqual(result["classification"]["primary_category"], "Billing")
        self.assertEqual(result["route"]["selected_subagent"], "BillingSubagent")

    def test_semantic_paraphrase_routes_to_human_before_drafting(self):
        def semantic_checker(_email_case):
            return SemanticCriticalResult(
                status="critical",
                requires_human_review=True,
                matched_condition="data_loss",
                confidence=0.96,
                evidence="All saved customer records vanished overnight",
                reason="The email describes customer records disappearing.",
                provider="deepseek",
                model="deepseek-v4-flash",
            )

        def unexpected_drafter(*_args):
            raise AssertionError("Critical semantic case must not be drafted.")

        result = process_email(
            {
                "case_id": "CASE-3005",
                "customer_id": "CUST-3005",
                "customer_name": "Nadia",
                "customer_email": "nadia@example.com",
                "subject": "Customer records disappeared",
                "body": "All saved customer records vanished overnight.",
                "contact_count_last_7_days": 1,
                "metadata": {},
            },
            drafter=unexpected_drafter,
            semantic_checker=semantic_checker,
        )

        self.assertEqual(result.status, "human_review")
        self.assertTrue(result.critical_check.is_critical)
        self.assertIn(
            "semantic_data_loss",
            result.critical_check.matched_triggers,
        )
        self.assertEqual(result.semantic_critical_check.status, "critical")
        self.assertEqual(result.classification.primary_category, "Other")
        self.assertIsNone(result.final_draft)

    def test_uncertain_semantic_result_routes_to_human(self):
        def semantic_checker(_email_case):
            return SemanticCriticalResult(
                status="uncertain",
                requires_human_review=True,
                matched_condition="none",
                confidence=0.51,
                evidence="",
                reason="The wording is ambiguous.",
                provider="deepseek",
                model="deepseek-v4-flash",
            )

        result = process_email(
            {
                "case_id": "CASE-3006",
                "subject": "Urgent account concern",
                "body": "Something unusual happened to several records.",
                "contact_count_last_7_days": 1,
            },
            drafter=draft_grounded_response,
            semantic_checker=semantic_checker,
        )

        self.assertEqual(result.status, "human_review")
        self.assertIn(
            "semantic_uncertain",
            result.critical_check.matched_triggers,
        )

    def test_semantic_error_falls_back_to_deterministic_route(self):
        def semantic_checker(_email_case):
            raise RuntimeError("simulated provider failure")

        result = process_email(
            {
                "case_id": "CASE-3007",
                "customer_name": "Alicia",
                "subject": "Can I return my order after 10 days?",
                "body": "The item is unused and still in original packaging.",
                "contact_count_last_7_days": 1,
            },
            drafter=draft_grounded_response,
            semantic_checker=semantic_checker,
        )

        self.assertEqual(result.status, "drafted")
        self.assertFalse(result.critical_check.is_critical)
        self.assertEqual(result.semantic_critical_check.status, "error")


if __name__ == "__main__":
    unittest.main()
