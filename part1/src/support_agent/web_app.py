from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

from support_agent.orchestrator import process_email_as_dict
from support_agent.llm_drafting import draft_with_configured_provider
from support_agent.router_agent import classify_with_configured_router
from support_agent.semantic_critical import (
    check_semantic_critical_with_configured_provider,
)


ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
MOCK_EMAILS_PATH = ROOT / "data" / "mock_emails.json"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def load_example_emails() -> list[dict[str, Any]]:
    return json.loads(MOCK_EMAILS_PATH.read_text(encoding="utf-8"))


def process_email_payload(
    payload: dict[str, Any],
    *,
    classifier=classify_with_configured_router,
    drafter=draft_with_configured_provider,
    semantic_checker=check_semantic_critical_with_configured_provider,
) -> dict[str, Any]:
    email_case = {
        "case_id": str(payload.get("case_id") or "WEB-CASE-001"),
        "customer_id": str(payload.get("customer_id") or "WEB-CUSTOMER"),
        "customer_name": str(payload.get("customer_name") or "Customer"),
        "customer_email": str(payload.get("customer_email") or "customer@example.com"),
        "subject": str(payload.get("subject") or ""),
        "body": str(payload.get("body") or ""),
        "contact_count_last_7_days": _safe_int(payload.get("contact_count_last_7_days", 0)),
        "received_at": str(payload.get("received_at") or ""),
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }

    if not email_case["subject"].strip() and not email_case["body"].strip():
        raise ValueError("Subject or body is required.")

    return process_email_as_dict(
        email_case,
        classifier=classifier,
        drafter=drafter,
        semantic_checker=semantic_checker,
    )


class SupportAgentRequestHandler(BaseHTTPRequestHandler):
    server_version = "SupportAgentHTTP/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/examples":
            self._send_json({"examples": load_example_emails()})
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
            result = process_email_payload(payload)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self._send_json({"error": f"Processing failed: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
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

    def _send_json(self, value: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static_file(self, requested_path: str) -> None:
        relative_path = requested_path.lstrip("/")
        file_path = (WEB_ROOT / relative_path).resolve()

        if not str(file_path).startswith(str(WEB_ROOT.resolve())) or not file_path.is_file():
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), SupportAgentRequestHandler)
    print(f"Support Agent UI running at http://{host}:{port}")
    server.serve_forever()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
