from dataclasses import dataclass
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from support_agent.config import DraftLLMConfig, load_draft_llm_config


ALLOWED_CONDITIONS = {
    "data_loss",
    "service_outage",
    "security_breach",
    "none",
}
ALLOWED_DECISIONS = {"critical", "non_critical", "uncertain"}
MIN_NON_CRITICAL_CONFIDENCE = 0.75
MAX_EMAIL_CHARS = 6_000
MAX_REASON_CHARS = 300


class SemanticCriticalError(RuntimeError):
    """Raised when the semantic critical check cannot be trusted."""


@dataclass(frozen=True)
class SemanticCriticalResult:
    status: str
    requires_human_review: bool
    matched_condition: str
    confidence: float | None
    evidence: str
    reason: str
    provider: str
    model: str


SemanticTransport = Callable[
    [str, str, dict[str, Any], float],
    dict[str, Any],
]


def check_semantic_critical_with_configured_provider(
    email_case: dict[str, Any],
) -> SemanticCriticalResult:
    try:
        config = load_draft_llm_config()
    except ValueError as exc:
        return semantic_error_result(str(exc))

    if config.provider != "deepseek":
        return SemanticCriticalResult(
            status="skipped",
            requires_human_review=False,
            matched_condition="none",
            confidence=None,
            evidence="",
            reason="Semantic critical checking is disabled for the configured provider.",
            provider=config.provider,
            model=config.model,
        )
    if not config.api_key:
        return SemanticCriticalResult(
            status="skipped",
            requires_human_review=False,
            matched_condition="none",
            confidence=None,
            evidence="",
            reason="DEEPSEEK_API_KEY is not configured for semantic checking.",
            provider=config.provider,
            model=config.model,
        )

    try:
        return check_semantic_critical_with_deepseek(
            email_case,
            config=config,
        )
    except (SemanticCriticalError, ValueError) as exc:
        return semantic_error_result(
            str(exc),
            provider=config.provider,
            model=config.model,
        )


def check_semantic_critical_with_deepseek(
    email_case: dict[str, Any],
    *,
    config: DraftLLMConfig,
    transport: SemanticTransport | None = None,
) -> SemanticCriticalResult:
    if not config.api_key:
        raise SemanticCriticalError("DEEPSEEK_API_KEY is not configured.")

    email_text = _email_text(email_case)
    if not email_text:
        raise SemanticCriticalError(
            "Subject or body is required for semantic critical checking."
        )

    request_transport = transport or _post_json
    response = request_transport(
        f"{config.base_url}/chat/completions",
        config.api_key,
        _build_payload(email_text, config.model),
        config.timeout_seconds,
    )
    return _parse_response(
        response,
        email_text=email_text,
        provider=config.provider,
        model=config.model,
    )


def semantic_error_result(
    reason: str,
    *,
    provider: str = "deepseek",
    model: str = "unknown",
) -> SemanticCriticalResult:
    return SemanticCriticalResult(
        status="error",
        requires_human_review=False,
        matched_condition="none",
        confidence=None,
        evidence="",
        reason=re.sub(r"\s+", " ", reason).strip()[:MAX_REASON_CHARS],
        provider=provider,
        model=model,
    )


def skip_semantic_critical_check(
    email_case: dict[str, Any],
) -> SemanticCriticalResult:
    del email_case
    return SemanticCriticalResult(
        status="skipped",
        requires_human_review=False,
        matched_condition="none",
        confidence=None,
        evidence="",
        reason="Semantic critical checking was skipped by the caller.",
        provider="deterministic",
        model="none",
    )


def _build_payload(email_text: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Classify whether a customer support email semantically "
                    "describes one of exactly three mandatory escalation "
                    "conditions: data loss, a current service outage, or a "
                    "security breach. Detect paraphrases, but do not treat "
                    "general prevention questions, hypothetical scenarios, "
                    "billing, refunds, shipping delays, or ordinary login "
                    "problems as critical. Contact frequency is checked "
                    "separately. Return only JSON with: "
                    '{"decision":"critical|non_critical|uncertain",'
                    '"condition":"data_loss|service_outage|security_breach|none",'
                    '"confidence":0.0,'
                    '"evidence":"exact contiguous quote from the email or empty",'
                    '"reason":"short explanation"}. '
                    "A critical decision requires an exact evidence quote."
                ),
            },
            {
                "role": "user",
                "content": email_text,
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": 300,
        "stream": False,
    }


def _post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Part1-Hybrid-Critical-Gate/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SemanticCriticalError(
            f"DeepSeek semantic check failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise SemanticCriticalError(
            "DeepSeek could not be reached for semantic checking."
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticCriticalError(
            "DeepSeek returned an invalid semantic-check response."
        ) from exc


def _parse_response(
    response: dict[str, Any],
    *,
    email_text: str,
    provider: str,
    model: str,
) -> SemanticCriticalResult:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SemanticCriticalError(
            "DeepSeek response is missing semantic-check content."
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise SemanticCriticalError(
            "DeepSeek returned empty semantic-check content."
        )

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SemanticCriticalError(
            "DeepSeek semantic-check content is not valid JSON."
        ) from exc
    if not isinstance(value, dict):
        raise SemanticCriticalError(
            "DeepSeek semantic-check JSON must be an object."
        )

    decision = str(value.get("decision", "")).strip().casefold()
    condition = str(value.get("condition", "")).strip().casefold()
    confidence = value.get("confidence")
    evidence = str(value.get("evidence", "")).strip()
    reason = re.sub(r"\s+", " ", str(value.get("reason", ""))).strip()

    if decision not in ALLOWED_DECISIONS:
        raise SemanticCriticalError(
            "DeepSeek returned an unsupported semantic decision."
        )
    if condition not in ALLOWED_CONDITIONS:
        raise SemanticCriticalError(
            "DeepSeek returned an unsupported critical condition."
        )
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= float(confidence) <= 1
    ):
        raise SemanticCriticalError(
            "DeepSeek returned an invalid semantic confidence."
        )
    if not reason:
        raise SemanticCriticalError(
            "DeepSeek semantic check is missing a reason."
        )
    if len(reason) > MAX_REASON_CHARS:
        raise SemanticCriticalError(
            "DeepSeek semantic-check reason is too long."
        )
    if evidence and evidence.casefold() not in email_text.casefold():
        raise SemanticCriticalError(
            "DeepSeek semantic evidence is absent from the email."
        )

    if decision == "critical":
        if condition == "none" or not evidence:
            raise SemanticCriticalError(
                "A critical semantic decision requires a condition and evidence."
            )
    elif decision == "non_critical" and condition != "none":
        raise SemanticCriticalError(
            "A non-critical semantic decision cannot name a critical condition."
        )

    normalized_confidence = round(float(confidence), 4)
    status = decision
    if (
        decision == "non_critical"
        and normalized_confidence < MIN_NON_CRITICAL_CONFIDENCE
    ):
        status = "uncertain"
        reason = (
            "Low-confidence non-critical decision requires human review. "
            f"{reason}"
        )[:MAX_REASON_CHARS]

    return SemanticCriticalResult(
        status=status,
        requires_human_review=status in {"critical", "uncertain"},
        matched_condition=condition,
        confidence=normalized_confidence,
        evidence=evidence,
        reason=reason,
        provider=provider,
        model=model,
    )


def _email_text(email_case: dict[str, Any]) -> str:
    subject = re.sub(
        r"\s+",
        " ",
        str(email_case.get("subject") or ""),
    ).strip()
    body = re.sub(
        r"\s+",
        " ",
        str(email_case.get("body") or ""),
    ).strip()
    return f"Subject: {subject}\nEmail: {body}".strip()[:MAX_EMAIL_CHARS]
