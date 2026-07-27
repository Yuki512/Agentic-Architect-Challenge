from dataclasses import dataclass
import re
from typing import Any


CRITICAL_PATTERNS = {
    "data_loss": re.compile(r"\bdata\s+loss\b|\blost\s+(my|our)\s+data\b", re.IGNORECASE),
    "service_outage": re.compile(r"\bservice\s+outage\b|\bsystem\s+outage\b|\boutage\b", re.IGNORECASE),
    "security_breach": re.compile(
        r"\bsecurity\s+breach\b|\bdata\s+breach\b|\bhacked\b|\bunauthorized\s+access\b",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class CriticalCheckResult:
    is_critical: bool
    matched_triggers: list[str]
    contact_count_last_7_days: int
    reason: str
    recommended_action: str


def check_critical_issue(email_case: dict[str, Any]) -> CriticalCheckResult:
    """Check whether a support email must be routed to a human before drafting."""
    subject = str(email_case.get("subject", ""))
    body = str(email_case.get("body", ""))
    text = f"{subject}\n{body}"

    matched_triggers = [
        trigger_name
        for trigger_name, pattern in CRITICAL_PATTERNS.items()
        if pattern.search(text)
    ]

    contact_count = _safe_int(email_case.get("contact_count_last_7_days", 0))
    if contact_count > 3:
        matched_triggers.append("repeat_contact_over_3_in_7_days")

    is_critical = bool(matched_triggers)
    if is_critical:
        reason = "Human review is required before any customer-facing draft is generated."
        recommended_action = "handoff_to_human_agent"
    else:
        reason = "No mandatory critical trigger was detected."
        recommended_action = "continue_to_classification"

    return CriticalCheckResult(
        is_critical=is_critical,
        matched_triggers=matched_triggers,
        contact_count_last_7_days=contact_count,
        reason=reason,
        recommended_action=recommended_action,
    )


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

