from dataclasses import dataclass, replace
import json
import re
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from web_summary_agent.chunker import ContentChunk
from web_summary_agent.config import LLMConfig, load_llm_config
from web_summary_agent.summarizer import (
    SummaryError,
    SummaryGuardrailResult,
    SummaryResult,
    summarize_chunks,
)


MAX_CONTEXT_CHUNKS = 30
MAX_CONTEXT_CHARACTERS = 80_000
GROUNDING_COVERAGE_THRESHOLD = 0.5
CONTENT_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "by",
    "for",
    "from",
    "has",
    "have",
    "he",
    "her",
    "his",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "was",
    "were",
    "who",
    "with",
}


class DeepSeekError(RuntimeError):
    """Raised when DeepSeek cannot return a valid grounded summary."""


class GeminiError(RuntimeError):
    """Raised when Gemini cannot return a valid grounded summary."""


@dataclass(frozen=True)
class GroundedPoint:
    text: str
    source_chunk_ids: tuple[str, ...]


DeepSeekTransport = Callable[[str, str, dict[str, Any], float], dict[str, Any]]
GeminiTransport = Callable[[str, str, dict[str, Any], float], dict[str, Any]]


def summarize_with_configured_provider(
    chunks: Iterable[ContentChunk],
    *,
    focus: str,
    max_words: int,
) -> SummaryResult:
    chunk_list = tuple(chunks)
    config = load_llm_config()
    if config.provider == "deterministic":
        return summarize_chunks(chunk_list, focus=focus, max_words=max_words)
    if not config.api_key:
        key_name = "GEMINI_API_KEY" if config.provider == "gemini" else "DEEPSEEK_API_KEY"
        return _deterministic_fallback(
            chunk_list,
            focus,
            max_words,
            f"{key_name} is not configured.",
        )

    try:
        if config.provider == "gemini":
            return summarize_with_gemini(
                chunk_list,
                focus=focus,
                max_words=max_words,
                config=config,
            )
        return summarize_with_deepseek(
            chunk_list,
            focus=focus,
            max_words=max_words,
            config=config,
        )
    except (DeepSeekError, GeminiError, SummaryError, ValueError) as exc:
        return _deterministic_fallback(
            chunk_list,
            focus,
            max_words,
            str(exc),
        )


def summarize_with_deepseek(
    chunks: Iterable[ContentChunk],
    *,
    focus: str,
    max_words: int,
    config: LLMConfig,
    transport: DeepSeekTransport | None = None,
) -> SummaryResult:
    chunk_list = tuple(chunks)
    if not chunk_list:
        raise SummaryError("No cleaned webpage content is available to summarize.")
    if max_words <= 0:
        raise ValueError("max_words must be greater than zero.")
    if not config.api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY is not configured.")

    context_chunks = _select_context_chunks(chunk_list, focus)
    payload = _build_payload(context_chunks, focus, max_words, config.model)
    request_transport = transport or _post_json
    response = request_transport(
        f"{config.base_url}/chat/completions",
        config.api_key,
        payload,
        config.timeout_seconds,
    )
    points = _parse_grounded_points(response)
    guardrail = check_llm_summary_guardrail(points, context_chunks, max_words)
    if guardrail.status != "passed":
        raise SummaryError(guardrail.reason)

    point_texts = tuple(point.text for point in points)
    source_chunk_ids = tuple(
        dict.fromkeys(
            chunk_id
            for point in points
            for chunk_id in point.source_chunk_ids
        )
    )
    return SummaryResult(
        summary="\n".join(f"- {point}" for point in point_texts),
        points=point_texts,
        word_count=_word_count(point_texts),
        max_words=max_words,
        source_chunk_ids=source_chunk_ids,
        guardrail=guardrail,
        provider="deepseek",
        model=config.model,
    )


def summarize_with_gemini(
    chunks: Iterable[ContentChunk],
    *,
    focus: str,
    max_words: int,
    config: LLMConfig,
    transport: GeminiTransport | None = None,
) -> SummaryResult:
    chunk_list = tuple(chunks)
    if not chunk_list:
        raise SummaryError("No cleaned webpage content is available to summarize.")
    if max_words <= 0:
        raise ValueError("max_words must be greater than zero.")
    if not config.api_key:
        raise GeminiError("GEMINI_API_KEY is not configured.")

    context_chunks = _select_context_chunks(chunk_list, focus)
    payload = _build_gemini_payload(context_chunks, focus, max_words)
    request_transport = transport or _post_json_with_gemini_key
    response = request_transport(
        f"{config.base_url}/models/{config.model}:generateContent",
        config.api_key,
        payload,
        config.timeout_seconds,
    )
    points = _parse_grounded_points(response, provider="gemini")
    guardrail = check_llm_summary_guardrail(points, context_chunks, max_words)
    if guardrail.status != "passed":
        raise SummaryError(guardrail.reason)

    point_texts = tuple(point.text for point in points)
    source_chunk_ids = tuple(
        dict.fromkeys(
            chunk_id
            for point in points
            for chunk_id in point.source_chunk_ids
        )
    )
    return SummaryResult(
        summary="\n".join(f"- {point}" for point in point_texts),
        points=point_texts,
        word_count=_word_count(point_texts),
        max_words=max_words,
        source_chunk_ids=source_chunk_ids,
        guardrail=guardrail,
        provider="gemini",
        model=config.model,
    )


def check_llm_summary_guardrail(
    points: Iterable[GroundedPoint],
    chunks: Iterable[ContentChunk],
    max_words: int,
) -> SummaryGuardrailResult:
    point_list = tuple(points)
    chunk_map = {chunk.chunk_id: chunk.text for chunk in chunks}
    if not point_list:
        return SummaryGuardrailResult("blocked", "LLM summary has no useful points.")
    if _word_count(point.text for point in point_list) > max_words:
        return SummaryGuardrailResult(
            "blocked",
            f"LLM summary exceeds the {max_words}-word limit.",
        )

    normalized_points = [_normalize(point.text) for point in point_list]
    if len(normalized_points) != len(set(normalized_points)):
        return SummaryGuardrailResult(
            "blocked",
            "LLM summary contains duplicate points.",
        )

    for point in point_list:
        if not point.source_chunk_ids:
            return SummaryGuardrailResult(
                "blocked",
                "An LLM summary point has no source chunk citation.",
            )
        if any(chunk_id not in chunk_map for chunk_id in point.source_chunk_ids):
            return SummaryGuardrailResult(
                "blocked",
                "An LLM summary point cites an unknown source chunk.",
            )

        cited_source = " ".join(chunk_map[chunk_id] for chunk_id in point.source_chunk_ids)
        point_terms = _content_terms(point.text)
        source_terms = _content_terms(cited_source)
        if point_terms:
            coverage = len(point_terms & source_terms) / len(point_terms)
            if coverage < GROUNDING_COVERAGE_THRESHOLD:
                return SummaryGuardrailResult(
                    "blocked",
                    "An LLM summary point is not sufficiently grounded in its cited chunks.",
                )

        source_tokens = _tokens(cited_source)
        unsupported_numbers = {
            token for token in _tokens(point.text) if token.isdigit()
        } - source_tokens
        if unsupported_numbers:
            return SummaryGuardrailResult(
                "blocked",
                "An LLM summary point contains a number absent from its cited chunks.",
            )

    return SummaryGuardrailResult(
        "passed",
        "LLM summary is concise, deduplicated, and linked to grounded source chunks.",
    )


def _deterministic_fallback(
    chunks: tuple[ContentChunk, ...],
    focus: str,
    max_words: int,
    reason: str,
) -> SummaryResult:
    result = summarize_chunks(chunks, focus=focus, max_words=max_words)
    return replace(
        result,
        provider="deterministic",
        fallback_reason=reason,
    )


def _select_context_chunks(
    chunks: tuple[ContentChunk, ...],
    focus: str,
) -> tuple[ContentChunk, ...]:
    focus_terms = _content_terms(focus)
    ranked = sorted(
        enumerate(chunks),
        key=lambda item: (
            -len(_content_terms(item[1].text) & focus_terms),
            item[0],
        ),
    )
    selected: list[tuple[int, ContentChunk]] = []
    character_count = 0
    for source_order, chunk in ranked:
        if len(selected) >= MAX_CONTEXT_CHUNKS:
            break
        if selected and character_count + len(chunk.text) > MAX_CONTEXT_CHARACTERS:
            continue
        selected.append((source_order, chunk))
        character_count += len(chunk.text)

    selected.sort(key=lambda item: item[0])
    return tuple(chunk for _, chunk in selected)


def _build_payload(
    chunks: tuple[ContentChunk, ...],
    focus: str,
    max_words: int,
    model: str,
) -> dict[str, Any]:
    system_prompt, user_prompt = _build_grounded_summary_prompt(chunks, focus, max_words)
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0.3,
        "max_tokens": max(500, max_words * 5),
        "stream": False,
    }


def _build_gemini_payload(
    chunks: tuple[ContentChunk, ...],
    focus: str,
    max_words: int,
) -> dict[str, Any]:
    system_prompt, user_prompt = _build_grounded_summary_prompt(chunks, focus, max_words)
    return {
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": max(500, max_words * 5),
            "responseMimeType": "application/json",
        },
    }


def _build_grounded_summary_prompt(
    chunks: tuple[ContentChunk, ...],
    focus: str,
    max_words: int,
) -> tuple[str, str]:
    source_context = "\n\n".join(
        f"[{chunk.chunk_id}]\n{chunk.text}" for chunk in chunks
    )
    system_prompt = (
        "You are a grounded webpage summarizer. Use only the supplied "
        "source chunks. Follow the user's requested scope, item count, "
        "and fields whenever the sources support them. Never add outside "
        "facts. Return only valid JSON with this shape: "
        '{"points":[{"text":"summary point",'
        '"source_chunk_ids":["chunk-001"]}]}. '
        "Every point must cite the source chunks that support it."
    )
    user_prompt = (
        f"Summary focus:\n{focus}\n\n"
        f"Maximum total summary length: {max_words} words.\n"
        "Keep points concise and non-duplicative.\n\n"
        f"Source chunks:\n{source_context}"
    )
    return system_prompt, user_prompt


def _post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Part2-Web-Summary-Agent/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise DeepSeekError(
            f"DeepSeek request failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise DeepSeekError("DeepSeek could not be reached.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeepSeekError("DeepSeek returned an invalid JSON response.") from exc


def _post_json_with_gemini_key(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Part2-Web-Summary-Agent/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GeminiError(f"Gemini request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise GeminiError("Gemini could not be reached.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiError("Gemini returned an invalid JSON response.") from exc


def _parse_grounded_points(
    response: dict[str, Any],
    *,
    provider: str = "deepseek",
) -> tuple[GroundedPoint, ...]:
    error_class: type[RuntimeError] = GeminiError if provider == "gemini" else DeepSeekError
    try:
        if provider == "gemini":
            parts = response["candidates"][0]["content"]["parts"]
            content = "".join(
                part.get("text", "") for part in parts if isinstance(part, dict)
            )
        else:
            content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise error_class(f"{provider.title()} response is missing summary content.") from exc
    if not isinstance(content, str) or not content.strip():
        raise error_class(f"{provider.title()} returned empty summary content.")

    cleaned_content = content.strip()
    if cleaned_content.startswith("```"):
        cleaned_content = re.sub(r"^```(?:json)?\s*", "", cleaned_content)
        cleaned_content = re.sub(r"\s*```$", "", cleaned_content)
    try:
        parsed = json.loads(cleaned_content)
    except json.JSONDecodeError as exc:
        raise error_class(
            f"{provider.title()} summary content is not valid JSON."
        ) from exc

    raw_points = parsed.get("points") if isinstance(parsed, dict) else None
    if not isinstance(raw_points, list) or not raw_points:
        raise error_class(f"{provider.title()} JSON must contain a non-empty points list.")

    points: list[GroundedPoint] = []
    for raw_point in raw_points:
        if not isinstance(raw_point, dict):
            raise error_class(f"Each {provider.title()} summary point must be an object.")
        text = raw_point.get("text")
        source_ids = raw_point.get("source_chunk_ids")
        if not isinstance(text, str) or not text.strip():
            raise error_class(f"A {provider.title()} summary point is missing text.")
        if not isinstance(source_ids, list) or not all(
            isinstance(chunk_id, str) and chunk_id.strip()
            for chunk_id in source_ids
        ):
            raise error_class(
                f"A {provider.title()} summary point has invalid source chunk citations."
            )
        points.append(
            GroundedPoint(
                text=re.sub(r"\s+", " ", text).strip(),
                source_chunk_ids=tuple(dict.fromkeys(source_ids)),
            )
        )
    return tuple(points)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _content_terms(value: str) -> set[str]:
    return _tokens(value) - CONTENT_STOP_WORDS


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _word_count(values: Iterable[str]) -> int:
    return sum(len(value.split()) for value in values)
