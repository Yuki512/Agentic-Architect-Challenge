from dataclasses import dataclass
import re
from typing import Any

from support_agent.subagents import SubagentRouteResult
from support_agent.tools import EvidencePassage, PDFSearchResult


@dataclass(frozen=True)
class DraftResponse:
    status: str
    reply: str
    evidence: list[EvidencePassage]
    internal_notes: list[str]
    provider: str = "deterministic"
    model: str | None = None
    fallback_reason: str | None = None


def draft_grounded_response(
    email_case: dict[str, Any],
    route: SubagentRouteResult,
    search_result: PDFSearchResult,
) -> DraftResponse:
    """Draft a customer reply from the selected subagent using retrieved PDF evidence."""
    customer_name = str(email_case.get("customer_name") or "there").strip()

    if not search_result.found:
        return DraftResponse(
            status="needs_human_review",
            reply=(
                f"Hi {customer_name}, thanks for reaching out. I could not find enough information "
                "in the available help-center FAQ to answer this confidently, so I am sending this "
                "to our support team for review."
            ),
            evidence=[],
            internal_notes=[
                f"{route.selected_subagent} could not find matching FAQ evidence.",
                "No customer-facing policy claim was made.",
            ],
        )

    evidence = search_result.passages
    answer_text = _answer_from_evidence(route.category, evidence[0].text)

    reply = (
        f"Hi {customer_name}, thanks for reaching out. {answer_text} "
        "If you want us to check your specific order or account, please reply with your order number "
        "or the email address linked to your account."
    )

    return DraftResponse(
        status="drafted",
        reply=_trim_words(reply, 150),
        evidence=evidence,
        internal_notes=[
            f"Draft created by {route.selected_subagent}.",
            f"Primary evidence source: page {evidence[0].page_number}, section '{evidence[0].section}'.",
        ],
    )


def _answer_from_evidence(category: str, evidence_text: str) -> str:
    cleaned = _remove_section_prefix(evidence_text)

    if category == "Refund":
        return _first_relevant_sentence(
            cleaned,
            [
                "eligible for a refund",
                "refund",
                "not refundable",
                "cancel",
                "business days",
            ],
        )
    if category == "Billing":
        return _first_relevant_sentence(
            cleaned,
            ["charged twice", "duplicate charge", "invoice", "receipt", "payment failed"],
        )
    if category == "Account":
        return _first_relevant_sentence(
            cleaned,
            ["reset their password", "account email address", "private browser window"],
        )
    if category == "Shipping":
        return _first_relevant_sentence(
            cleaned,
            ["delivery", "package", "tracking", "damaged"],
        )
    if category == "Technical":
        return _first_relevant_sentence(
            cleaned,
            ["update the app", "restart the device", "error message", "tracking"],
        )
    return _trim_words(cleaned, 55)


def _first_relevant_sentence(text: str, keywords: list[str]) -> str:
    sentences = [
        sentence
        for sentence in _split_sentences(text)
        if not _looks_like_heading_or_question(sentence)
    ]
    for keyword in keywords:
        for sentence in sentences:
            if keyword.casefold() in sentence.casefold():
                return sentence
    return sentences[0] if sentences else "The FAQ includes related information, but a human should review the details."


def _split_sentences(text: str) -> list[str]:
    sentences = []
    current = []
    for token in text.split():
        current.append(token)
        if token.endswith((".", "?", "!")):
            sentences.append(" ".join(current))
            current = []
    if current:
        sentences.append(" ".join(current))
    return sentences


def _remove_section_prefix(text: str) -> str:
    return re.sub(r"^\d+\.\s+[A-Za-z ]+\s+", "", text).strip()


def _looks_like_heading_or_question(sentence: str) -> bool:
    stripped = sentence.strip()
    return stripped.endswith("?") or stripped.count(".") == 0 and len(stripped.split()) <= 8


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(".,") + "."
