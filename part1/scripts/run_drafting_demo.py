import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from support_agent.classifier import classify_email  # noqa: E402
from support_agent.critical_detector import check_critical_issue  # noqa: E402
from support_agent.drafting import draft_grounded_response  # noqa: E402
from support_agent.guardrails import apply_refund_guardrail  # noqa: E402
from support_agent.subagents import route_to_subagent  # noqa: E402
from support_agent.tools import human_handoff_tool, pdf_search_tool  # noqa: E402


def main() -> None:
    email_cases = json.loads((ROOT / "data" / "mock_emails.json").read_text(encoding="utf-8"))

    for email_case in email_cases:
        print(f"{email_case['case_id']} | {email_case['subject']}")
        critical_result = check_critical_issue(email_case)

        if critical_result.is_critical:
            ticket = human_handoff_tool(email_case, critical_result)
            print(f"  status: human_review")
            print(f"  ticket: {ticket.ticket_id}")
            print(f"  summary: {ticket.summary}")
            continue

        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        search = pdf_search_tool(
            query=f"{email_case['subject']} {email_case['body']}",
            category=classification.primary_category,
            limit=2,
        )
        draft = draft_grounded_response(email_case, route, search)
        guardrail = apply_refund_guardrail(email_case, classification.primary_category, draft)
        final_draft = guardrail.final_draft

        print(f"  status: {final_draft.status}")
        print(f"  subagent: {route.selected_subagent}")
        print(f"  guardrail: {guardrail.status} - {guardrail.reason}")
        print(f"  reply: {final_draft.reply}")
        print(f"  evidence_count: {len(final_draft.evidence)}")


if __name__ == "__main__":
    main()
