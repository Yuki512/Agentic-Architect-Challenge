from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from document_agent import ConversationMemory, create_thread_id  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demonstrate persistent Part 3 conversation memory."
    )
    parser.add_argument(
        "--thread-id",
        default=create_thread_id(),
        help="Conversation ID to create or resume.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the selected conversation before recording the demo.",
    )
    args = parser.parse_args()

    with ConversationMemory() as memory:
        if args.clear:
            memory.clear_conversation(args.thread_id)
        memory.record_exchange(
            args.thread_id,
            "My name is Hojun.",
            "Nice to meet you, Hojun.",
        )
        snapshot = memory.record_exchange(
            args.thread_id,
            "What name did I give you?",
            "You told me your name is Hojun.",
        )

    print(f"thread_id={snapshot.thread_id}")
    print(f"user_name={snapshot.user_name}")
    print(f"turn_count={snapshot.turn_count}")
    print(f"message_count={len(snapshot.messages)}")


if __name__ == "__main__":
    main()
