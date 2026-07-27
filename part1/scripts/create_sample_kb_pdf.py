from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "nimbus_support_knowledge_base.pdf"


def add_section(story, title, items, styles):
    story.append(Paragraph(title, styles["SectionTitle"]))
    for heading, body in items:
        story.append(Paragraph(f"<b>{heading}</b>", styles["Question"]))
        story.append(Paragraph(body, styles["Body"]))
        story.append(Spacer(1, 0.08 * inch))
    story.append(Spacer(1, 0.12 * inch))


def build_pdf():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.58 * inch,
        title="NimbusShop Help Center FAQ",
        author="NimbusShop Support Operations",
        subject="Sample PDF FAQ for customer support questions",
    )

    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=8,
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=10,
        ),
        "SectionTitle": ParagraphStyle(
            "SectionTitle",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=15,
            textColor=colors.HexColor("#0F766E"),
            spaceBefore=6,
            spaceAfter=5,
        ),
        "Question": ParagraphStyle(
            "Question",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.2,
            leading=12,
            textColor=colors.HexColor("#111827"),
            spaceAfter=2,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=11.5,
            textColor=colors.HexColor("#374151"),
            spaceAfter=3,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=10,
            textColor=colors.HexColor("#4B5563"),
        ),
    }

    story = [
        Paragraph("NimbusShop Help Center FAQ", styles["Title"]),
        Paragraph(
            "Common customer questions about orders, refunds, billing, account access, app troubleshooting, and privacy.",
            styles["Subtitle"],
        ),
    ]

    summary_data = [
        ["Category", "Use when the customer asks about"],
        ["Billing", "Invoices, duplicate charges, failed payments, payment method updates, tax receipts"],
        ["Technical", "Login issues, app crashes, sync problems, order tracking bugs, checkout errors"],
        ["Refunds", "Return eligibility, subscription cancellation, refund timeline, non-refundable items"],
        ["Shipping", "Delivery times, tracking updates, missing packages, damaged packages"],
        ["Account", "Profile updates, password reset, email address changes, account privacy"],
    ]
    table = Table(summary_data, colWidths=[1.28 * inch, 5.08 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0F2F1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([table, Spacer(1, 0.14 * inch)])

    add_section(
        story,
        "1. Refund And Return Policy",
        [
            (
                "What is the standard refund window?",
                "Physical product orders are eligible for a refund within 30 calendar days of delivery if the item is unused, "
                "undamaged, and returned with the original packaging. Refunds are issued to the original payment method.",
            ),
            (
                "How long does a refund take?",
                "After the returned item is received and inspected, NimbusShop approves or rejects the refund within 3 business days. "
                "Approved refunds usually appear on the customer's statement within 5 to 10 business days, depending on the bank.",
            ),
            (
                "Which items are not refundable?",
                "Gift cards, final-sale products, downloadable digital goods, and items damaged after delivery are not refundable unless "
                "local consumer law requires otherwise.",
            ),
            (
                "How do subscription cancellations work?",
                "A customer may cancel a NimbusPlus subscription at any time. Cancellation stops the next renewal. NimbusShop does not "
                "refund the unused portion of the current billing month unless the customer was charged twice or the service was unavailable "
                "for more than 24 consecutive hours.",
            ),
        ],
        styles,
    )

    add_section(
        story,
        "2. Billing FAQ",
        [
            (
                "The customer says they were charged twice.",
                "Ask for the order number, last four digits of the payment card, charge dates, and charge amounts. If two settled charges "
                "exist for one order, refund the duplicate charge in full. Pending authorizations are not settled charges and normally drop "
                "off within 3 to 7 business days.",
            ),
            (
                "The customer wants an invoice or receipt.",
                "Invoices and receipts are available from Account > Orders > View receipt. If the customer cannot access the account, verify "
                "the order email address and send the receipt to that same email only.",
            ),
            (
                "The customer's payment failed.",
                "Suggest checking card expiration, billing address, bank restrictions, and available funds. Do not ask the customer to send "
                "full card numbers, passwords, or one-time passcodes.",
            ),
        ],
        styles,
    )

    add_section(
        story,
        "3. Account And App FAQ",
        [
            (
                "The customer cannot log in.",
                "Customers should reset their password, confirm they are using the correct account email address, update the app, and try a private browser window. "
                "If the problem continues, they should contact support with their device, browser, app version, and the error message shown.",
            ),
            (
                "The app crashes or freezes.",
                "Customers should update the app, restart the device, clear cache, and retry on a stable network. If the crash continues, they should share "
                "the device model, OS version, app version, and the exact action that caused the crash.",
            ),
            (
                "Order tracking does not update.",
                "Tracking can take up to 24 hours to refresh after a carrier scan. If tracking has not changed for 72 hours, create a carrier investigation "
                "ticket and tell the customer they will receive an update within 2 business days.",
            ),
        ],
        styles,
    )

    add_section(
        story,
        "4. Shipping FAQ",
        [
            (
                "How long does delivery take?",
                "Standard delivery usually takes 3 to 6 business days after the order ships. Express delivery usually takes 1 to 2 business days after shipment. "
                "Delivery times may vary during public holidays, severe weather, or carrier delays.",
            ),
            (
                "What should customers do if a package is missing?",
                "Customers should first check the tracking page, delivery photo, mailbox, reception desk, and nearby safe places. If the package is still missing "
                "24 hours after the carrier marks it delivered, customers should contact support with the order number.",
            ),
            (
                "What if an item arrives damaged?",
                "Customers should contact support within 7 calendar days of delivery and include the order number, a photo of the damaged item, a photo of the "
                "shipping box, and a short description of the issue.",
            ),
        ],
        styles,
    )

    add_section(
        story,
        "5. Privacy And Security FAQ",
        [
            (
                "What information should customers never send?",
                "Customers should never send full payment card numbers, passwords, security codes, or one-time passcodes through email or chat. NimbusShop support "
                "will only ask for safe verification details such as order number, account email address, and the last four digits of a payment card.",
            ),
            (
                "What should customers do if they suspect unauthorized account access?",
                "Customers should reset their password immediately, sign out of all active sessions from Account > Security, and contact support if they notice "
                "unknown orders, changed profile details, or unfamiliar payment methods.",
            ),
            (
                "How can customers request deletion of their account?",
                "Customers can request account deletion from Account > Privacy > Delete account. Deletion requests are reviewed within 10 business days. Some order, "
                "payment, and tax records may be retained where required by law.",
            ),
        ],
        styles,
    )

    story.append(Spacer(1, 0.06 * inch))
    story.append(
        Paragraph(
            "Document version: 1.0 | Intended use: sample customer FAQ for NimbusShop support.",
            styles["Small"],
        )
    )

    doc.build(story)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
