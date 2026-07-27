from dataclasses import dataclass
import re
from typing import Iterable

from web_summary_agent.chunker import ContentChunk
from web_summary_agent.text_utils import split_sentences


MAX_SUMMARY_POINTS = 4
STOP_WORDS = {
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
    "how",
    "in",
    "is",
    "it",
    "its",
    "main",
    "of",
    "on",
    "or",
    "the",
    "their",
    "to",
    "what",
    "which",
    "with",
}
FOCUS_EXPANSIONS = {
    "adaptation": {
        "adaptation",
        "anime",
        "broadcast",
        "episode",
        "game",
        "novel",
        "television",
        "video",
    },
    "application": {
        "application",
        "automation",
        "database",
        "development",
        "education",
        "game",
        "internet",
        "network",
        "scientific",
        "software",
        "web",
    },
    "benefit": {
        "benefit",
        "easy",
        "fast",
        "friendly",
        "learn",
        "open",
        "powerful",
        "readable",
    },
    "publication": {
        "chapters",
        "magazine",
        "published",
        "publisher",
        "serialization",
        "serialized",
        "volumes",
    },
    "story": {
        "boss",
        "character",
        "family",
        "follows",
        "leadership",
        "mafia",
        "plot",
        "reborn",
        "sawada",
        "series",
        "story",
        "tsuna",
        "tsunayoshi",
        "tutor",
        "vongola",
    },
}
RECEPTION_FOCUS_TERMS = {"criticism", "reception", "review", "reviews"}


class SummaryError(RuntimeError):
    """Raised when no grounded concise summary can be created."""


@dataclass(frozen=True)
class SummaryGuardrailResult:
    status: str
    reason: str


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    points: tuple[str, ...]
    word_count: int
    max_words: int
    source_chunk_ids: tuple[str, ...]
    guardrail: SummaryGuardrailResult
    provider: str = "deterministic"
    model: str | None = None
    fallback_reason: str | None = None


@dataclass(frozen=True)
class _Candidate:
    text: str
    chunk_id: str
    source_order: int
    score: float


def summarize_chunks(
    chunks: Iterable[ContentChunk],
    *,
    focus: str,
    max_words: int,
) -> SummaryResult:
    chunk_list = tuple(chunks)
    if not chunk_list:
        raise SummaryError("No cleaned webpage content is available to summarize.")
    if max_words <= 0:
        raise ValueError("max_words must be greater than zero.")

    focus_terms = _focus_terms(focus)
    candidates = _extract_candidates(chunk_list, focus_terms)
    selected = _select_candidates(candidates, max_words)
    if not selected:
        raise SummaryError("No grounded sentence fits the summary word limit.")

    selected.sort(key=lambda candidate: candidate.source_order)
    points = tuple(candidate.text for candidate in selected)
    source_chunk_ids = tuple(dict.fromkeys(candidate.chunk_id for candidate in selected))
    guardrail = check_summary_guardrail(points, chunk_list, max_words)
    if guardrail.status != "passed":
        raise SummaryError(guardrail.reason)

    return SummaryResult(
        summary="\n".join(f"- {point}" for point in points),
        points=points,
        word_count=_word_count(points),
        max_words=max_words,
        source_chunk_ids=source_chunk_ids,
        guardrail=guardrail,
    )


def check_summary_guardrail(
    points: Iterable[str],
    chunks: Iterable[ContentChunk],
    max_words: int,
) -> SummaryGuardrailResult:
    point_list = tuple(point.strip() for point in points if point.strip())
    if not point_list:
        return SummaryGuardrailResult("blocked", "Summary contains no useful points.")
    if _word_count(point_list) > max_words:
        return SummaryGuardrailResult(
            "blocked",
            f"Summary exceeds the {max_words}-word limit.",
        )

    normalized_points = [_normalize_for_match(point) for point in point_list]
    if len(normalized_points) != len(set(normalized_points)):
        return SummaryGuardrailResult(
            "blocked",
            "Summary contains duplicate points.",
        )

    normalized_source = _normalize_for_match(
        " ".join(chunk.text for chunk in chunks)
    )
    unsupported = [
        point
        for point, normalized in zip(point_list, normalized_points)
        if normalized not in normalized_source
    ]
    if unsupported:
        return SummaryGuardrailResult(
            "blocked",
            "Summary contains text that is not supported by the scraped page.",
        )

    return SummaryGuardrailResult(
        "passed",
        "Summary is concise, deduplicated, and grounded in scraped content.",
    )


def _extract_candidates(
    chunks: tuple[ContentChunk, ...],
    focus_terms: set[str],
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    seen: set[str] = set()
    source_order = 0

    for chunk in chunks:
        blocks = [block.strip() for block in chunk.text.split("\n\n") if block.strip()]
        for block in blocks:
            sentences = split_sentences(block)
            for sentence in sentences:
                text = re.sub(r"\s+", " ", sentence).strip()
                normalized = _normalize_for_match(text)
                words = text.split()
                if not normalized or normalized in seen:
                    continue
                if len(words) < 3 or len(words) > 60:
                    continue

                seen.add(normalized)
                candidate_terms = _tokenize(text)
                focus_hits = len(candidate_terms & focus_terms)
                length_score = min(len(words), 24) / 24
                position_score = max(0.0, 1.2 - source_order * 0.025)
                punctuation_score = 0.4 if text[-1:] in ".!?" else 0.0
                score = focus_hits * 3.0 + length_score + position_score + punctuation_score
                if (
                    text.lower().startswith("according to ")
                    and not focus_terms & RECEPTION_FOCUS_TERMS
                ):
                    score -= 8.0
                candidates.append(
                    _Candidate(
                        text=text,
                        chunk_id=chunk.chunk_id,
                        source_order=source_order,
                        score=score,
                    )
                )
                source_order += 1

    return candidates


def _select_candidates(
    candidates: list[_Candidate],
    max_words: int,
) -> list[_Candidate]:
    selected: list[_Candidate] = []
    selected_words = 0

    for candidate in sorted(candidates, key=lambda item: (-item.score, item.source_order)):
        candidate_words = len(candidate.text.split())
        if selected_words + candidate_words > max_words:
            continue
        if any(_is_too_similar(candidate.text, item.text) for item in selected):
            continue

        selected.append(candidate)
        selected_words += candidate_words
        if len(selected) >= MAX_SUMMARY_POINTS:
            break

    return selected


def _focus_terms(focus: str) -> set[str]:
    terms = _tokenize(focus) - STOP_WORDS
    expanded = set(terms)
    for term in terms:
        singular = term[:-1] if term.endswith("s") else term
        if singular in FOCUS_EXPANSIONS:
            expanded.update(FOCUS_EXPANSIONS[singular])
    return expanded


def _is_too_similar(left: str, right: str) -> bool:
    left_terms = _tokenize(left) - STOP_WORDS
    right_terms = _tokenize(right) - STOP_WORDS
    union = left_terms | right_terms
    if not union:
        return True
    if left_terms <= right_terms or right_terms <= left_terms:
        return True
    return len(left_terms & right_terms) / len(union) >= 0.45


def _tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _normalize_for_match(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _word_count(values: Iterable[str]) -> int:
    return sum(len(value.split()) for value in values)
