from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pdfplumber


PART3_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCUMENT_PATH = (
    PART3_ROOT / "data" / "nimbus_travel_expense_policy.pdf"
)
SECTION_HEADING = re.compile(r"^(?P<number>\d{1,2})\.\s+(?P<title>.+)$")
FOOTER_LINE = re.compile(
    r"^NIM-FIN-TRV-2026-01\s+\|\s+Internal policy\s+Page\s+\d+$"
)
PAGE_CHROME = {
    "NIMBUS FINANCE OPERATIONS",
    "Nimbus Travel & Expense Policy",
    "Employee business travel and reimbursement standard",
    "Operational rules, claims, and exceptions",
}


class DocumentLoadError(RuntimeError):
    """Raised when the policy PDF cannot be loaded into grounded sections."""


@dataclass(frozen=True)
class DocumentSection:
    citation_id: str
    page_number: int
    section_number: int
    title: str
    text: str
    word_count: int


@dataclass(frozen=True)
class LoadedDocument:
    title: str
    source_path: Path
    page_count: int
    sections: tuple[DocumentSection, ...]


def load_policy_document(
    path: Path | str = DEFAULT_DOCUMENT_PATH,
) -> LoadedDocument:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise DocumentLoadError(f"Policy PDF was not found: {source_path}")
    if source_path.suffix.lower() != ".pdf":
        raise DocumentLoadError("Policy document must be a PDF file.")

    try:
        with pdfplumber.open(source_path) as pdf:
            sections = tuple(
                section
                for page_number, page in enumerate(pdf.pages, start=1)
                for section in _sections_from_page(
                    page.extract_text() or "",
                    page_number,
                )
            )
            page_count = len(pdf.pages)
    except DocumentLoadError:
        raise
    except Exception as exc:
        raise DocumentLoadError(
            f"Policy PDF could not be read: {source_path.name}"
        ) from exc

    if not sections:
        raise DocumentLoadError("Policy PDF contains no readable sections.")
    section_numbers = [
        section.section_number
        for section in sections
        if section.section_number > 0
    ]
    if len(section_numbers) != len(set(section_numbers)):
        raise DocumentLoadError("Policy PDF contains duplicate section numbers.")

    return LoadedDocument(
        title="Nimbus Travel & Expense Policy",
        source_path=source_path,
        page_count=page_count,
        sections=sections,
    )


def _sections_from_page(
    raw_text: str,
    page_number: int,
) -> tuple[DocumentSection, ...]:
    lines = [
        normalized
        for line in raw_text.splitlines()
        if (normalized := _normalize_line(line))
    ]
    sections: list[DocumentSection] = []
    overview_lines: list[str] = []
    current_number: int | None = None
    current_title = ""
    current_lines: list[str] = []

    def finish_current() -> None:
        if current_number is None:
            return
        sections.append(
            _build_section(
                page_number,
                current_number,
                current_title,
                current_lines,
            )
        )

    for line in lines:
        if _is_page_chrome(line):
            continue
        heading = SECTION_HEADING.match(line)
        if heading:
            if current_number is None and overview_lines:
                sections.append(
                    _build_section(
                        page_number,
                        0,
                        "Policy overview",
                        overview_lines,
                    )
                )
                overview_lines = []
            finish_current()
            current_number = int(heading.group("number"))
            current_title = heading.group("title").strip()
            current_lines = []
            continue
        if current_number is None:
            overview_lines.append(line)
        else:
            current_lines.append(line)

    finish_current()
    if current_number is None and overview_lines:
        sections.append(
            _build_section(
                page_number,
                0,
                "Policy overview",
                overview_lines,
            )
        )
    return tuple(sections)


def _build_section(
    page_number: int,
    section_number: int,
    title: str,
    lines: list[str],
) -> DocumentSection:
    text = "\n".join(lines).strip()
    if not text:
        raise DocumentLoadError(
            f"Section {section_number} on page {page_number} is empty."
        )
    return DocumentSection(
        citation_id=f"P{page_number}:S{section_number}",
        page_number=page_number,
        section_number=section_number,
        title=title,
        text=text,
        word_count=len(re.findall(r"\b[\w$.-]+\b", text)),
    )


def _normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_page_chrome(line: str) -> bool:
    return line in PAGE_CHROME or bool(FOOTER_LINE.match(line))
