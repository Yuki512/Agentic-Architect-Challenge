import json
import unittest

from web_summary_agent.orchestrator import (
    PIPELINE_COMPONENTS,
    process_scrape_request,
    process_url_payload,
)
from web_summary_agent.scraper import FetchedPage
from web_summary_agent.summarizer import summarize_chunks
from web_summary_agent.url_input import ScrapeRequest


HTML = """
<html>
  <head><title>Python Overview</title></head>
  <body>
    <nav><p>Home Products Login Documentation</p></nav>
    <main>
      <h1>Python is powerful and easy to learn</h1>
      <p>Python is a readable programming language with an open-source community.</p>
      <p>Developers use Python for web development, automation, and scientific computing.</p>
      <p>Its large package ecosystem helps teams build useful software efficiently.</p>
    </main>
    <footer><p>Copyright and privacy links belong here.</p></footer>
  </body>
</html>
"""


def fake_fetcher(url: str) -> FetchedPage:
    return FetchedPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        charset="utf-8",
        html=HTML,
        bytes_downloaded=len(HTML.encode("utf-8")),
    )


class OrchestratorTests(unittest.TestCase):
    def test_processes_complete_pipeline(self):
        request = ScrapeRequest(
            case_id="WEB-TEST-001",
            url="https://example.com/article",
            focus="Explain Python benefits and applications.",
            max_summary_words=60,
        )

        result = process_scrape_request(
            request,
            fetcher=fake_fetcher,
            summarizer=summarize_chunks,
        )

        self.assertEqual(result.status, "summary_ready")
        self.assertEqual(result.fetch.status_code, 200)
        self.assertEqual(result.cleaning.title, "Python Overview")
        self.assertGreater(result.cleaning.useful_words, 0)
        self.assertGreater(len(result.chunks), 0)
        self.assertEqual(result.summary.guardrail.status, "passed")
        self.assertLessEqual(result.summary.word_count, 60)
        self.assertEqual(result.components, PIPELINE_COMPONENTS)

    def test_serialized_result_does_not_expose_raw_html(self):
        payload = {
            "case_id": "WEB-TEST-002",
            "url": "https://example.com/article",
            "focus": "Summarize Python applications.",
            "max_summary_words": 60,
        }

        result = process_url_payload(
            payload,
            fetcher=fake_fetcher,
            summarizer=summarize_chunks,
        )
        serialized = json.dumps(result)

        self.assertNotIn("<html>", serialized)
        self.assertNotIn("Home Products Login", serialized)
        self.assertIn("summary_ready", serialized)
        self.assertIn("Python", result["summary"]["summary"])

    def test_payload_validation_runs_before_fetch(self):
        fetch_calls = []

        def recording_fetcher(url):
            fetch_calls.append(url)
            return fake_fetcher(url)

        with self.assertRaisesRegex(ValueError, "public website"):
            process_url_payload(
                {
                    "case_id": "WEB-TEST-003",
                    "url": "http://localhost/private",
                    "focus": "Summarize the page.",
                    "max_summary_words": 60,
                },
                fetcher=recording_fetcher,
                summarizer=summarize_chunks,
            )

        self.assertEqual(fetch_calls, [])

    def test_payload_honors_requested_summary_limit(self):
        result = process_url_payload(
            {
                "case_id": "WEB-TEST-004",
                "url": "https://example.com/article",
                "focus": "Python benefits",
                "max_summary_words": 40,
            },
            fetcher=fake_fetcher,
            summarizer=summarize_chunks,
        )

        self.assertLessEqual(result["summary"]["word_count"], 40)


if __name__ == "__main__":
    unittest.main()
