from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Annotated, Any
from uuid import uuid4


os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langchain_core.messages import (  # noqa: E402
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
)
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.graph.message import add_messages  # noqa: E402
from typing_extensions import TypedDict  # noqa: E402


PART3_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_PATH = PART3_ROOT / "data" / "conversations.sqlite3"
MAX_USER_MESSAGE_LENGTH = 2_000
MAX_ASSISTANT_MESSAGE_LENGTH = 8_000
MAX_RETAINED_TURNS = 20
THREAD_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
NAME_PATTERNS = (
    re.compile(
        r"\bmy name is\s+"
        r"(?P<name>[A-Za-z][A-Za-z'-]*"
        r"(?:\s+[A-Za-z][A-Za-z'-]*){0,3})"
        r"(?=\s*(?:[.!?,]|$|\band\b|\bbut\b))",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcall me\s+"
        r"(?P<name>[A-Za-z][A-Za-z'-]*"
        r"(?:\s+[A-Za-z][A-Za-z'-]*){0,3})"
        r"(?=\s*(?:[.!?,]|$|\band\b|\bbut\b))",
        re.IGNORECASE,
    ),
)


class ConversationState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    user_name: str
    turn_count: int


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ConversationSnapshot:
    thread_id: str
    user_name: str | None
    turn_count: int
    messages: tuple[ConversationMessage, ...]


def create_thread_id() -> str:
    return str(uuid4())


def validate_thread_id(thread_id: str) -> str:
    normalized = thread_id.strip()
    if not THREAD_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "thread_id must be 1-128 characters using only letters, "
            "numbers, dots, underscores, or hyphens."
        )
    return normalized


def capture_memory(state: ConversationState) -> dict[str, Any]:
    messages = list(state.get("messages", ()))
    latest_user_message = next(
        (
            message.content
            for message in reversed(messages)
            if isinstance(message, HumanMessage)
            and isinstance(message.content, str)
        ),
        "",
    )
    remembered_name = _extract_name(latest_user_message)
    update: dict[str, Any] = {
        "turn_count": int(state.get("turn_count", 0)) + 1,
    }
    if remembered_name:
        update["user_name"] = remembered_name

    retained_message_count = MAX_RETAINED_TURNS * 2
    if len(messages) > retained_message_count:
        update["messages"] = [
            RemoveMessage(id=message.id)
            for message in messages[:-retained_message_count]
            if message.id
        ]
    return update


class ConversationMemory:
    def __init__(
        self,
        database_path: Path | str = DEFAULT_MEMORY_PATH,
    ) -> None:
        self.database_path = _normalize_database_path(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
        )
        self._checkpointer = SqliteSaver(self._connection)
        self._graph = _build_memory_graph(self._checkpointer)
        self._closed = False

    def record_exchange(
        self,
        thread_id: str,
        user_message: str,
        assistant_message: str,
    ) -> ConversationSnapshot:
        self._ensure_open()
        validated_thread_id = validate_thread_id(thread_id)
        normalized_user_message = _validate_message(
            user_message,
            field_name="user_message",
            maximum_length=MAX_USER_MESSAGE_LENGTH,
        )
        normalized_assistant_message = _validate_message(
            assistant_message,
            field_name="assistant_message",
            maximum_length=MAX_ASSISTANT_MESSAGE_LENGTH,
        )
        self._graph.invoke(
            {
                "messages": [
                    HumanMessage(content=normalized_user_message),
                    AIMessage(content=normalized_assistant_message),
                ]
            },
            thread_config(validated_thread_id),
        )
        return self.get_conversation(validated_thread_id)

    def get_conversation(self, thread_id: str) -> ConversationSnapshot:
        self._ensure_open()
        validated_thread_id = validate_thread_id(thread_id)
        state = self._graph.get_state(thread_config(validated_thread_id))
        return snapshot_from_values(
            validated_thread_id,
            state.values or {},
        )

    def clear_conversation(self, thread_id: str) -> None:
        self._ensure_open()
        self._checkpointer.delete_thread(validate_thread_id(thread_id))

    def close(self) -> None:
        if self._closed:
            return
        self._connection.close()
        self._closed = True

    def __enter__(self) -> ConversationMemory:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Conversation memory is closed.")


def _build_memory_graph(checkpointer: SqliteSaver) -> Any:
    builder = StateGraph(ConversationState)
    builder.add_node("capture_memory", capture_memory)
    builder.add_edge(START, "capture_memory")
    builder.add_edge("capture_memory", END)
    return builder.compile(checkpointer=checkpointer)


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": validate_thread_id(thread_id)}}


def validate_user_message(value: str) -> str:
    return _validate_message(
        value,
        field_name="user_message",
        maximum_length=MAX_USER_MESSAGE_LENGTH,
    )


def snapshot_from_values(
    thread_id: str,
    values: dict[str, Any],
) -> ConversationSnapshot:
    validated_thread_id = validate_thread_id(thread_id)
    return ConversationSnapshot(
        thread_id=validated_thread_id,
        user_name=values.get("user_name") or None,
        turn_count=int(values.get("turn_count", 0)),
        messages=tuple(
            _serialize_message(message)
            for message in values.get("messages", ())
            if isinstance(message, BaseMessage)
        ),
    )


def _normalize_database_path(database_path: Path | str) -> str:
    if str(database_path) == ":memory:":
        return ":memory:"
    return str(Path(database_path).expanduser().resolve())


def _validate_message(
    value: str,
    *,
    field_name: str,
    maximum_length: int,
) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(normalized) > maximum_length:
        raise ValueError(
            f"{field_name} cannot exceed {maximum_length:,} characters."
        )
    return normalized


def _extract_name(message: str) -> str | None:
    for pattern in NAME_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group("name")).strip(" .,!?'\"")
        if name:
            return " ".join(part.capitalize() for part in name.split())
    return None


def _serialize_message(message: BaseMessage) -> ConversationMessage:
    role = {
        "ai": "assistant",
        "human": "user",
        "system": "system",
        "tool": "tool",
    }.get(message.type, message.type)
    content = message.content
    if isinstance(content, str):
        serialized_content = content
    else:
        serialized_content = json.dumps(
            content,
            ensure_ascii=True,
            sort_keys=True,
        )
    return ConversationMessage(role=role, content=serialized_content)
