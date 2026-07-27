import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from support_agent.orchestrator import process_email  # noqa: E402


def main() -> None:
    email_cases = json.loads((ROOT / "data" / "mock_emails.json").read_text(encoding="utf-8"))

    for email_case in email_cases:
        result = process_email(email_case)
        print(f"{result.case_id} | {email_case['subject']}")
        print(f"  status: {result.status}")
        print(f"  critical: {result.critical_check.is_critical}")

        if result.handoff_ticket:
            print(f"  handoff_ticket: {result.handoff_ticket.ticket_id}")
            print(f"  triggers: {', '.join(result.handoff_ticket.matched_triggers)}")
        else:
            print(f"  category: {result.classification.primary_category}")
            print(f"  subagent: {result.route.selected_subagent}")
            print(f"  skills: {' -> '.join(result.skill_plan.execution_order)}")
            print(f"  guardrail: {result.guardrail.status}")
            print(f"  response writer: {result.final_draft.provider}")
            if result.final_draft.model:
                print(f"  model: {result.final_draft.model}")
            if result.final_draft.fallback_reason:
                print(f"  fallback: {result.final_draft.fallback_reason}")
            print(f"  reply: {result.final_draft.reply}")
        print(f"  audit_events: {len(result.audit_logs)}")


if __name__ == "__main__":
    main()
