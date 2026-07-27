from dataclasses import dataclass
import re
from typing import Any

from support_agent.drafting import DraftResponse


@dataclass(frozen=True)
class GuardrailResult:
    passed: bool
    status: str
    reason: str
    final_draft: DraftResponse


def apply_refund_guardrail(
    email_case: dict[str, Any],
    category: str,
    draft: DraftResponse,
) -> GuardrailResult:
    """Block refund replies that are not directly supported by the FAQ evidence."""
    if category != "Refund":
        return GuardrailResult(
            passed=True,
            status="not_applicable",
            reason="Refund guardrail is only applied to Refund category cases.",
            final_draft=draft,
        )

    customer_name = str(email_case.get("customer_name") or "there").strip()
    question_text = f"{email_case.get('subject', '')} {email_case.get('body', '')}"
    evidence_text = " ".join(passage.text for passage in draft.evidence)

    if not draft.evidence:
        blocked_draft = _blocked_refund_draft(
            customer_name,
            "No refund evidence was retrieved from the FAQ PDF.",
        )
        return GuardrailResult(
            passed=False,
            status="blocked",
            reason="No refund evidence was retrieved from the FAQ PDF.",
            final_draft=blocked_draft,
        )

    if not _has_refund_section_evidence(draft):
        blocked_draft = _blocked_refund_draft(
            customer_name,
            "Retrieved evidence did not come from the refund FAQ section.",
        )
        return GuardrailResult(
            passed=False,
            status="blocked",
            reason="Retrieved evidence did not come from the refund FAQ section.",
            final_draft=blocked_draft,
        )

    unsupported_window = _detect_unsupported_refund_window(question_text, evidence_text)
    if unsupported_window:
        blocked_draft = _blocked_refund_draft(
            customer_name,
            f"The customer asked about {unsupported_window}, but the FAQ only supports the documented refund policy.",
        )
        return GuardrailResult(
            passed=False,
            status="blocked",
            reason=(
                f"The customer asked about {unsupported_window}, but that exact refund condition "
                "is not supported by the FAQ evidence."
            ),
            final_draft=blocked_draft,
        )

    return GuardrailResult(
        passed=True,
        status="passed",
        reason="Refund answer is supported by retrieved refund FAQ evidence.",
        final_draft=draft,
    )


def _blocked_refund_draft(customer_name: str, reason: str) -> DraftResponse:
    return DraftResponse(
        status="needs_human_review",
        reply=(
            f"Hi {customer_name}, thanks for reaching out. I could not confirm that refund detail "
            "from the available help-center FAQ, so I am sending this to our support team for review "
            "instead of guessing about the policy."
        ),
        evidence=[],
        internal_notes=[
            "RefundGuardrailSkill blocked the customer-facing refund draft.",
            reason,
        ],
        provider="human_review",
    )


def _has_refund_section_evidence(draft: DraftResponse) -> bool:
    return any("refund" in passage.section.casefold() for passage in draft.evidence)


def _detect_unsupported_refund_window(question_text: str, evidence_text: str) -> str | None:
    question_days = _extract_day_counts(question_text)
    if not question_days:
        return None

    supported_days = _extract_day_counts(evidence_text)
    if not supported_days:
        return f"{question_days[0]} days"

    max_supported_days = max(supported_days)
    unsupported = [days for days in question_days if days > max_supported_days]
    return f"{unsupported[0]} days" if unsupported else None


def _extract_day_counts(text: str) -> list[int]:
    return [int(match) for match in re.findall(r"\b(\d+)\s*(?:calendar\s+)?days?\b", text.casefold())]
