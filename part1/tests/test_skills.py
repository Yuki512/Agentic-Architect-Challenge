import unittest

from support_agent.classifier import ClassificationResult
from support_agent.critical_detector import CriticalCheckResult
from support_agent.skills import add_human_review_skill, plan_human_review_skill, plan_skills_for_subagent
from support_agent.subagents import route_to_subagent


def classification_for(category: str) -> ClassificationResult:
    return ClassificationResult(
        primary_category=category,
        categories=[category],
        confidence=1.0,
        scores={category: 1},
        reason="test classification",
        recommended_subagent=f"{category}Subagent",
    )


class SkillPlanningTests(unittest.TestCase):
    def test_refund_subagent_gets_refund_guardrail_skill(self):
        route = route_to_subagent(classification_for("Refund"))
        plan = plan_skills_for_subagent(route)

        self.assertEqual(plan.selected_subagent, "RefundSubagent")
        self.assertEqual(
            plan.execution_order,
            ["KnowledgeRetrievalSkill", "GroundedDraftSkill", "RefundGuardrailSkill"],
        )

    def test_billing_subagent_gets_retrieval_and_draft_skills(self):
        route = route_to_subagent(classification_for("Billing"))
        plan = plan_skills_for_subagent(route)

        self.assertEqual(plan.selected_subagent, "BillingSubagent")
        self.assertEqual(plan.execution_order, ["KnowledgeRetrievalSkill", "GroundedDraftSkill"])

    def test_handoff_plan_bypasses_normal_subagent_skills(self):
        critical_result = CriticalCheckResult(
            is_critical=True,
            matched_triggers=["data_loss"],
            contact_count_last_7_days=1,
            reason="Human review is required before any customer-facing draft is generated.",
            recommended_action="handoff_to_human_agent",
        )

        plan = plan_human_review_skill(critical_result)

        self.assertEqual(plan.selected_subagent, "HumanReview")
        self.assertEqual(plan.execution_order, ["HumanReviewSkill"])
        self.assertEqual(plan.skills[0].planned_tools, ["HumanHandoffTool", "AuditLoggingTool"])

    def test_non_critical_plan_can_append_human_review_skill(self):
        route = route_to_subagent(classification_for("Refund"))
        plan = plan_skills_for_subagent(route)

        updated_plan = add_human_review_skill(plan, "refund evidence was unsupported")

        self.assertEqual(
            updated_plan.execution_order,
            [
                "KnowledgeRetrievalSkill",
                "GroundedDraftSkill",
                "RefundGuardrailSkill",
                "HumanReviewSkill",
            ],
        )


if __name__ == "__main__":
    unittest.main()
