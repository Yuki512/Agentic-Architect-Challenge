from __future__ import annotations

import argparse
from dataclasses import asdict
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
from typing import Any
from urllib.parse import unquote, urlparse

from document_agent.agent import AgentExecutionError, AgentResponse, DocumentAgent
from document_agent.document_loader import DEFAULT_DOCUMENT_PATH
from document_agent.memory import (
    MAX_USER_MESSAGE_LENGTH,
    ConversationSnapshot,
    validate_thread_id,
    validate_user_message,
)
from document_agent.observability import configure_logging


PART3_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PART3_ROOT / "web"
MAX_REQUEST_BYTES = 16_384
THREAD_ROUTE = re.compile(r"^/api/conversations/([^/]+)$")


def serialize_response(response: AgentResponse) -> dict[str, Any]:
    return asdict(response)


def serialize_conversation(snapshot: ConversationSnapshot) -> dict[str, Any]:
    messages = [
        asdict(message)
        for message in snapshot.messages
        if message.role in {"user", "assistant"} and message.content.strip()
    ]
    return {
        "thread_id": snapshot.thread_id,
        "remembered_name": snapshot.user_name,
        "turn_count": snapshot.turn_count,
        "messages": messages,
    }


def serialize_health(agent: DocumentAgent) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "nimbus-policy-agent",
        "provider": agent.config.provider,
        "model": agent.config.model,
        "document": {
            "title": agent.document.title,
            "pages": agent.document.page_count,
            "sections": len(agent.document.sections),
        },
        "memory": {
            "backend": "sqlite",
            "persistent": agent.database_path != ":memory:",
        },
    }


def parse_chat_payload(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    thread_id = validate_thread_id(str(payload.get("thread_id", "")))
    message = validate_user_message(str(payload.get("message", "")))
    return thread_id, message


class AgentHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[SimpleHTTPRequestHandler],
        *,
        agent: DocumentAgent,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.agent = agent
        self.agent_lock = threading.Lock()


class AgentRequestHandler(SimpleHTTPRequestHandler):
    server: AgentHTTPServer

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                serialize_health(self.server.agent),
            )
            return
        if path == "/api/config":
            self._send_json(
                HTTPStatus.OK,
                {
                    "provider": self.server.agent.config.provider,
                    "model": self.server.agent.config.model,
                    "document": "Nimbus Travel and Expense Policy",
                    "max_message_length": MAX_USER_MESSAGE_LENGTH,
                },
            )
            return
        match = THREAD_ROUTE.fullmatch(path)
        if match:
            self._get_conversation(unquote(match.group(1)))
            return
        if path == "/document":
            self._send_document()
            return
        super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/chat":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            payload = self._read_json()
            thread_id, message = parse_chat_payload(payload)
            response = self.server.agent.ask(thread_id, message)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except AgentExecutionError as exc:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": str(exc)},
            )
            return
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "The document agent could not complete the request."},
            )
            return
        self._send_json(HTTPStatus.OK, serialize_response(response))

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        match = THREAD_ROUTE.fullmatch(path)
        if not match:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            thread_id = validate_thread_id(unquote(match.group(1)))
            self.server.agent.clear_conversation(thread_id)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, {"status": "cleared"})

    def log_message(self, format: str, *args: Any) -> None:
        print(
            f"{self.address_string()} - "
            f"[{self.log_date_time_string()}] {format % args}"
        )

    def _get_conversation(self, raw_thread_id: str) -> None:
        try:
            thread_id = validate_thread_id(raw_thread_id)
            snapshot = self.server.agent.get_conversation(thread_id)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(
            HTTPStatus.OK,
            serialize_conversation(snapshot),
        )

    def _read_json(self) -> Any:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer.") from exc
        if length <= 0:
            raise ValueError("Request body is required.")
        if length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is too large.")
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def _send_document(self) -> None:
        try:
            content = DEFAULT_DOCUMENT_PATH.read_bytes()
        except OSError:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "Policy document was not found."},
            )
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(content)))
        self.send_header(
            "Content-Disposition",
            'inline; filename="nimbus-travel-expense-policy.pdf"',
        )
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: HTTPStatus, payload: Any) -> None:
        content = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def create_server(
    host: str = "127.0.0.1",
    port: int = 9000,
    *,
    agent: DocumentAgent | None = None,
) -> AgentHTTPServer:
    active_agent = agent or DocumentAgent()
    handler = partial(AgentRequestHandler)
    return AgentHTTPServer(
        (host, port),
        handler,
        agent=active_agent,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local Nimbus policy agent web app.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configure_logging()
    server = create_server(args.host, args.port)
    url = f"http://{args.host}:{server.server_port}"
    print(f"Nimbus Policy Agent running at {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Part 3 server.", flush=True)
    finally:
        server.shutdown()
        server.server_close()
        server.agent.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
