from email.message import Message
import gzip
import socket
import unittest
from unittest.mock import patch

from web_summary_agent.scraper import ScrapeError, _ensure_public_host, fetch_web_page


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        url: str = "https://example.com/",
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        content_encoding: str = "",
    ):
        self._body = body
        self._url = url
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if content_encoding:
            self.headers["Content-Encoding"] = content_encoding

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self):
        return self.status

    def geturl(self):
        return self._url

    def read(self, size=-1):
        return self._body if size < 0 else self._body[:size]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


class ScraperTests(unittest.TestCase):
    @patch("web_summary_agent.scraper._ensure_public_host")
    def test_downloads_html_page(self, ensure_public_host):
        opener = FakeOpener(
            FakeResponse(b"<html><body><h1>Python</h1></body></html>")
        )

        page = fetch_web_page("https://example.com", opener=opener)

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.content_type, "text/html")
        self.assertIn("<h1>Python</h1>", page.html)
        self.assertEqual(page.bytes_downloaded, 41)
        self.assertEqual(opener.timeout, 15)
        self.assertEqual(opener.request.get_header("Accept-encoding"), "gzip, deflate")
        self.assertEqual(ensure_public_host.call_count, 2)

    @patch("web_summary_agent.scraper._ensure_public_host")
    def test_decompresses_gzip_html(self, ensure_public_host):
        html = b"<html><body><p>Compressed useful content.</p></body></html>"
        opener = FakeOpener(
            FakeResponse(gzip.compress(html), content_encoding="gzip")
        )

        page = fetch_web_page("https://example.com", opener=opener)

        self.assertEqual(page.html, html.decode("utf-8"))

    @patch("web_summary_agent.scraper._ensure_public_host")
    def test_limits_decompressed_page_size(self, ensure_public_host):
        compressed = gzip.compress(b"x" * 100)
        opener = FakeOpener(
            FakeResponse(compressed, content_encoding="gzip")
        )

        with self.assertRaisesRegex(ScrapeError, "Decompressed page exceeds"):
            fetch_web_page("https://example.com", max_bytes=50, opener=opener)

    @patch("web_summary_agent.scraper._ensure_public_host")
    def test_rejects_non_html_content(self, ensure_public_host):
        opener = FakeOpener(
            FakeResponse(b"%PDF", content_type="application/pdf")
        )

        with self.assertRaisesRegex(ScrapeError, "Expected an HTML page"):
            fetch_web_page("https://example.com/report.pdf", opener=opener)

    @patch("web_summary_agent.scraper._ensure_public_host")
    def test_rejects_page_over_download_limit(self, ensure_public_host):
        opener = FakeOpener(FakeResponse(b"x" * 21))

        with self.assertRaisesRegex(ScrapeError, "20-byte download limit"):
            fetch_web_page("https://example.com", max_bytes=20, opener=opener)

    @patch("web_summary_agent.scraper.socket.getaddrinfo")
    def test_rejects_hostname_resolving_to_private_ip(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]

        with self.assertRaisesRegex(ScrapeError, "private or local IP"):
            _ensure_public_host("https://example.com/")

    @patch("web_summary_agent.scraper.socket.getaddrinfo")
    def test_accepts_hostname_resolving_to_public_ip(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]

        _ensure_public_host("https://example.com/")

    @patch("web_summary_agent.scraper.socket.getaddrinfo")
    def test_reports_dns_failure(self, getaddrinfo):
        getaddrinfo.side_effect = socket.gaierror("not found")

        with self.assertRaisesRegex(ScrapeError, "Could not resolve"):
            _ensure_public_host("https://missing.example/")


if __name__ == "__main__":
    unittest.main()
