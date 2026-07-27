from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from web_summary_agent.chunker import chunk_cleaned_page  # noqa: E402
from web_summary_agent.content_cleaner import clean_page  # noqa: E402
from web_summary_agent.scraper import fetch_web_page  # noqa: E402
from web_summary_agent.summarizer import summarize_chunks  # noqa: E402
from web_summary_agent.url_input import load_scrape_requests  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    requests = load_scrape_requests(ROOT / "data" / "sample_urls.json")

    for scrape_request in requests:
        fetched_page = fetch_web_page(scrape_request.url)
        cleaned_page = clean_page(fetched_page)
        chunks = chunk_cleaned_page(cleaned_page)
        result = summarize_chunks(
            chunks,
            focus=scrape_request.focus,
            max_words=scrape_request.max_summary_words,
        )

        print(f"{scrape_request.case_id} | summary ready")
        print(f"  title: {cleaned_page.title}")
        print(f"  summary words: {result.word_count}/{result.max_words}")
        print(f"  source chunks: {', '.join(result.source_chunk_ids)}")
        print(f"  concise guardrail: {result.guardrail.status}")
        print("  summary:")
        print(result.summary)


if __name__ == "__main__":
    main()
