from dataclasses import replace
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from support_agent.classifier import (
    CATEGORY_KEYWORDS,
    ClassificationResult,
    classify_email,
)
from support_agent.config import DraftLLMConfig, load_router_llm_config


ALLOWED_CATEGORIES = {*CATEGORY_KEYWORDS, "Other"}
MAX_EMAIL_CHARS = 6_000
MAX_REASON_CHARS = 300


class RouterAgentError(RuntimeError):
    """Raised when the Router Agent response cannot be trusted."""


RouterTransport = Callable[
    [str, str, dict[str, Any], float],
    dict[str, Any],
]


def classify_with_configured_router(
    email_case: dict[str, Any],
) -> ClassificationResult:
    baseline = classify_email(email_case)
    try:
        config = load_router_llm_config()
    except ValueError as exc:
        return replace(
            baseline,
            fallback_reason=str(exc),
        )

    if config.provider != "deepseek":
        return baseline
    if not config.api_key:
        return replace(
            baseline,
            fallback_reason="DEEPSEEK_API_KEY is not configured.",
        )

    try:
        return classify_with_deepseek(
            email_case,
            baseline=baseline,
            config=config,
        )
    except (RouterAgentError, ValueError) as exc:
        return replace(
            baseline,
            fallback_reason=str(exc),
        )


def classify_with_deepseek(
    email_case: dict[str, Any],
    *,
    baseline: ClassificationResult | None = None,
    config: DraftLLMConfig,
    transport: RouterTransport | None = None,
) -> ClassificationResult:
    if not config.api_key:
        raise RouterAgentError("DEEPSEEK_API_KEY is not configured.")

    email_text = _email_text(email_case)
    if not email_text:
        raise RouterAgentError(
            "Subject or body is required for Router Agent classification."
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
        baseline=baseline or classify_email(email_case),
        provider=config.provider,
        model=config.model,
    )


def _build_payload(email_text: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a customer-support Router Agent. Classify the "
                    "email into one primary category: Billing, Refund, "
                    "Technical, Account, Shipping, Feedback, or Other. "
                    "Billing covers charges, payments, invoices, and receipts. "
                    "Refund covers returns, refunds, and cancellations. "
                    "Technical covers app crashes, bugs, and technical errors. "
                    "Account covers login, password, profile, and privacy. "
                    "Shipping covers delivery, packages, and tracking. "
                    "Feedback covers suggestions, complaints, and praise. "
                    "Use Other only when none fits. Do not decide whether the "
                    "case is critical. Return only JSON with this shape: "
                    '{"primary_category":"Billing",'
                    '"categories":["Billing"],'
                    '"confidence":0.0,'
                    '"reason":"short explanation"}.'
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
        "max_tokens": 250,
        "stream": False,
    }


def _parse_response(
    response: dict[str, Any],
    *,
    baseline: ClassificationResult,
    provider: str,
    model: str,
) -> ClassificationResult:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RouterAgentError(
            "DeepSeek response is missing Router Agent content."
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise RouterAgentError(
            "DeepSeek returned empty Router Agent content."
        )

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RouterAgentError(
            "DeepSeek Router Agent content is not valid JSON."
        ) from exc
    if not isinstance(value, dict):
        raise RouterAgentError(
            "DeepSeek Router Agent JSON must be an object."
        )

    primary_category = _normalize_category(
        value.get("primary_category"),
    )
    raw_categories = value.get("categories")
    if not isinstance(raw_categories, list) or not raw_categories:
        raise RouterAgentError(
            "DeepSeek Router Agent categories must be a non-empty list."
        )
    categories = list(
        dict.fromkeys(_normalize_category(item) for item in raw_categories)
    )
    if primary_category not in categories:
        categories.insert(0, primary_category)

    confidence = value.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= float(confidence) <= 1
    ):
        raise RouterAgentError(
            "DeepSeek returned an invalid routing confidence."
        )
    reason = re.sub(
        r"\s+",
        " ",
        str(value.get("reason", "")),
    ).strip()
    if not reason or len(reason) > MAX_REASON_CHARS:
        raise RouterAgentError(
            "DeepSeek returned an invalid routing reason."
        )

    return ClassificationResult(
        primary_category=primary_category,
        categories=categories,
        confidence=round(float(confidence), 4),
        scores=baseline.scores,
        reason=reason,
        recommended_subagent=f"{primary_category}Subagent",
        provider=provider,
        model=model,
    )


def _normalize_category(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    category_map = {
        category.casefold(): category
        for category in ALLOWED_CATEGORIES
    }
    if normalized not in category_map:
        raise RouterAgentError(
            "DeepSeek returned an unsupported routing category."
        )
    return category_map[normalized]


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
            "User-Agent": "Part1-Router-Agent/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RouterAgentError(
            f"DeepSeek Router Agent failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise RouterAgentError(
            "DeepSeek could not be reached by the Router Agent."
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RouterAgentError(
            "DeepSeek returned an invalid Router Agent response."
        ) from exc
