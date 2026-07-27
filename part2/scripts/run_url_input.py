from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from web_summary_agent.url_input import load_scrape_requests  # noqa: E402


def main() -> None:
    requests = load_scrape_requests(ROOT / "data" / "sample_urls.json")
    for request in requests:
        print(f"{request.case_id} | ready")
        print(f"  url: {request.url}")
        print(f"  focus: {request.focus}")
        print(f"  maximum summary: {request.max_summary_words} words")


if __name__ == "__main__":
    main()
