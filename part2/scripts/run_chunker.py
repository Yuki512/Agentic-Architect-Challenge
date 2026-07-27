from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from web_summary_agent.chunker import chunk_cleaned_page  # noqa: E402
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
        chunks = chunk_cleaned_page(cleaned_page)

        print(f"{scrape_request.case_id} | long content prepared")
        print(f"  cleaned words: {cleaned_page.word_count}")
        print(f"  chunks created: {len(chunks)}")
        for chunk in chunks:
            print(f"  {chunk.chunk_id}: {chunk.word_count} words")


if __name__ == "__main__":
    main()
