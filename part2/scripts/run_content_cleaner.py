from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from web_summary_agent.content_cleaner import clean_page  # noqa: E402
from web_summary_agent.scraper import fetch_web_page  # noqa: E402
from web_summary_agent.url_input import load_scrape_requests  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    requests = load_scrape_requests(ROOT / "data" / "sample_urls.json")

    for scrape_request in requests:
        fetched_page = fetch_web_page(scrape_request.url)
        cleaned_page = clean_page(fetched_page)
        print(f"{scrape_request.case_id} | content cleaned")
        print(f"  title: {cleaned_page.title}")
        print(f"  useful blocks: {cleaned_page.block_count}")
        print(f"  useful words: {cleaned_page.word_count}")
        print(f"  primary content selected: {cleaned_page.used_primary_content}")
        print(f"  duplicate blocks removed: {cleaned_page.duplicate_blocks_removed}")
        print("  preview:")
        print(f"    {cleaned_page.text[:600]}")


if __name__ == "__main__":
    main()
