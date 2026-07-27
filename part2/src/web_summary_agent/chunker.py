from dataclasses import dataclass
import re
from typing import Iterable

from web_summary_agent.content_cleaner import CleanedPage
from web_summary_agent.text_utils import split_sentences


DEFAULT_MAX_CHUNK_WORDS = 180
DEFAULT_OVERLAP_WORDS = 20
MIN_CHUNK_WORDS = 40
MAX_CHUNK_WORDS = 1_000


@dataclass(frozen=True)
class ContentChunk:
    chunk_id: str
    text: str
    word_count: int


def chunk_cleaned_page(
    page: CleanedPage,
    *,
    max_words: int = DEFAULT_MAX_CHUNK_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> tuple[ContentChunk, ...]:
    _validate_settings(max_words, overlap_words)
    if not page.text.strip():
        return ()

    source_blocks = page.blocks or tuple(
        block.strip() for block in page.text.split("\n\n") if block.strip()
    )
    units = _create_units(source_blocks, max_words)
    chunks = _group_units(units, max_words, overlap_words)

    return tuple(
        ContentChunk(
            chunk_id=f"chunk-{index:03d}",
            text="\n\n".join(chunk_units),
            word_count=_word_count(chunk_units),
        )
        for index, chunk_units in enumerate(chunks, start=1)
    )


def _create_units(
    blocks: Iterable[str],
    max_words: int,
) -> list[str]:
    units: list[str] = []
    for block in blocks:
        normalized_block = re.sub(r"\s+", " ", block).strip()
        if not normalized_block:
            continue

        sentences = split_sentences(normalized_block)
        for sentence in sentences:
            words = sentence.split()
            if not words:
                continue
            if len(words) <= max_words:
                units.append(" ".join(words))
                continue

            for start in range(0, len(words), max_words):
                units.append(" ".join(words[start : start + max_words]))

    return units


def _group_units(
    units: list[str],
    max_words: int,
    overlap_words: int,
) -> list[list[str]]:
    if not units:
        return []

    chunks: list[list[str]] = []
    current: list[str] = []

    for unit in units:
        unit_words = len(unit.split())
        if current and _word_count(current) + unit_words > max_words:
            chunks.append(current)
            current = _overlap_tail(current, overlap_words)

            while current and _word_count(current) + unit_words > max_words:
                current.pop(0)

        current.append(unit)

    if current:
        chunks.append(current)
    return chunks


def _overlap_tail(units: list[str], overlap_words: int) -> list[str]:
    if overlap_words == 0:
        return []

    selected: list[str] = []
    selected_words = 0
    for unit in reversed(units):
        unit_words = len(unit.split())
        if selected_words + unit_words > overlap_words:
            break
        selected.insert(0, unit)
        selected_words += unit_words
    return selected


def _validate_settings(max_words: int, overlap_words: int) -> None:
    if not MIN_CHUNK_WORDS <= max_words <= MAX_CHUNK_WORDS:
        raise ValueError(
            f"max_words must be between {MIN_CHUNK_WORDS} and {MAX_CHUNK_WORDS}."
        )
    if overlap_words < 0:
        raise ValueError("overlap_words must not be negative.")
    if overlap_words >= max_words // 2:
        raise ValueError("overlap_words must be less than half of max_words.")


def _word_count(values: Iterable[str]) -> int:
    return sum(len(value.split()) for value in values)
