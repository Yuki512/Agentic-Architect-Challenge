import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from support_agent.classifier import classify_email  # noqa: E402
from support_agent.critical_detector import check_critical_issue  # noqa: E402
from support_agent.tools import audit_logging_tool, human_handoff_tool, pdf_search_tool  # noqa: E402


def main() -> None:
    email_cases = json.loads((ROOT / "data" / "mock_emails.json").read_text(encoding="utf-8"))

    for email_case in email_cases:
        print(f"{email_case['case_id']} | {email_case['subject']}")
        critical_result = check_critical_issue(email_case)

        if critical_result.is_critical:
            ticket = human_handoff_tool(email_case, critical_result)
            audit = audit_logging_tool(
                case_id=ticket.case_id,
                event_type="human_handoff_created",
                status="success",
                details={"ticket_id": ticket.ticket_id, "triggers": ticket.matched_triggers},
            )
            print(f"  tool: HumanHandoffTool -> {ticket.ticket_id}")
            print(f"  summary: {ticket.summary}")
            print(f"  audit: {audit.event_type} / {audit.status}")
            continue

        classification = classify_email(email_case)
        search = pdf_search_tool(
            query=f"{email_case['subject']} {email_case['body']}",
            category=classification.primary_category,
            limit=1,
        )
        print(f"  tool: PDFSearchTool -> found={search.found}")
        if search.passages:
            passage = search.passages[0]
            print(f"  evidence page {passage.page_number}, score {passage.score}: {passage.text[:180]}")


if __name__ == "__main__":
    main()

