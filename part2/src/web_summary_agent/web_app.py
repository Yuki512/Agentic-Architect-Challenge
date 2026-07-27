from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

from web_summary_agent.orchestrator import process_url_payload
from web_summary_agent.scraper import ScrapeError
from web_summary_agent.summarizer import SummaryError


ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
SAMPLE_URLS_PATH = ROOT / "data" / "sample_urls.json"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def load_example_requests() -> list[dict[str, Any]]:
    return json.loads(SAMPLE_URLS_PATH.read_text(encoding="utf-8"))


def process_web_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return process_url_payload(payload)


class WebSummaryRequestHandler(BaseHTTPRequestHandler):
    server_version = "WebSummaryHTTP/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/examples":
            self._send_json({"examples": load_example_requests()})
            return

        requested_path = "/index.html" if parsed.path == "/" else parsed.path
        self._send_static_file(requested_path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/process":
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            result = process_web_payload(payload)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except SummaryError as exc:
            self._send_json(
                {"error": str(exc)},
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
            return
        except ScrapeError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        except Exception as exc:
            self._send_json(
                {"error": f"Processing failed: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json({"result": result})

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _read_json(self) -> dict[str, Any]:
        length = _safe_int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        if not raw_body:
            return {}

        payload = json.loads(raw_body)
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _send_json(
        self,
        value: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static_file(self, requested_path: str) -> None:
        relative_path = requested_path.lstrip("/")
        file_path = (WEB_ROOT / relative_path).resolve()

        try:
            file_path.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        if not file_path.is_file():
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            CONTENT_TYPES.get(file_path.suffix, "application/octet-stream"),
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), WebSummaryRequestHandler)
    print(f"Web Summary UI running at http://{host}:{port}")
    server.serve_forever()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
