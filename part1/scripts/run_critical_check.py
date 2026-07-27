import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from support_agent.critical_detector import check_critical_issue  # noqa: E402


def main() -> None:
    mock_email_path = ROOT / "data" / "mock_emails.json"
    email_cases = json.loads(mock_email_path.read_text(encoding="utf-8"))

    for email_case in email_cases:
        result = check_critical_issue(email_case)
        status = "HANDOFF" if result.is_critical else "CONTINUE"
        print(f"{email_case['case_id']} | {status} | {email_case['subject']}")
        print(f"  triggers: {', '.join(result.matched_triggers) or 'none'}")
        print(f"  action: {result.recommended_action}")


if __name__ == "__main__":
    main()

