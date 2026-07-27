from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from web_summary_agent.orchestrator import process_scrape_request  # noqa: E402
from web_summary_agent.url_input import load_scrape_requests  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    requests = load_scrape_requests(ROOT / "data" / "sample_urls.json")

    for request in requests:
        result = process_scrape_request(request)
        print(f"{result.case_id} | {result.status}")
        print(f"  final URL: {result.fetch.final_url}")
        print(f"  HTTP status: {result.fetch.status_code}")
        print(f"  title: {result.cleaning.title}")
        print(f"  useful words: {result.cleaning.useful_words}")
        print(f"  chunks: {len(result.chunks)}")
        print(
            f"  summary: {result.summary.word_count}/"
            f"{result.summary.max_words} words"
        )
        print(f"  guardrail: {result.summary.guardrail.status}")
        print(f"  summarizer: {result.summary.provider}")
        if result.summary.model:
            print(f"  model: {result.summary.model}")
        if result.summary.fallback_reason:
            print(f"  fallback: {result.summary.fallback_reason}")
        print("  result:")
        print(result.summary.summary)


if __name__ == "__main__":
    main()
