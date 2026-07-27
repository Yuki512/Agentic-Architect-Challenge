import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from support_agent.classifier import classify_email  # noqa: E402
from support_agent.critical_detector import check_critical_issue  # noqa: E402
from support_agent.subagents import route_to_subagent  # noqa: E402


def main() -> None:
    mock_email_path = ROOT / "data" / "mock_emails.json"
    email_cases = json.loads(mock_email_path.read_text(encoding="utf-8"))

    for email_case in email_cases:
        critical_result = check_critical_issue(email_case)
        print(f"{email_case['case_id']} | {email_case['subject']}")

        if critical_result.is_critical:
            print("  selected_subagent: HumanHandoff")
            print(f"  triggers: {', '.join(critical_result.matched_triggers)}")
            print("  next: HumanReviewSkill")
            continue

        classification = classify_email(email_case)
        route = route_to_subagent(classification)
        print(f"  category: {route.category}")
        print(f"  selected_subagent: {route.selected_subagent}")
        print(f"  skills: {', '.join(route.allowed_skills)}")
        print(f"  reason: {route.reason}")


if __name__ == "__main__":
    main()
