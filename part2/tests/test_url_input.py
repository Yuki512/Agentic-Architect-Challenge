import json
from pathlib import Path
import tempfile
import unittest

from web_summary_agent.url_input import load_scrape_requests, validate_public_url


class UrlInputTests(unittest.TestCase):
    def test_loads_real_public_url_request(self):
        request = self._load_single_request(
            {
                "case_id": "WEB-2001",
                "url": "https://www.python.org/about/#top",
                "focus": "Explain Python.",
                "max_summary_words": 120,
            }
        )

        self.assertEqual(request.case_id, "WEB-2001")
        self.assertEqual(request.url, "https://www.python.org/about/")
        self.assertEqual(request.max_summary_words, 120)

    def test_rejects_file_url(self):
        with self.assertRaisesRegex(ValueError, "http or https"):
            validate_public_url("file:///etc/passwd")

    def test_rejects_localhost(self):
        with self.assertRaisesRegex(ValueError, "public website"):
            validate_public_url("http://localhost:8000/private")

    def test_rejects_private_ip(self):
        with self.assertRaisesRegex(ValueError, "private or local IP"):
            validate_public_url("http://192.168.1.20/admin")

    def test_rejects_credentials_in_url(self):
        with self.assertRaisesRegex(ValueError, "login credentials"):
            validate_public_url("https://user:secret@example.com/")

    def test_rejects_excessive_summary_length(self):
        with self.assertRaisesRegex(ValueError, "between 40 and 250"):
            self._load_single_request(
                {
                    "case_id": "WEB-2002",
                    "url": "https://example.com/",
                    "focus": "Summarize the page.",
                    "max_summary_words": 500,
                }
            )

    def _load_single_request(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requests.json"
            path.write_text(json.dumps([value]), encoding="utf-8")
            return load_scrape_requests(path)[0]


if __name__ == "__main__":
    unittest.main()
