from collections.abc import Callable
from pathlib import Path
import tempfile
import unittest
from typing import Any

from langchain_core.messages import AIMessage

from document_agent.agent import DocumentAgent
from document_agent.config import AgentConfig
from document_agent.memory import create_thread_id


TEST_CONFIG = AgentConfig(
    provider="deepseek",
    api_key="test-key",
    base_url="https://api.deepseek.com",
    model="deepseek-v4-flash",
    timeout_seconds=45,
    timezone_name="Asia/Singapore",
)


class ScriptedModel:
    def __init__(
        self,
        responses: list[AIMessage | Callable[[list[Any]], AIMessage]],
    ) -> None:
        self.responses = list(responses)
        self.invocations: list[list[Any]] = []
        self.bound_tool_names: tuple[str, ...] = ()
        self.tool_choice = ""

    def bind_tools(self, tools, *, tool_choice):
        self.bound_tool_names = tuple(tool.name for tool in tools)
        self.tool_choice = tool_choice
        return self

    def invoke(self, messages):
        self.invocations.append(list(messages))
        if not self.responses:
            raise AssertionError("No scripted model response remains.")
        response = self.responses.pop(0)
        return response(messages) if callable(response) else response


class DocumentAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temp_directory.name) / "agent.sqlite3"
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def build_agent(self, responses):
        model = ScriptedModel(responses)
        agent = DocumentAgent(
            database_path=self.database_path,
            config=TEST_CONFIG,
            model=model,
        )
        return agent, model

    def test_direct_policy_answer_does_not_call_tool(self):
        agent, model = self.build_agent(
            [
                AIMessage(
                    content=(
                        "Alcohol is not reimbursable under the meal policy "
                        "[P1:S4]."
                    )
                )
            ]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "Is alcohol reimbursable?",
            )

        self.assertEqual(response.status, "answer_ready")
        self.assertEqual(response.citations, ("P1:S4",))
        self.assertEqual(response.tool_events, ())
        self.assertEqual(model.bound_tool_names, ("calculator", "date_tool"))
        self.assertEqual(model.tool_choice, "auto")

    def test_calculator_is_called_for_three_night_total(self):
        agent, _ = self.build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"expression": "240 * 3"},
                            "id": "call-calculator",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(
                    content=(
                        "Three nights at S$240 per night total S$720 "
                        "[P1:S3]."
                    )
                ),
            ]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "The Singapore hotel limit is S$240. What is 3 nights?",
            )

        self.assertEqual(response.status, "answer_ready")
        self.assertEqual(len(response.tool_events), 1)
        self.assertEqual(response.tool_events[0].name, "calculator")
        self.assertEqual(response.tool_events[0].status, "ok")
        self.assertIn('"result": "720"', response.tool_events[0].result)

    def test_date_tool_is_called_for_claim_deadline(self):
        agent, _ = self.build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "date_tool",
                            "args": {
                                "operation": "add_days",
                                "start_date": "2026-08-10",
                                "days": 10,
                            },
                            "id": "call-date",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(
                    content=(
                        "The claim deadline is 20 August 2026 [P2:S6]."
                    )
                ),
            ]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "I returned on 2026-08-10. When is my claim due?",
            )

        self.assertEqual(response.tool_events[0].name, "date_tool")
        self.assertIn("2026-08-20", response.tool_events[0].result)
        self.assertEqual(response.citations, ("P2:S6",))

    def test_name_and_previous_context_are_checkpointed(self):
        agent, _ = self.build_agent(
            [
                AIMessage(content="Nice to meet you, Hojun."),
                AIMessage(content="You told me your name is Hojun."),
            ]
        )
        thread_id = create_thread_id()
        with agent:
            first = agent.ask(thread_id, "My name is Hojun.")
            second = agent.ask(thread_id, "What is my name?")
            snapshot = agent.get_conversation(thread_id)

        self.assertEqual(first.remembered_name, "Hojun")
        self.assertEqual(second.remembered_name, "Hojun")
        self.assertEqual(second.turn_count, 2)
        self.assertEqual(snapshot.user_name, "Hojun")
        self.assertEqual(len(snapshot.messages), 4)

    def test_follow_up_query_uses_previous_question_for_retrieval(self):
        agent, _ = self.build_agent(
            [
                AIMessage(
                    content=(
                        "The Singapore hotel limit is S$240 per night "
                        "[P1:S3]."
                    )
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"expression": "240 * 3"},
                            "id": "follow-up-calc",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(
                    content="Three nights total S$720 [P1:S3]."
                ),
            ]
        )
        thread_id = create_thread_id()
        with agent:
            agent.ask(thread_id, "What is the Singapore hotel limit?")
            response = agent.ask(thread_id, "What about three nights?")

        self.assertEqual(
            response.retrieved_sections[0].citation_id,
            "P1:S3",
        )
        self.assertEqual(response.tool_events[0].name, "calculator")

    def test_unsupported_ungrounded_answer_is_blocked(self):
        agent, _ = self.build_agent(
            [AIMessage(content="The championship was won by Nimbus FC.")]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "Who won the football championship?",
            )

        self.assertEqual(response.status, "grounding_blocked")
        self.assertIn("could not verify", response.answer)
        self.assertEqual(response.citations, ())

    def test_policy_answer_without_citation_is_blocked(self):
        agent, _ = self.build_agent(
            [
                AIMessage(content="The hotel limit is S$240 per night."),
                AIMessage(content="The hotel limit is S$240 per night."),
            ]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "What is the Singapore hotel limit?",
            )

        self.assertEqual(response.status, "grounding_blocked")

    def test_citation_outside_retrieved_evidence_is_blocked(self):
        agent, _ = self.build_agent(
            [
                AIMessage(content="The hotel limit is S$240 [P2:S8]."),
                AIMessage(content="The hotel limit is S$240 [P2:S8]."),
            ]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "What is the Singapore hotel limit?",
            )

        self.assertEqual(response.status, "grounding_blocked")
        self.assertEqual(response.citations, ())

    def test_missing_citation_is_repaired_once(self):
        agent, model = self.build_agent(
            [
                AIMessage(content="The hotel limit is S$240 per night."),
                AIMessage(
                    content="The hotel limit is S$240 per night [P1:S3]."
                ),
            ]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "What is the Singapore hotel limit?",
            )

        self.assertEqual(response.status, "answer_ready")
        self.assertEqual(response.citations, ("P1:S3",))
        self.assertEqual(len(model.invocations), 2)

    def test_tool_loop_stops_after_two_iterations(self):
        tool_call = lambda identifier: AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "calculator",
                    "args": {"expression": "2 + 2"},
                    "id": identifier,
                    "type": "tool_call",
                }
            ],
        )
        agent, _ = self.build_agent(
            [
                tool_call("call-1"),
                tool_call("call-2"),
                tool_call("call-3"),
            ]
        )
        with agent:
            response = agent.ask(
                create_thread_id(),
                "Please calculate 2 + 2.",
            )

        self.assertEqual(response.status, "tool_limit_reached")
        self.assertEqual(len(response.tool_events), 2)
        self.assertIn("two-tool safety limit", response.answer)

    def test_clear_removes_agent_conversation(self):
        agent, _ = self.build_agent(
            [AIMessage(content="Hello.")]
        )
        thread_id = create_thread_id()
        with agent:
            agent.ask(thread_id, "Hello.")
            agent.clear_conversation(thread_id)
            snapshot = agent.get_conversation(thread_id)

        self.assertEqual(snapshot.messages, ())
        self.assertEqual(snapshot.turn_count, 0)


if __name__ == "__main__":
    unittest.main()
