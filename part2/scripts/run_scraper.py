from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from web_summary_agent.scraper import fetch_web_page  # noqa: E402
from web_summary_agent.url_input import load_scrape_requests  # noqa: E402


def main() -> None:
    requests = load_scrape_requests(ROOT / "data" / "sample_urls.json")

    for scrape_request in requests:
        page = fetch_web_page(scrape_request.url)
        print(f"{scrape_request.case_id} | downloaded")
        print(f"  final URL: {page.final_url}")
        print(f"  status: HTTP {page.status_code}")
        print(f"  content type: {page.content_type}")
        print(f"  downloaded: {page.bytes_downloaded:,} bytes")


if __name__ == "__main__":
    main()
