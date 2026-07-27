from pathlib import Path
import tempfile
import unittest
from uuid import UUID

from document_agent.memory import (
    MAX_RETAINED_TURNS,
    MAX_USER_MESSAGE_LENGTH,
    ConversationMemory,
    create_thread_id,
    validate_thread_id,
)


class ConversationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temp_directory.name) / "conversation.sqlite3"
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_create_thread_id_returns_uuid(self):
        thread_id = create_thread_id()

        self.assertEqual(str(UUID(thread_id)), thread_id)

    def test_remembers_name_and_previous_messages(self):
        thread_id = create_thread_id()
        with ConversationMemory(self.database_path) as memory:
            memory.record_exchange(
                thread_id,
                "My name is Hojun.",
                "Nice to meet you, Hojun.",
            )
            snapshot = memory.record_exchange(
                thread_id,
                "What is the Singapore hotel limit?",
                "The limit is S$240 per night.",
            )

        self.assertEqual(snapshot.user_name, "Hojun")
        self.assertEqual(snapshot.turn_count, 2)
        self.assertEqual(
            tuple(message.role for message in snapshot.messages),
            ("user", "assistant", "user", "assistant"),
        )
        self.assertIn("hotel limit", snapshot.messages[2].content)

    def test_memory_survives_database_reopen(self):
        thread_id = create_thread_id()
        with ConversationMemory(self.database_path) as memory:
            memory.record_exchange(
                thread_id,
                "Call me June.",
                "I will remember that.",
            )

        with ConversationMemory(self.database_path) as reopened:
            snapshot = reopened.get_conversation(thread_id)

        self.assertEqual(snapshot.user_name, "June")
        self.assertEqual(snapshot.turn_count, 1)
        self.assertEqual(len(snapshot.messages), 2)

    def test_name_can_be_updated(self):
        thread_id = create_thread_id()
        with ConversationMemory(self.database_path) as memory:
            memory.record_exchange(
                thread_id,
                "My name is Hojun.",
                "Hello, Hojun.",
            )
            snapshot = memory.record_exchange(
                thread_id,
                "Please call me June.",
                "Understood, June.",
            )

        self.assertEqual(snapshot.user_name, "June")

    def test_clear_removes_conversation(self):
        thread_id = create_thread_id()
        with ConversationMemory(self.database_path) as memory:
            memory.record_exchange(thread_id, "Hello.", "Hello.")
            memory.clear_conversation(thread_id)
            snapshot = memory.get_conversation(thread_id)

        self.assertEqual(snapshot.turn_count, 0)
        self.assertEqual(snapshot.messages, ())
        self.assertIsNone(snapshot.user_name)

    def test_retains_only_latest_twenty_turns(self):
        thread_id = create_thread_id()
        with ConversationMemory(self.database_path) as memory:
            for turn in range(MAX_RETAINED_TURNS + 2):
                memory.record_exchange(
                    thread_id,
                    f"Question {turn}.",
                    f"Answer {turn}.",
                )
            snapshot = memory.get_conversation(thread_id)

        self.assertEqual(snapshot.turn_count, MAX_RETAINED_TURNS + 2)
        self.assertEqual(len(snapshot.messages), MAX_RETAINED_TURNS * 2)
        self.assertEqual(snapshot.messages[0].content, "Question 2.")

    def test_invalid_thread_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "thread_id must be"):
            validate_thread_id("../outside")

    def test_empty_user_message_is_rejected(self):
        with ConversationMemory(self.database_path) as memory:
            with self.assertRaisesRegex(ValueError, "cannot be empty"):
                memory.record_exchange(create_thread_id(), " ", "Hello.")

    def test_long_user_message_is_rejected(self):
        with ConversationMemory(self.database_path) as memory:
            with self.assertRaisesRegex(ValueError, "cannot exceed"):
                memory.record_exchange(
                    create_thread_id(),
                    "x" * (MAX_USER_MESSAGE_LENGTH + 1),
                    "Hello.",
                )

    def test_closed_memory_rejects_operations(self):
        memory = ConversationMemory(self.database_path)
        memory.close()

        with self.assertRaisesRegex(RuntimeError, "closed"):
            memory.get_conversation(create_thread_id())


if __name__ == "__main__":
    unittest.main()
