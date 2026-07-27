from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "data" / "nimbus_travel_expense_policy.json"
OUTPUT_PATH = ROOT / "data" / "nimbus_travel_expense_policy.pdf"

NAVY = colors.HexColor("#18324A")
TEAL = colors.HexColor("#008F87")
INK = colors.HexColor("#26333D")
MUTED = colors.HexColor("#5E6C76")
LINE = colors.HexColor("#D8E0E5")
PALE_TEAL = colors.HexColor("#E8F6F4")
PALE_BLUE = colors.HexColor("#EEF3F7")


def load_policy(path: Path = SOURCE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_pdf(
    policy: dict[str, Any],
    output_path: Path = OUTPUT_PATH,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=policy["title"],
        author="Nimbus Finance Operations",
        subject="Business travel and expense reimbursement policy",
    )
    styles = _build_styles()
    story: list[Any] = []

    story.extend(_title_block(policy, styles))
    for section in policy["sections"]:
        if section["number"] == 5:
            story.append(PageBreak())
            story.extend(_continuation_heading(policy, styles))
        story.append(_section_block(section, styles))

    document.build(
        story,
        onFirstPage=lambda canvas, doc: _draw_page_frame(canvas, doc, policy),
        onLaterPages=lambda canvas, doc: _draw_page_frame(canvas, doc, policy),
    )
    return output_path


def _build_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PolicyTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "subtitle": ParagraphStyle(
            "PolicySubtitle",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=MUTED,
            spaceAfter=4 * mm,
        ),
        "section": ParagraphStyle(
            "PolicySection",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=NAVY,
            spaceBefore=2.5 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "PolicyBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.6,
            leading=11.2,
            textColor=INK,
            spaceAfter=1.5 * mm,
        ),
        "bullet": ParagraphStyle(
            "PolicyBullet",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.4,
            leading=10.8,
            textColor=INK,
            leftIndent=5 * mm,
            firstLineIndent=-3 * mm,
            bulletIndent=1.5 * mm,
            spaceAfter=1.1 * mm,
        ),
        "meta_label": ParagraphStyle(
            "MetaLabel",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=MUTED,
        ),
        "meta_value": ParagraphStyle(
            "MetaValue",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=NAVY,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
        ),
        "principle": ParagraphStyle(
            "Principle",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=NAVY,
        ),
        "continued": ParagraphStyle(
            "Continued",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=TEAL,
            spaceAfter=3 * mm,
        ),
    }


def _title_block(
    policy: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    metadata = [
        [
            Paragraph("POLICY ID", styles["meta_label"]),
            Paragraph("EFFECTIVE", styles["meta_label"]),
            Paragraph("OWNER", styles["meta_label"]),
            Paragraph("VERSION", styles["meta_label"]),
        ],
        [
            Paragraph(policy["policy_id"], styles["meta_value"]),
            Paragraph(policy["effective_date"], styles["meta_value"]),
            Paragraph(policy["owner"], styles["meta_value"]),
            Paragraph(policy["version"], styles["meta_value"]),
        ],
    ]
    metadata_table = Table(
        metadata,
        colWidths=[43 * mm, 36 * mm, 53 * mm, 24 * mm],
        rowHeights=[5 * mm, 7 * mm],
    )
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
            ]
        )
    )
    principle_table = Table(
        [[Paragraph(f"GUIDING PRINCIPLE  {policy['principle']}", styles["principle"])]],
        colWidths=[156 * mm],
    )
    principle_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_TEAL),
                ("BOX", (0, 0), (-1, -1), 0.6, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]
        )
    )
    return [
        Paragraph(policy["title"], styles["title"]),
        Paragraph(policy["subtitle"], styles["subtitle"]),
        metadata_table,
        Spacer(1, 3 * mm),
        principle_table,
        Spacer(1, 2 * mm),
    ]


def _continuation_heading(
    policy: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(policy["title"], styles["continued"]),
        Paragraph(
            "Operational rules, claims, and exceptions",
            styles["subtitle"],
        ),
    ]


def _section_block(
    section: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> KeepTogether:
    elements: list[Any] = [
        Paragraph(
            f"{section['number']}. {section['title']}",
            styles["section"],
        )
    ]
    for paragraph in section.get("paragraphs", []):
        elements.append(Paragraph(paragraph, styles["body"]))
    table_data = section.get("table")
    if table_data:
        elements.append(_policy_table(table_data, styles))
        elements.append(Spacer(1, 1.2 * mm))
    for bullet in section.get("bullets", []):
        elements.append(
            Paragraph(
                f"- {bullet}",
                styles["bullet"],
            )
        )
    return KeepTogether(elements)


def _policy_table(
    table_data: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows = [
        [Paragraph(value, styles["table_header"]) for value in table_data["headers"]]
    ]
    rows.extend(
        [Paragraph(value, styles["body"]) for value in row]
        for row in table_data["rows"]
    )
    table = Table(rows, colWidths=[102 * mm, 54 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ]
        )
    )
    return table


def _draw_page_frame(canvas: Any, document: Any, policy: dict[str, Any]) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 10 * mm, width, 10 * mm, stroke=0, fill=1)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.white)
    canvas.drawString(18 * mm, height - 6.5 * mm, "NIMBUS")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(
        width - 18 * mm,
        height - 6.5 * mm,
        "FINANCE OPERATIONS",
    )

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        18 * mm,
        8.5 * mm,
        f"{policy['policy_id']}  |  Internal policy",
    )
    canvas.drawRightString(
        width - 18 * mm,
        8.5 * mm,
        f"Page {document.page}",
    )
    canvas.restoreState()


if __name__ == "__main__":
    result = build_pdf(load_policy())
    print(result)
