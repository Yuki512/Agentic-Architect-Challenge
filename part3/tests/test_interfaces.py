from dataclasses import replace
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

from document_agent.agent import AgentResponse, EvidenceReference, ToolEvent
from document_agent.memory import (
    ConversationMessage,
    ConversationSnapshot,
    create_thread_id,
)
from document_agent.web_app import (
    MAX_REQUEST_BYTES,
    parse_chat_payload,
    serialize_conversation,
    serialize_health,
    serialize_response,
)


PART3_ROOT = Path(__file__).resolve().parents[1]


def load_cli_module():
    path = PART3_ROOT / "scripts" / "run_agent.py"
    spec = importlib.util.spec_from_file_location("part3_run_agent", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load the Part 3 CLI module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InterfaceHelperTests(unittest.TestCase):
    def setUp(self):
        self.thread_id = create_thread_id()
        self.response = AgentResponse(
            request_id="request-1",
            thread_id=self.thread_id,
            status="answer_ready",
            answer="The limit is S$240 [P1:S3].",
            citations=("P1:S3",),
            remembered_name="Hojun",
            turn_count=2,
            retrieved_sections=(
                EvidenceReference(
                    citation_id="P1:S3",
                    title="Lodging",
                    page_number=1,
                    score=3.25,
                ),
            ),
            tool_events=(
                ToolEvent(
                    name="calculator",
                    arguments={"expression": "240 * 3"},
                    result='{"status":"ok","result":720}',
                    status="ok",
                ),
            ),
            provider="deepseek",
            model="deepseek-v4-flash",
            latency_ms=120,
        )

    def test_parse_chat_payload_normalizes_values(self):
        thread_id, message = parse_chat_payload(
            {
                "thread_id": f"  {self.thread_id}  ",
                "message": "  What   is the limit?  ",
            }
        )

        self.assertEqual(thread_id, self.thread_id)
        self.assertEqual(message, "What is the limit?")

    def test_parse_chat_payload_rejects_non_object(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            parse_chat_payload(["not", "an", "object"])

    def test_parse_chat_payload_rejects_invalid_thread(self):
        with self.assertRaisesRegex(ValueError, "thread_id"):
            parse_chat_payload(
                {"thread_id": "../bad", "message": "Hello"}
            )

    def test_response_serialization_keeps_trace_metadata(self):
        payload = serialize_response(self.response)

        self.assertEqual(payload["citations"], ("P1:S3",))
        self.assertEqual(
            payload["retrieved_sections"][0]["page_number"],
            1,
        )
        self.assertEqual(payload["tool_events"][0]["name"], "calculator")

    def test_conversation_serialization_hides_internal_messages(self):
        snapshot = ConversationSnapshot(
            thread_id=self.thread_id,
            user_name="Hojun",
            turn_count=1,
            messages=(
                ConversationMessage("system", "private prompt"),
                ConversationMessage("user", "Hello"),
                ConversationMessage("tool", "private result"),
                ConversationMessage("assistant", "Hi Hojun."),
                ConversationMessage("assistant", ""),
            ),
        )

        payload = serialize_conversation(snapshot)

        self.assertEqual(
            [item["role"] for item in payload["messages"]],
            ["user", "assistant"],
        )
        self.assertNotIn("private", str(payload))

    def test_cli_format_includes_citations_and_tool_name(self):
        module = load_cli_module()

        formatted = module.format_response(self.response)

        self.assertIn("Citations: P1:S3", formatted)
        self.assertIn("Tools: calculator", formatted)
        self.assertIn("120 ms", formatted)

    def test_cli_format_omits_empty_optional_lines(self):
        module = load_cli_module()
        response = replace(
            self.response,
            citations=(),
            tool_events=(),
        )

        formatted = module.format_response(response)

        self.assertNotIn("Citations:", formatted)
        self.assertNotIn("Tools:", formatted)

    def test_request_bound_is_small_and_explicit(self):
        self.assertGreaterEqual(MAX_REQUEST_BYTES, 4_096)
        self.assertLessEqual(MAX_REQUEST_BYTES, 65_536)

    def test_health_payload_reports_dependencies_without_local_paths(self):
        agent = SimpleNamespace(
            config=SimpleNamespace(
                provider="deepseek",
                model="deepseek-v4-flash",
            ),
            document=SimpleNamespace(
                title="Nimbus Travel & Expense Policy",
                page_count=3,
                sections=(object(), object()),
            ),
            database_path="C:/private/conversations.sqlite3",
        )

        payload = serialize_health(agent)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["document"]["sections"], 2)
        self.assertEqual(payload["memory"]["backend"], "sqlite")
        self.assertTrue(payload["memory"]["persistent"])
        self.assertNotIn("C:/private", str(payload))


class StaticInterfaceTests(unittest.TestCase):
    def test_required_static_files_exist(self):
        for name in ("index.html", "styles.css", "app.js"):
            path = PART3_ROOT / "web" / name
            self.assertTrue(path.is_file(), name)
            self.assertGreater(path.stat().st_size, 100)

    def test_interface_has_mobile_panels_and_pdf(self):
        html = (PART3_ROOT / "web" / "index.html").read_text(
            encoding="utf-8"
        )
        css = (PART3_ROOT / "web" / "styles.css").read_text(
            encoding="utf-8"
        )

        self.assertIn('src="/document#page=1', html)
        self.assertIn('data-panel="chat"', html)
        self.assertIn('data-panel="document"', html)
        self.assertIn('data-panel="trace"', html)
        self.assertIn("@media (max-width: 820px)", css)


if __name__ == "__main__":
    unittest.main()
