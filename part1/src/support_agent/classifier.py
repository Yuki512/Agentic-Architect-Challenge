from dataclasses import dataclass
import re
from typing import Any


CATEGORY_KEYWORDS = {
    "Refund": [
        "refund",
        "return",
        "cancel",
        "cancellation",
        "non-refundable",
        "money back",
    ],
    "Billing": [
        "charged",
        "charge",
        "invoice",
        "receipt",
        "payment",
        "card",
        "duplicate",
        "billing",
    ],
    "Technical": [
        "crash",
        "freezes",
        "bug",
        "error",
        "app",
        "tracking does not update",
        "checkout error",
    ],
    "Account": [
        "log in",
        "login",
        "password",
        "account",
        "profile",
        "email address",
    ],
    "Shipping": [
        "package",
        "delivery",
        "shipping",
        "tracking",
        "arrived damaged",
        "carrier",
    ],
    "Feedback": [
        "feedback",
        "feature request",
        "suggestion",
        "complaint",
        "praise",
        "review",
    ],
}


@dataclass(frozen=True)
class ClassificationResult:
    primary_category: str
    categories: list[str]
    confidence: float
    scores: dict[str, int]
    reason: str
    recommended_subagent: str
    provider: str = "deterministic"
    model: str = "keyword-rules"
    fallback_reason: str | None = None


def classify_email(email_case: dict[str, Any]) -> ClassificationResult:
    """Classify a support email into the category used by the router agent."""
    subject = str(email_case.get("subject", ""))
    body = str(email_case.get("body", ""))
    text = _normalize_text(f"{subject}\n{body}")

    scores = {
        category: _score_category(text, keywords)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    matched_scores = {category: score for category, score in scores.items() if score > 0}

    if not matched_scores:
        return ClassificationResult(
            primary_category="Other",
            categories=["Other"],
            confidence=0.2,
            scores=scores,
            reason="No category-specific keywords were detected.",
            recommended_subagent="OtherSubagent",
        )

    sorted_matches = sorted(matched_scores.items(), key=lambda item: (-item[1], item[0]))
    primary_category = sorted_matches[0][0]
    categories = [category for category, _score in sorted_matches]

    top_score = sorted_matches[0][1]
    total_score = sum(matched_scores.values())
    confidence = round(top_score / total_score, 2)

    return ClassificationResult(
        primary_category=primary_category,
        categories=categories,
        confidence=confidence,
        scores=scores,
        reason=f"Matched {top_score} keyword signal(s) for {primary_category}.",
        recommended_subagent=f"{primary_category}Subagent",
    )


def _score_category(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if re.search(rf"\b{re.escape(keyword)}\b", text))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()
