from dataclasses import asdict, dataclass, replace
import operator
from typing import Annotated, Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from support_agent.classifier import ClassificationResult, classify_email
from support_agent.critical_detector import CriticalCheckResult, check_critical_issue
from support_agent.drafting import DraftResponse
from support_agent.guardrails import GuardrailResult, apply_refund_guardrail
from support_agent.llm_drafting import draft_with_configured_provider
from support_agent.semantic_critical import (
    SemanticCriticalResult,
    check_semantic_critical_with_configured_provider,
    semantic_error_result,
)
from support_agent.skills import (
    SkillPlan,
    add_human_review_skill,
    plan_human_review_skill,
    plan_skills_for_subagent,
)
from support_agent.subagents import SubagentRouteResult, route_to_subagent
from support_agent.tools import (
    AuditLogEntry,
    HumanHandoffTicket,
    PDFSearchResult,
    audit_logging_tool,
    human_handoff_tool,
    pdf_search_tool,
)

DraftFunction = Callable[
    [dict[str, Any], SubagentRouteResult, PDFSearchResult],
    DraftResponse,
]
SemanticCriticalFunction = Callable[
    [dict[str, Any]],
    SemanticCriticalResult,
]
ClassifierFunction = Callable[
    [dict[str, Any]],
    ClassificationResult,
]


@dataclass(frozen=True)
class ProcessEmailResult:
    case_id: str
    status: str
    critical_check: CriticalCheckResult
    semantic_critical_check: SemanticCriticalResult | None
    classification: ClassificationResult | None
    route: SubagentRouteResult | None
    skill_plan: SkillPlan
    search_result: PDFSearchResult | None
    guardrail: GuardrailResult | None
    final_draft: DraftResponse | None
    handoff_ticket: HumanHandoffTicket | None
    audit_logs: list[AuditLogEntry]


class EmailWorkflowState(TypedDict, total=False):
    email_case: dict[str, Any]
    case_id: str
    classification: ClassificationResult
    critical_check: CriticalCheckResult
    semantic_critical_check: SemanticCriticalResult | None
    route: SubagentRouteResult
    skill_plan: SkillPlan
    search_result: PDFSearchResult
    guardrail: GuardrailResult
    final_draft: DraftResponse
    handoff_ticket: HumanHandoffTicket
    status: str
    audit_logs: Annotated[list[AuditLogEntry], operator.add]


def process_email(
    email_case: dict[str, Any],
    *,
    classifier: ClassifierFunction = classify_email,
    drafter: DraftFunction = draft_with_configured_provider,
    semantic_checker: SemanticCriticalFunction = (
        check_semantic_critical_with_configured_provider
    ),
) -> ProcessEmailResult:
    """Run the Part 1 LangGraph support email workflow."""
    case_id = str(email_case.get("case_id", "UNKNOWN-CASE"))
    graph = build_email_workflow(
        classifier=classifier,
        drafter=drafter,
        semantic_checker=semantic_checker,
    )
    state = graph.invoke(
        {
            "email_case": email_case,
            "case_id": case_id,
            "semantic_critical_check": None,
            "audit_logs": [],
        }
    )
    return _result_from_state(state)


def build_email_workflow(
    *,
    classifier: ClassifierFunction = classify_email,
    drafter: DraftFunction = draft_with_configured_provider,
    semantic_checker: SemanticCriticalFunction = (
        check_semantic_critical_with_configured_provider
    ),
) -> Any:
    """Build the explicit LangGraph workflow used by Part 1."""
    builder = StateGraph(EmailWorkflowState)
    builder.add_node(
        "router_agent",
        lambda state: _router_agent_node(state, classifier),
    )
    builder.add_node("critical_keyword_check", _critical_keyword_node)
    builder.add_node(
        "critical_semantic_check",
        lambda state: _semantic_critical_node(state, semantic_checker),
    )
    builder.add_node("human_handoff", _human_handoff_node)
    builder.add_node("specialist_routing", _specialist_routing_node)
    builder.add_node("pdf_search", _pdf_search_node)
    builder.add_node(
        "draft_response",
        lambda state: _draft_response_node(state, drafter),
    )
    builder.add_node("refund_guardrail", _refund_guardrail_node)

    builder.add_edge(START, "router_agent")
    builder.add_edge("router_agent", "critical_keyword_check")
    builder.add_conditional_edges(
        "critical_keyword_check",
        _route_after_critical_check,
        {
            "human_handoff": "human_handoff",
            "semantic_check": "critical_semantic_check",
        },
    )
    builder.add_conditional_edges(
        "critical_semantic_check",
        _route_after_semantic_check,
        {
            "human_handoff": "human_handoff",
            "specialist_routing": "specialist_routing",
        },
    )
    builder.add_edge("human_handoff", END)
    builder.add_edge("specialist_routing", "pdf_search")
    builder.add_edge("pdf_search", "draft_response")
    builder.add_edge("draft_response", "refund_guardrail")
    builder.add_edge("refund_guardrail", END)
    return builder.compile()


def _router_agent_node(
    state: EmailWorkflowState,
    classifier: ClassifierFunction,
) -> dict[str, Any]:
    classification = classifier(state["email_case"])
    if not isinstance(classification, ClassificationResult):
        raise TypeError("Router Agent returned an unsupported result.")
    return {
        "classification": classification,
        "audit_logs": [
            audit_logging_tool(
                case_id=state["case_id"],
                event_type="classification",
                status="success",
                details={
                    "primary_category": classification.primary_category,
                    "confidence": classification.confidence,
                    "recommended_subagent": (
                        classification.recommended_subagent
                    ),
                    "provider": classification.provider,
                    "model": classification.model,
                    "fallback_reason": classification.fallback_reason,
                },
            )
        ],
    }


def _critical_keyword_node(state: EmailWorkflowState) -> dict[str, Any]:
    result = check_critical_issue(state["email_case"])
    return {
        "critical_check": result,
        "audit_logs": [
            audit_logging_tool(
                case_id=state["case_id"],
                event_type="critical_check",
                status="critical" if result.is_critical else "passed",
                details={
                    "matched_triggers": result.matched_triggers,
                    "recommended_action": result.recommended_action,
                },
            )
        ],
    }


def _semantic_critical_node(
    state: EmailWorkflowState,
    semantic_checker: SemanticCriticalFunction,
) -> dict[str, Any]:
    try:
        candidate = semantic_checker(state["email_case"])
        if not isinstance(candidate, SemanticCriticalResult):
            raise TypeError(
                "Semantic critical checker returned an unsupported result."
            )
        semantic_result = candidate
    except Exception as exc:
        semantic_result = semantic_error_result(
            f"Semantic critical check failed: {type(exc).__name__}."
        )

    critical_result = state["critical_check"]
    if semantic_result.requires_human_review:
        trigger = (
            f"semantic_{semantic_result.matched_condition}"
            if semantic_result.matched_condition != "none"
            else "semantic_uncertain"
        )
        critical_result = replace(
            critical_result,
            is_critical=True,
            matched_triggers=[trigger],
            reason=(
                "Semantic critical checking requires human review before "
                "any customer-facing draft is generated. "
                f"{semantic_result.reason}"
            ),
            recommended_action="handoff_to_human_agent",
        )

    return {
        "semantic_critical_check": semantic_result,
        "critical_check": critical_result,
        "audit_logs": [
            audit_logging_tool(
                case_id=state["case_id"],
                event_type="semantic_critical_check",
                status=semantic_result.status,
                details={
                    "matched_condition": semantic_result.matched_condition,
                    "confidence": semantic_result.confidence,
                    "evidence": semantic_result.evidence,
                    "reason": semantic_result.reason,
                    "provider": semantic_result.provider,
                    "model": semantic_result.model,
                },
            )
        ],
    }


def _route_after_critical_check(
    state: EmailWorkflowState,
) -> Literal["human_handoff", "semantic_check"]:
    if state["critical_check"].is_critical:
        return "human_handoff"
    return "semantic_check"


def _route_after_semantic_check(
    state: EmailWorkflowState,
) -> Literal["human_handoff", "specialist_routing"]:
    if state["critical_check"].is_critical:
        return "human_handoff"
    return "specialist_routing"


def _human_handoff_node(state: EmailWorkflowState) -> dict[str, Any]:
    critical_result = state["critical_check"]
    handoff_ticket = human_handoff_tool(
        state["email_case"],
        critical_result,
    )
    return {
        "status": "human_review",
        "skill_plan": plan_human_review_skill(critical_result),
        "handoff_ticket": handoff_ticket,
        "audit_logs": [
            audit_logging_tool(
                case_id=state["case_id"],
                event_type="human_handoff_created",
                status="success",
                details={
                    "ticket_id": handoff_ticket.ticket_id,
                    "matched_triggers": handoff_ticket.matched_triggers,
                },
            )
        ],
    }


def _specialist_routing_node(
    state: EmailWorkflowState,
) -> dict[str, Any]:
    route = route_to_subagent(state["classification"])
    return {
        "route": route,
        "skill_plan": plan_skills_for_subagent(route),
    }


def _pdf_search_node(state: EmailWorkflowState) -> dict[str, Any]:
    email_case = state["email_case"]
    search_result = pdf_search_tool(
        query=f"{email_case.get('subject', '')} {email_case.get('body', '')}",
        category=state["classification"].primary_category,
        limit=2,
    )
    return {
        "search_result": search_result,
        "audit_logs": [
            audit_logging_tool(
                case_id=state["case_id"],
                event_type="pdf_search",
                status="found" if search_result.found else "not_found",
                details={
                    "source_path": search_result.source_path,
                    "passage_count": len(search_result.passages),
                },
            )
        ],
    }


def _draft_response_node(
    state: EmailWorkflowState,
    drafter: DraftFunction,
) -> dict[str, Any]:
    return {
        "final_draft": drafter(
            state["email_case"],
            state["route"],
            state["search_result"],
        )
    }


def _refund_guardrail_node(
    state: EmailWorkflowState,
) -> dict[str, Any]:
    guardrail = apply_refund_guardrail(
        state["email_case"],
        state["classification"].primary_category,
        state["final_draft"],
    )
    final_draft = guardrail.final_draft
    skill_plan = state["skill_plan"]
    if final_draft.status == "needs_human_review":
        skill_plan = add_human_review_skill(skill_plan, guardrail.reason)

    return {
        "status": _public_status(final_draft.status),
        "guardrail": guardrail,
        "final_draft": final_draft,
        "skill_plan": skill_plan,
        "audit_logs": [
            audit_logging_tool(
                case_id=state["case_id"],
                event_type="guardrail_check",
                status=guardrail.status,
                details={"reason": guardrail.reason},
            ),
            audit_logging_tool(
                case_id=state["case_id"],
                event_type="final_result",
                status=final_draft.status,
                details={
                    "selected_subagent": state["route"].selected_subagent,
                    "response_provider": final_draft.provider,
                    "response_model": final_draft.model,
                    "fallback_reason": final_draft.fallback_reason,
                },
            ),
        ],
    }


def _result_from_state(state: EmailWorkflowState) -> ProcessEmailResult:
    return ProcessEmailResult(
        case_id=state["case_id"],
        status=state["status"],
        critical_check=state["critical_check"],
        semantic_critical_check=state.get("semantic_critical_check"),
        classification=state.get("classification"),
        route=state.get("route"),
        skill_plan=state["skill_plan"],
        search_result=state.get("search_result"),
        guardrail=state.get("guardrail"),
        final_draft=state.get("final_draft"),
        handoff_ticket=state.get("handoff_ticket"),
        audit_logs=state.get("audit_logs", []),
    )


def process_email_as_dict(
    email_case: dict[str, Any],
    *,
    classifier: ClassifierFunction = classify_email,
    drafter: DraftFunction = draft_with_configured_provider,
    semantic_checker: SemanticCriticalFunction = (
        check_semantic_critical_with_configured_provider
    ),
) -> dict[str, Any]:
    """Serialize the full pipeline result for scripts, tests, and future web UI responses."""
    return asdict(
        process_email(
            email_case,
            classifier=classifier,
            drafter=drafter,
            semantic_checker=semantic_checker,
        )
    )


def _public_status(status: str) -> str:
    if status == "needs_human_review":
        return "human_review"
    return status
