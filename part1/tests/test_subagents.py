import unittest

from support_agent.classifier import ClassificationResult
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


class SubagentRoutingTests(unittest.TestCase):
    def test_refund_routes_to_refund_subagent_with_guardrail_skill(self):
        route = route_to_subagent(classification_for("Refund"))

        self.assertEqual(route.selected_subagent, "RefundSubagent")
        self.assertIn("RefundGuardrailSkill", route.allowed_skills)

    def test_billing_routes_to_billing_subagent(self):
        route = route_to_subagent(classification_for("Billing"))

        self.assertEqual(route.selected_subagent, "BillingSubagent")
        self.assertEqual(route.category, "Billing")

    def test_unknown_subagent_falls_back_to_other_subagent(self):
        classification = ClassificationResult(
            primary_category="Mystery",
            categories=["Mystery"],
            confidence=0.2,
            scores={},
            reason="unknown",
            recommended_subagent="MysterySubagent",
        )

        route = route_to_subagent(classification)

        self.assertEqual(route.selected_subagent, "OtherSubagent")
        self.assertEqual(route.category, "Other")


if __name__ == "__main__":
    unittest.main()

