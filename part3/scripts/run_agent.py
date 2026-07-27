from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


PART3_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PART3_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from document_agent import (  # noqa: E402
    AgentConfigurationError,
    AgentExecutionError,
    AgentResponse,
    DocumentAgent,
    create_thread_id,
    validate_thread_id,
)
from document_agent.observability import configure_logging  # noqa: E402


def format_response(response: AgentResponse) -> str:
    lines = [response.answer]
    if response.citations:
        lines.append(f"Citations: {', '.join(response.citations)}")
    if response.tool_events:
        tools = ", ".join(event.name for event in response.tool_events)
        lines.append(f"Tools: {tools}")
    lines.append(
        f"Status: {response.status} | {response.latency_ms} ms | "
        f"turn {response.turn_count}"
    )
    return "\n".join(lines)


def print_history(agent: DocumentAgent, thread_id: str) -> None:
    snapshot = agent.get_conversation(thread_id)
    visible = [
        message
        for message in snapshot.messages
        if message.role in {"user", "assistant"} and message.content.strip()
    ]
    if not visible:
        print("No conversation history.")
        return
    for message in visible:
        label = "You" if message.role == "user" else "Agent"
        print(f"{label}: {message.content}")


def run_one_shot(
    agent: DocumentAgent,
    thread_id: str,
    message: str,
    *,
    json_output: bool,
) -> int:
    try:
        response = agent.ask(thread_id, message)
    except (AgentExecutionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if json_output:
        print(json.dumps(asdict(response), ensure_ascii=True, indent=2))
    else:
        print(format_response(response))
    return 0


def run_interactive(agent: DocumentAgent, thread_id: str) -> int:
    print("Nimbus Policy Agent")
    print(f"Thread: {thread_id}")
    print("Commands: /new, /clear, /history, /quit")

    while True:
        try:
            message = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0

        if not message:
            continue
        if message.casefold() in {"/quit", "/exit"}:
            print("Goodbye.")
            return 0
        if message.casefold() == "/new":
            thread_id = create_thread_id()
            print(f"New thread: {thread_id}")
            continue
        if message.casefold() == "/clear":
            agent.clear_conversation(thread_id)
            print("Current conversation cleared.")
            continue
        if message.casefold() == "/history":
            print_history(agent, thread_id)
            continue

        try:
            response = agent.ask(thread_id, message)
        except (AgentExecutionError, ValueError) as exc:
            print(f"Agent error: {exc}")
            continue
        print(f"\nAgent: {format_response(response)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chat with the Nimbus policy document agent.",
    )
    parser.add_argument(
        "--thread-id",
        help="Resume a saved thread. A new UUID is used when omitted.",
    )
    parser.add_argument(
        "--message",
        help="Send one message and exit instead of opening interactive mode.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one-shot output as JSON.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configure_logging()
    try:
        thread_id = (
            validate_thread_id(args.thread_id)
            if args.thread_id
            else create_thread_id()
        )
        with DocumentAgent() as agent:
            if args.message is not None:
                return run_one_shot(
                    agent,
                    thread_id,
                    args.message,
                    json_output=args.json,
                )
            return run_interactive(agent, thread_id)
    except (AgentConfigurationError, OSError, ValueError) as exc:
        print(f"Startup error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
