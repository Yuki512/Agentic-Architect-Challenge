from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from support_agent.critical_detector import CriticalCheckResult


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KB_PATH = ROOT / "docs" / "nimbus_support_knowledge_base.pdf"

STOP_WORDS = {
    "a",
    "about",
    "after",
    "am",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "get",
    "hi",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "was",
    "what",
    "with",
    "you",
}


@dataclass(frozen=True)
class EvidencePassage:
    source_path: str
    page_number: int
    section: str
    text: str
    score: int


@dataclass(frozen=True)
class PDFSearchResult:
    query: str
    source_path: str
    found: bool
    passages: list[EvidencePassage]


@dataclass(frozen=True)
class HumanHandoffTicket:
    ticket_id: str
    case_id: str
    priority: str
    matched_triggers: list[str]
    summary: str
    customer_context: dict[str, Any]


@dataclass(frozen=True)
class AuditLogEntry:
    case_id: str
    event_type: str
    status: str
    details: dict[str, Any]


def pdf_search_tool(
    query: str,
    pdf_path: Path | str = DEFAULT_KB_PATH,
    category: str | None = None,
    limit: int = 3,
) -> PDFSearchResult:
    """Search the FAQ PDF and return the most relevant evidence passages."""
    pdf_path = Path(pdf_path)
    passages = _extract_pdf_passages(pdf_path)
    query_terms = _tokenize(f"{category or ''} {query}")

    scored_passages = []
    for passage in passages:
        passage_terms = _tokenize(passage.text)
        score = len(query_terms.intersection(passage_terms))
        if category and category.casefold() in passage.section.casefold():
            score += 8
        elif category and category.casefold() in passage.text.casefold():
            score += 2
        if score > 0:
            scored_passages.append(
                EvidencePassage(
                    source_path=str(pdf_path),
                    page_number=passage.page_number,
                    section=passage.section,
                    text=passage.text,
                    score=score,
                )
            )

    top_passages = sorted(scored_passages, key=lambda item: (-item.score, item.page_number))[:limit]
    return PDFSearchResult(
        query=query,
        source_path=str(pdf_path),
        found=bool(top_passages),
        passages=top_passages,
    )


def human_handoff_tool(
    email_case: dict[str, Any],
    critical_result: CriticalCheckResult,
) -> HumanHandoffTicket:
    """Create the handoff payload a real system would send to a human queue."""
    case_id = str(email_case.get("case_id", "UNKNOWN-CASE"))
    subject = str(email_case.get("subject", "No subject"))
    body = str(email_case.get("body", ""))
    summary = _summarize_email(subject, body)

    return HumanHandoffTicket(
        ticket_id=f"HANDOFF-{case_id}",
        case_id=case_id,
        priority="high",
        matched_triggers=critical_result.matched_triggers,
        summary=summary,
        customer_context={
            "customer_id": email_case.get("customer_id"),
            "customer_name": email_case.get("customer_name"),
            "customer_email": email_case.get("customer_email"),
            "contact_count_last_7_days": critical_result.contact_count_last_7_days,
            "metadata": email_case.get("metadata", {}),
        },
    )


def audit_logging_tool(
    case_id: str,
    event_type: str,
    status: str,
    details: dict[str, Any],
) -> AuditLogEntry:
    """Return a structured audit entry for observability."""
    return AuditLogEntry(
        case_id=case_id,
        event_type=event_type,
        status=status,
        details=details,
    )


def serialize_tool_result(value: Any) -> dict[str, Any]:
    return asdict(value)


@dataclass(frozen=True)
class _RawPassage:
    page_number: int
    section: str
    text: str


def _extract_pdf_passages(pdf_path: Path) -> list[_RawPassage]:
    import pdfplumber

    if not pdf_path.exists():
        raise FileNotFoundError(f"Knowledge base PDF not found: {pdf_path}")

    passages: list[_RawPassage] = []
    current: list[str] = []
    current_page = 1
    current_section = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for line in lines:
                section_match = re.match(r"^\d+\.\s+(.+)", line)
                starts_new_section = bool(section_match)
                starts_new_question = line.endswith("?")

                if starts_new_section:
                    if current:
                        passages.append(
                            _RawPassage(
                                page_number=current_page,
                                section=current_section,
                                text=" ".join(current),
                            )
                        )
                    current = [line]
                    current_page = page_index
                    current_section = section_match.group(1)
                    continue

                # Ignore title, summary, and category table text before the first FAQ section.
                if not current_section:
                    continue

                if current and starts_new_question:
                    passages.append(
                        _RawPassage(
                            page_number=current_page,
                            section=current_section,
                            text=" ".join(current),
                        )
                    )
                    current = []
                    current_page = page_index

                current.append(line)

    if current:
        passages.append(
            _RawPassage(
                page_number=current_page,
                section=current_section,
                text=" ".join(current),
            )
        )
    return passages


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+", text.casefold())
    return {word for word in words if len(word) > 2 and word not in STOP_WORDS}


def _summarize_email(subject: str, body: str, max_chars: int = 220) -> str:
    text = re.sub(r"\s+", " ", f"{subject}. {body}").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
