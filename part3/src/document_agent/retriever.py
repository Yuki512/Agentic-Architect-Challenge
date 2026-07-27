from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from rank_bm25 import BM25Okapi

from document_agent.document_loader import DocumentSection, LoadedDocument


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "be",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "policy",
    "please",
    "should",
    "tell",
    "the",
    "to",
    "travel",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "would",
}
QUERY_EXPANSIONS = {
    "car": {"vehicle", "mileage"},
    "deadline": {"claim", "submit"},
    "food": {"meal"},
    "hotel": {"accommodation", "room"},
    "lodging": {"accommodation", "room"},
    "maximum": {"limit", "maximum"},
    "receipt": {"receipt", "claim"},
}


@dataclass(frozen=True)
class RetrievalMatch:
    section: DocumentSection
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    matches: tuple[RetrievalMatch, ...]

    @property
    def has_relevant_evidence(self) -> bool:
        return bool(self.matches)


class DocumentRetriever:
    def __init__(self, document: LoadedDocument) -> None:
        if not document.sections:
            raise ValueError("Document must contain at least one section.")
        self.document = document
        self._section_tokens = tuple(
            _tokenize(f"{section.title} {section.text}")
            for section in document.sections
        )
        self._section_term_sets = tuple(
            frozenset(tokens) for tokens in self._section_tokens
        )
        self._index = BM25Okapi(self._section_tokens)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
    ) -> RetrievalResult:
        normalized_query = re.sub(r"\s+", " ", query).strip()
        if not normalized_query:
            raise ValueError("Retrieval query cannot be empty.")
        if not 1 <= top_k <= len(self.document.sections):
            raise ValueError(
                f"top_k must be between 1 and {len(self.document.sections)}."
            )

        query_tokens = _expand_query(_tokenize(normalized_query))
        if not query_tokens:
            return RetrievalResult(query=normalized_query, matches=())

        scores = self._index.get_scores(query_tokens)
        ranked = sorted(
            enumerate(scores),
            key=lambda item: (-float(item[1]), item[0]),
        )
        matches = tuple(
            RetrievalMatch(
                section=self.document.sections[index],
                score=round(float(score), 4),
                matched_terms=tuple(
                    sorted(
                        set(query_tokens)
                        & self._section_term_sets[index]
                    )
                ),
            )
            for index, score in ranked[:top_k]
            if float(score) > 0
        )
        return RetrievalResult(query=normalized_query, matches=matches)


def _tokenize(value: str) -> list[str]:
    return [
        normalized
        for token in TOKEN_PATTERN.findall(value.casefold())
        if (normalized := _normalize_token(token))
        and normalized not in STOP_WORDS
    ]


def _normalize_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _expand_query(tokens: Iterable[str]) -> list[str]:
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        expanded.extend(sorted(QUERY_EXPANSIONS.get(token, ())))
    return list(dict.fromkeys(expanded))
