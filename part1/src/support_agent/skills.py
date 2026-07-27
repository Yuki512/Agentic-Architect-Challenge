from dataclasses import dataclass

from support_agent.critical_detector import CriticalCheckResult
from support_agent.subagents import SubagentRouteResult


@dataclass(frozen=True)
class SkillProfile:
    name: str
    purpose: str
    rules: list[str]
    planned_tools: list[str]


@dataclass(frozen=True)
class SkillPlan:
    selected_subagent: str
    skills: list[SkillProfile]
    execution_order: list[str]
    reason: str


SKILL_REGISTRY = {
    "KnowledgeRetrievalSkill": SkillProfile(
        name="KnowledgeRetrievalSkill",
        purpose="Find relevant support policy or FAQ evidence before drafting.",
        rules=[
            "Search the internal PDF knowledge base before writing policy-specific answers.",
            "Return short evidence passages with enough context for the drafting step.",
        ],
        planned_tools=["PDFSearchTool"],
    ),
    "GroundedDraftSkill": SkillProfile(
        name="GroundedDraftSkill",
        purpose="Create a concise customer-facing response grounded in retrieved evidence.",
        rules=[
            "Answer the customer's specific question first.",
            "Use a friendly support tone.",
            "Do not include facts that were not found in the available evidence.",
        ],
        planned_tools=["DraftBuilderTool"],
    ),
    "RefundGuardrailSkill": SkillProfile(
        name="RefundGuardrailSkill",
        purpose="Prevent fake or unsupported refund policy claims.",
        rules=[
            "Refund policy answers must be supported by PDF evidence.",
            "If refund evidence is missing, do not guess and recommend human review.",
        ],
        planned_tools=["RefundEvidenceCheckTool"],
    ),
    "HumanReviewSkill": SkillProfile(
        name="HumanReviewSkill",
        purpose="Prepare a case for human review when escalation rules match or the agent cannot answer safely.",
        rules=[
            "Run before customer-facing drafting for critical cases.",
            "Run after a guardrail blocks an unsupported answer.",
            "Include the review reason, customer context, and a short issue summary.",
        ],
        planned_tools=["HumanHandoffTool", "AuditLoggingTool"],
    ),
}


def plan_skills_for_subagent(route: SubagentRouteResult) -> SkillPlan:
    """Build the reusable workflow plan for a selected subagent."""
    skills = [SKILL_REGISTRY[skill_name] for skill_name in route.allowed_skills]

    return SkillPlan(
        selected_subagent=route.selected_subagent,
        skills=skills,
        execution_order=[skill.name for skill in skills],
        reason=f"{route.selected_subagent} can use {len(skills)} skill(s) for {route.category} cases.",
    )


def plan_human_review_skill(critical_result: CriticalCheckResult) -> SkillPlan:
    """Build the workflow plan for cases that bypass subagents and go to humans."""
    review_skill = SKILL_REGISTRY["HumanReviewSkill"]
    triggers = ", ".join(critical_result.matched_triggers) or "unknown trigger"

    return SkillPlan(
        selected_subagent="HumanReview",
        skills=[review_skill],
        execution_order=[review_skill.name],
        reason=f"Critical gate matched {triggers}, so the case must be sent to human review.",
    )


def add_human_review_skill(skill_plan: SkillPlan, reason: str) -> SkillPlan:
    """Append HumanReviewSkill when a non-critical workflow later needs human review."""
    if "HumanReviewSkill" in skill_plan.execution_order:
        return skill_plan

    review_skill = SKILL_REGISTRY["HumanReviewSkill"]
    skills = [*skill_plan.skills, review_skill]

    return SkillPlan(
        selected_subagent=skill_plan.selected_subagent,
        skills=skills,
        execution_order=[skill.name for skill in skills],
        reason=f"{skill_plan.reason} Human review added because {reason}",
    )


plan_handoff_skill = plan_human_review_skill
