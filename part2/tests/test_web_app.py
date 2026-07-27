import unittest
from unittest.mock import patch

from web_summary_agent.web_app import load_example_requests, process_web_payload


class WebAppTests(unittest.TestCase):
    def test_loads_optional_public_url_example(self):
        examples = load_example_requests()

        self.assertGreater(len(examples), 0)
        self.assertEqual(examples[0]["url"], "https://en.wikipedia.org/wiki/Reborn!")

    @patch("web_summary_agent.web_app.process_url_payload")
    def test_web_processor_receives_user_payload(self, processor):
        processor.return_value = {"status": "summary_ready"}
        payload = {
            "case_id": "WEB-UI-001",
            "url": "https://example.com/article",
            "focus": "Main ideas",
            "max_summary_words": 100,
        }

        result = process_web_payload(payload)

        self.assertEqual(result["status"], "summary_ready")
        processor.assert_called_once_with(payload)

    def test_static_ui_files_exist(self):
        from web_summary_agent.web_app import WEB_ROOT

        self.assertTrue((WEB_ROOT / "index.html").is_file())
        self.assertTrue((WEB_ROOT / "styles.css").is_file())
        self.assertTrue((WEB_ROOT / "app.js").is_file())


if __name__ == "__main__":
    unittest.main()
