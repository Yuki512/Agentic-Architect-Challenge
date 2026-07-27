from dataclasses import dataclass

from support_agent.classifier import ClassificationResult


@dataclass(frozen=True)
class SubagentProfile:
    name: str
    category: str
    responsibility: str
    allowed_skills: list[str]


@dataclass(frozen=True)
class SubagentRouteResult:
    selected_subagent: str
    category: str
    responsibility: str
    allowed_skills: list[str]
    reason: str


SUBAGENT_REGISTRY = {
    "BillingSubagent": SubagentProfile(
        name="BillingSubagent",
        category="Billing",
        responsibility="Handle invoices, duplicate charges, failed payments, receipts, and payment verification guidance.",
        allowed_skills=["KnowledgeRetrievalSkill", "GroundedDraftSkill"],
    ),
    "RefundSubagent": SubagentProfile(
        name="RefundSubagent",
        category="Refund",
        responsibility="Handle refund windows, return eligibility, cancellations, refund timing, and non-refundable items.",
        allowed_skills=["KnowledgeRetrievalSkill", "GroundedDraftSkill", "RefundGuardrailSkill"],
    ),
    "TechnicalSubagent": SubagentProfile(
        name="TechnicalSubagent",
        category="Technical",
        responsibility="Handle app crashes, bugs, checkout errors, and order-tracking technical issues.",
        allowed_skills=["KnowledgeRetrievalSkill", "GroundedDraftSkill"],
    ),
    "AccountSubagent": SubagentProfile(
        name="AccountSubagent",
        category="Account",
        responsibility="Handle login, password, profile, email address, and account privacy questions.",
        allowed_skills=["KnowledgeRetrievalSkill", "GroundedDraftSkill"],
    ),
    "ShippingSubagent": SubagentProfile(
        name="ShippingSubagent",
        category="Shipping",
        responsibility="Handle delivery timelines, missing packages, damaged shipments, and carrier tracking questions.",
        allowed_skills=["KnowledgeRetrievalSkill", "GroundedDraftSkill"],
    ),
    "FeedbackSubagent": SubagentProfile(
        name="FeedbackSubagent",
        category="Feedback",
        responsibility="Handle customer suggestions, feature requests, complaints, praise, and product feedback.",
        allowed_skills=["GroundedDraftSkill"],
    ),
    "OtherSubagent": SubagentProfile(
        name="OtherSubagent",
        category="Other",
        responsibility="Handle uncategorized questions and decide whether the available knowledge base is sufficient.",
        allowed_skills=["KnowledgeRetrievalSkill", "GroundedDraftSkill"],
    ),
}


def route_to_subagent(classification: ClassificationResult) -> SubagentRouteResult:
    """Select the specialized subagent for a classified support email."""
    profile = SUBAGENT_REGISTRY.get(
        classification.recommended_subagent,
        SUBAGENT_REGISTRY["OtherSubagent"],
    )

    return SubagentRouteResult(
        selected_subagent=profile.name,
        category=profile.category,
        responsibility=profile.responsibility,
        allowed_skills=profile.allowed_skills,
        reason=(
            f"Router selected {profile.name} because the primary category is "
            f"{classification.primary_category}."
        ),
    )

