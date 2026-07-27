from dataclasses import replace
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from support_agent.config import DraftLLMConfig, load_draft_llm_config
from support_agent.drafting import DraftResponse, draft_grounded_response
from support_agent.subagents import SubagentRouteResult
from support_agent.tools import EvidencePassage, PDFSearchResult


MAX_DRAFT_WORDS = 150
MIN_GROUNDING_COVERAGE = 0.35
UNSUPPORTED_PROMISE_TERMS = {
    "always",
    "definitely",
    "guarantee",
    "guaranteed",
    "immediately",
    "promise",
}
CONTENT_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "hi",
    "i",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "please",
    "that",
    "the",
    "their",
    "this",
    "to",
    "us",
    "we",
    "with",
    "you",
    "your",
}


class DeepSeekDraftError(RuntimeError):
    """Raised when DeepSeek cannot produce a grounded customer reply."""


DeepSeekTransport = Callable[[str, str, dict[str, Any], float], dict[str, Any]]


def draft_with_configured_provider(
    email_case: dict[str, Any],
    route: SubagentRouteResult,
    search_result: PDFSearchResult,
) -> DraftResponse:
    if not search_result.found:
        return draft_grounded_response(email_case, route, search_result)

    config = load_draft_llm_config()
    if config.provider == "deterministic":
        return draft_grounded_response(email_case, route, search_result)
    if not config.api_key:
        return _fallback_draft(
            email_case,
            route,
            search_result,
            "DEEPSEEK_API_KEY is not configured.",
        )

    try:
        return draft_with_deepseek(
            email_case,
            route,
            search_result,
            config=config,
        )
    except (DeepSeekDraftError, ValueError) as exc:
        return _fallback_draft(
            email_case,
            route,
            search_result,
            str(exc),
        )


def draft_with_deepseek(
    email_case: dict[str, Any],
    route: SubagentRouteResult,
    search_result: PDFSearchResult,
    *,
    config: DraftLLMConfig,
    transport: DeepSeekTransport | None = None,
) -> DraftResponse:
    if not search_result.found or not search_result.passages:
        raise DeepSeekDraftError("No PDF evidence is available for LLM drafting.")
    if not config.api_key:
        raise DeepSeekDraftError("DEEPSEEK_API_KEY is not configured.")

    evidence_map = {
        f"evidence-{index}": passage
        for index, passage in enumerate(search_result.passages, start=1)
    }
    payload = _build_payload(email_case, route, evidence_map, config.model)
    request_transport = transport or _post_json
    response = request_transport(
        f"{config.base_url}/chat/completions",
        config.api_key,
        payload,
        config.timeout_seconds,
    )
    reply, source_ids, supporting_quotes = _parse_response(response)
    _check_grounded_reply(
        reply,
        source_ids,
        supporting_quotes,
        evidence_map,
        email_case,
    )

    used_evidence = [
        evidence_map[evidence_id]
        for evidence_id in source_ids
    ]
    return DraftResponse(
        status="drafted",
        reply=reply,
        evidence=used_evidence,
        internal_notes=[
            f"Dynamic draft created by {route.selected_subagent} using {config.model}.",
            f"Grounded in {', '.join(source_ids)} from the FAQ PDF.",
            "LLM draft grounding checks passed before the refund guardrail.",
        ],
        provider="deepseek",
        model=config.model,
    )


def _fallback_draft(
    email_case: dict[str, Any],
    route: SubagentRouteResult,
    search_result: PDFSearchResult,
    reason: str,
) -> DraftResponse:
    draft = draft_grounded_response(email_case, route, search_result)
    return replace(
        draft,
        provider="deterministic",
        fallback_reason=reason,
        internal_notes=[
            *draft.internal_notes,
            f"Dynamic drafting fallback reason: {reason}",
        ],
    )


def _build_payload(
    email_case: dict[str, Any],
    route: SubagentRouteResult,
    evidence_map: dict[str, EvidencePassage],
    model: str,
) -> dict[str, Any]:
    evidence_context = "\n\n".join(
        (
            f"[{evidence_id}] Page {passage.page_number}, "
            f"section: {passage.section}\n{passage.text}"
        )
        for evidence_id, passage in evidence_map.items()
    )
    customer_name = str(email_case.get("customer_name") or "Customer").strip()
    subject = str(email_case.get("subject") or "").strip()
    body = str(email_case.get("body") or "").strip()

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write concise customer-support email replies. Use only "
                    "the customer email and supplied FAQ evidence. Do not decide "
                    "policy, invent eligibility, dates, fees, timelines, actions, "
                    "or promises. Preserve all conditions in the evidence. Write "
                    "at most 150 words with a greeting, direct answer, and useful "
                    "next step. Return only valid JSON with this shape: "
                    '{"reply":"customer-facing reply",'
                    '"source_evidence_ids":["evidence-1"],'
                    '"supporting_quotes":["exact source sentence"]}. '
                    "Every quote must be copied exactly from cited evidence."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Customer name: {customer_name}\n"
                    f"Category: {route.category}\n"
                    f"Assigned subagent: {route.selected_subagent}\n"
                    f"Subject: {subject}\n"
                    f"Email: {body}\n\n"
                    f"FAQ evidence:\n{evidence_context}"
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0.3,
        "max_tokens": 700,
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
            "User-Agent": "Part1-Support-Email-Agent/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise DeepSeekDraftError(
            f"DeepSeek request failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise DeepSeekDraftError("DeepSeek could not be reached.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeepSeekDraftError(
            "DeepSeek returned an invalid JSON response."
        ) from exc


def _parse_response(
    response: dict[str, Any],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekDraftError(
            "DeepSeek response is missing draft content."
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekDraftError("DeepSeek returned empty draft content.")

    cleaned_content = content.strip()
    if cleaned_content.startswith("```"):
        cleaned_content = re.sub(r"^```(?:json)?\s*", "", cleaned_content)
        cleaned_content = re.sub(r"\s*```$", "", cleaned_content)
    try:
        parsed = json.loads(cleaned_content)
    except json.JSONDecodeError as exc:
        raise DeepSeekDraftError("DeepSeek draft content is not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise DeepSeekDraftError("DeepSeek draft JSON must be an object.")
    reply = parsed.get("reply")
    source_ids = parsed.get("source_evidence_ids")
    quotes = parsed.get("supporting_quotes")
    if not isinstance(reply, str) or not reply.strip():
        raise DeepSeekDraftError("DeepSeek draft JSON is missing the reply.")
    if not isinstance(source_ids, list) or not source_ids or not all(
        isinstance(source_id, str) and source_id.strip()
        for source_id in source_ids
    ):
        raise DeepSeekDraftError(
            "DeepSeek draft JSON has invalid evidence citations."
        )
    if not isinstance(quotes, list) or not quotes or not all(
        isinstance(quote, str) and quote.strip() for quote in quotes
    ):
        raise DeepSeekDraftError(
            "DeepSeek draft JSON has invalid supporting quotes."
        )

    return (
        re.sub(r"\s+", " ", reply).strip(),
        tuple(dict.fromkeys(source_ids)),
        tuple(dict.fromkeys(quote.strip() for quote in quotes)),
    )


def _check_grounded_reply(
    reply: str,
    source_ids: tuple[str, ...],
    supporting_quotes: tuple[str, ...],
    evidence_map: dict[str, EvidencePassage],
    email_case: dict[str, Any],
) -> None:
    if len(reply.split()) > MAX_DRAFT_WORDS:
        raise DeepSeekDraftError(
            f"DeepSeek draft exceeds the {MAX_DRAFT_WORDS}-word limit."
        )
    if any(source_id not in evidence_map for source_id in source_ids):
        raise DeepSeekDraftError("DeepSeek draft cites unknown PDF evidence.")

    cited_text = " ".join(evidence_map[source_id].text for source_id in source_ids)
    normalized_cited_text = _normalize(cited_text)
    for quote in supporting_quotes:
        if _normalize(quote) not in normalized_cited_text:
            raise DeepSeekDraftError(
                "DeepSeek supplied a quote that is absent from cited PDF evidence."
            )

    allowed_context = " ".join(
        [
            cited_text,
            str(email_case.get("customer_name") or ""),
            str(email_case.get("subject") or ""),
            str(email_case.get("body") or ""),
        ]
    )
    unsupported_numbers = _number_tokens(reply) - _number_tokens(allowed_context)
    if unsupported_numbers:
        raise DeepSeekDraftError(
            "DeepSeek draft contains a number absent from the email and PDF evidence."
        )

    reply_terms = _content_terms(reply)
    allowed_terms = _content_terms(allowed_context)
    if reply_terms:
        coverage = len(reply_terms & allowed_terms) / len(reply_terms)
        if coverage < MIN_GROUNDING_COVERAGE:
            raise DeepSeekDraftError(
                "DeepSeek draft is not sufficiently grounded in the email and PDF evidence."
            )

    unsupported_promises = (
        _tokens(reply) & UNSUPPORTED_PROMISE_TERMS
    ) - _tokens(allowed_context)
    if unsupported_promises:
        raise DeepSeekDraftError(
            "DeepSeek draft contains an unsupported promise or absolute claim."
        )


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _content_terms(value: str) -> set[str]:
    return _tokens(value) - CONTENT_STOP_WORDS


def _number_tokens(value: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:[.,]\d+)?\b", value.casefold()))


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))
