from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import sqlite3
import threading
from time import perf_counter
from typing import Any
from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from document_agent.config import (
    AgentConfig,
    build_chat_model,
    load_agent_config,
)
from document_agent.document_loader import (
    DEFAULT_DOCUMENT_PATH,
    load_policy_document,
)
from document_agent.memory import (
    DEFAULT_MEMORY_PATH,
    ConversationSnapshot,
    ConversationState,
    capture_memory,
    snapshot_from_values,
    thread_config,
    validate_thread_id,
    validate_user_message,
)
from document_agent.observability import log_event
from document_agent.retriever import DocumentRetriever
from document_agent.tools import calculator, date_tool


MAX_TOOL_ITERATIONS = 2
CITATION_PATTERN = re.compile(r"\[(P\d+:S\d+)\]")
REFUSAL_MARKERS = (
    "does not provide",
    "doesn't provide",
    "not covered",
    "could not find",
    "couldn't find",
    "cannot find",
    "not in the policy",
)
SOCIAL_OR_MEMORY_PATTERNS = (
    re.compile(r"\b(?:my name|your name|what name|call me|remember|told you)\b"),
    re.compile(r"^(?:hello|hi|hey|thanks|thank you|help)\b"),
)
AGENT_TOOLS = (calculator, date_tool)
LOGGER = logging.getLogger("document_agent.agent")


class AgentExecutionError(RuntimeError):
    """Raised when the Part 3 agent cannot complete a turn safely."""


class EvidenceState(TypedDict):
    citation_id: str
    title: str
    page_number: int
    score: float
    text: str


class ToolEventState(TypedDict):
    name: str
    arguments: dict[str, Any]
    result: str
    status: str


class AgentState(ConversationState, total=False):
    request_id: str
    retrieval_query: str
    retrieved_sections: list[EvidenceState]
    tool_iterations: int
    tool_trace: list[ToolEventState]
    final_answer: str
    citations: list[str]
    status: str
    validation_attempts: int
    validation_reason: str


@dataclass(frozen=True)
class EvidenceReference:
    citation_id: str
    title: str
    page_number: int
    score: float


@dataclass(frozen=True)
class ToolEvent:
    name: str
    arguments: dict[str, Any]
    result: str
    status: str


@dataclass(frozen=True)
class AgentResponse:
    request_id: str
    thread_id: str
    status: str
    answer: str
    citations: tuple[str, ...]
    remembered_name: str | None
    turn_count: int
    retrieved_sections: tuple[EvidenceReference, ...]
    tool_events: tuple[ToolEvent, ...]
    provider: str
    model: str
    latency_ms: int


class DocumentAgent:
    def __init__(
        self,
        *,
        database_path: Path | str = DEFAULT_MEMORY_PATH,
        document_path: Path | str = DEFAULT_DOCUMENT_PATH,
        config: AgentConfig | None = None,
        model: Any | None = None,
    ) -> None:
        self.config = config or load_agent_config()
        self.document = load_policy_document(document_path)
        self.retriever = DocumentRetriever(self.document)
        self.database_path = _normalize_database_path(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
        )
        self._checkpointer = SqliteSaver(self._connection)
        base_model = model or build_chat_model(self.config)
        self._base_model = base_model
        self._model = base_model.bind_tools(
            AGENT_TOOLS,
            tool_choice="auto",
        )
        self._tool_node = ToolNode(AGENT_TOOLS, handle_tool_errors=True)
        self._graph = self._build_graph()
        self._thread_locks: dict[str, threading.Lock] = {}
        self._thread_locks_guard = threading.Lock()
        self._closed = False

    def ask(self, thread_id: str, message: str) -> AgentResponse:
        self._ensure_open()
        validated_thread_id = validate_thread_id(thread_id)
        normalized_message = validate_user_message(message)
        request_id = str(uuid4())
        started = perf_counter()
        try:
            with self._lock_for_thread(validated_thread_id):
                values = self._graph.invoke(
                    {
                        "messages": [
                            HumanMessage(content=normalized_message)
                        ],
                        "request_id": request_id,
                    },
                    thread_config(validated_thread_id),
                )
            response = self._response_from_state(
                validated_thread_id,
                values,
                request_id=request_id,
                latency_ms=round((perf_counter() - started) * 1_000),
            )
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1_000)
            public_error = _safe_execution_error(exc)
            log_event(
                LOGGER,
                logging.ERROR,
                "agent_turn_failed",
                request_id=request_id,
                thread_id=validated_thread_id,
                latency_ms=latency_ms,
                error_type=type(exc).__name__,
                public_error=public_error,
            )
            raise AgentExecutionError(public_error) from exc
        log_event(
            LOGGER,
            logging.INFO,
            "agent_turn_completed",
            request_id=request_id,
            thread_id=validated_thread_id,
            status=response.status,
            latency_ms=response.latency_ms,
            evidence_count=len(response.retrieved_sections),
            tool_count=len(response.tool_events),
        )
        return response

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
        validated_thread_id = validate_thread_id(thread_id)
        with self._lock_for_thread(validated_thread_id):
            self._checkpointer.delete_thread(validated_thread_id)

    def close(self) -> None:
        if self._closed:
            return
        self._connection.close()
        self._closed = True

    def __enter__(self) -> DocumentAgent:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _build_graph(self) -> Any:
        builder = StateGraph(AgentState)
        builder.add_node("prepare_turn", self._prepare_turn)
        builder.add_node("agent", self._call_agent)
        builder.add_node("tools", self._execute_tools)
        builder.add_node("tool_limit", self._tool_limit)
        builder.add_node("validate", self._validate_answer)
        builder.add_node("repair_citations", self._repair_citations)
        builder.add_edge(START, "prepare_turn")
        builder.add_edge("prepare_turn", "agent")
        builder.add_conditional_edges(
            "agent",
            self._route_after_agent,
            {
                "tools": "tools",
                "tool_limit": "tool_limit",
                "validate": "validate",
            },
        )
        builder.add_edge("tools", "agent")
        builder.add_edge("tool_limit", "validate")
        builder.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {
                "repair_citations": "repair_citations",
                "end": END,
            },
        )
        builder.add_edge("repair_citations", "validate")
        return builder.compile(checkpointer=self._checkpointer)

    def _prepare_turn(self, state: AgentState) -> dict[str, Any]:
        memory_update = capture_memory(state)
        retrieval_query = _build_retrieval_query(state.get("messages", ()))
        retrieval = self.retriever.retrieve(retrieval_query)
        evidence = [
            EvidenceState(
                citation_id=match.section.citation_id,
                title=match.section.title,
                page_number=match.section.page_number,
                score=match.score,
                text=match.section.text,
            )
            for match in retrieval.matches
        ]
        return {
            **memory_update,
            "retrieval_query": retrieval_query,
            "retrieved_sections": evidence,
            "tool_iterations": 0,
            "tool_trace": [],
            "final_answer": "",
            "citations": [],
            "status": "processing",
            "validation_attempts": 0,
            "validation_reason": "",
        }

    def _call_agent(self, state: AgentState) -> dict[str, Any]:
        prompt = _system_prompt(
            state.get("retrieved_sections", ()),
            state.get("user_name") or None,
        )
        response = self._model.invoke(
            [
                SystemMessage(content=prompt),
                *state.get("messages", ()),
            ]
        )
        if not isinstance(response, AIMessage):
            raise AgentExecutionError(
                "The configured model returned an unsupported message."
            )
        return {"messages": [response]}

    def _execute_tools(self, state: AgentState) -> dict[str, Any]:
        result = self._tool_node.invoke(
            {"messages": state.get("messages", ())}
        )
        tool_messages = [
            message
            for message in result.get("messages", ())
            if isinstance(message, ToolMessage)
        ]
        latest_agent_message = _latest_ai_message(state.get("messages", ()))
        calls_by_id = {
            call.get("id", ""): call
            for call in latest_agent_message.tool_calls
        }
        events = list(state.get("tool_trace", ()))
        for message in tool_messages:
            call = calls_by_id.get(message.tool_call_id, {})
            result_text = _message_content(message)
            events.append(
                ToolEventState(
                    name=str(call.get("name") or message.name or "unknown"),
                    arguments=dict(call.get("args") or {}),
                    result=result_text,
                    status=_tool_result_status(result_text),
                )
            )
        return {
            "messages": tool_messages,
            "tool_iterations": int(state.get("tool_iterations", 0)) + 1,
            "tool_trace": events,
        }

    def _route_after_agent(self, state: AgentState) -> str:
        message = _latest_ai_message(state.get("messages", ()))
        if not message.tool_calls:
            return "validate"
        if int(state.get("tool_iterations", 0)) >= MAX_TOOL_ITERATIONS:
            return "tool_limit"
        return "tools"

    def _tool_limit(self, state: AgentState) -> dict[str, Any]:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I could not complete this request within the "
                        "two-tool safety limit. Please simplify the question."
                    )
                )
            ],
            "status": "tool_limit_reached",
        }

    def _validate_answer(self, state: AgentState) -> dict[str, Any]:
        final_message = _latest_ai_message(state.get("messages", ()))
        answer = _message_content(final_message).strip()
        evidence_ids = {
            item["citation_id"]
            for item in state.get("retrieved_sections", ())
        }
        citations = list(dict.fromkeys(CITATION_PATTERN.findall(answer)))
        invalid_citations = set(citations) - evidence_ids
        user_query = _latest_human_text(state.get("messages", ()))
        tool_trace = state.get("tool_trace", ())
        blocked_reason = ""

        if not answer:
            blocked_reason = "The model returned an empty answer."
        elif invalid_citations:
            blocked_reason = "The answer cited evidence that was not retrieved."
        elif (
            evidence_ids
            and not citations
            and not _is_social_or_memory_query(user_query)
        ):
            blocked_reason = "The policy answer did not cite its evidence."
        elif (
            not evidence_ids
            and not tool_trace
            and not _is_social_or_memory_query(user_query)
            and not _is_grounded_refusal(answer)
        ):
            blocked_reason = "The answer was not supported by policy evidence."

        status = state.get("status", "answer_ready")
        if blocked_reason:
            if (
                evidence_ids
                and int(state.get("validation_attempts", 0)) < 1
                and status != "tool_limit_reached"
            ):
                return {
                    "status": "citation_repair_required",
                    "validation_attempts": 1,
                    "validation_reason": blocked_reason,
                }
            answer = (
                "I could not verify a grounded answer from the Nimbus Travel "
                "and Expense Policy. Please rephrase the question or provide "
                "the missing travel details."
            )
            citations = []
            status = "grounding_blocked"
            replacement = AIMessage(
                id=final_message.id,
                content=answer,
            )
            return {
                "messages": [replacement],
                "final_answer": answer,
                "citations": citations,
                "status": status,
                "validation_reason": blocked_reason,
            }

        if status == "processing":
            status = "answer_ready"
        return {
            "final_answer": answer,
            "citations": citations,
            "status": status,
            "validation_reason": "",
        }

    def _route_after_validation(self, state: AgentState) -> str:
        if state.get("status") == "citation_repair_required":
            return "repair_citations"
        return "end"

    def _repair_citations(self, state: AgentState) -> dict[str, Any]:
        final_message = _latest_ai_message(state.get("messages", ()))
        evidence = state.get("retrieved_sections", ())
        evidence_text = "\n\n".join(
            f"[{item['citation_id']}] {item['title']}\n{item['text']}"
            for item in evidence
        )
        response = self._base_model.invoke(
            [
                SystemMessage(
                    content=(
                        "Repair the draft answer using only the supplied "
                        "Nimbus policy evidence. Preserve useful content, "
                        "remove unsupported claims, and cite every policy "
                        "claim with one or more exact evidence IDs. Return "
                        "only the corrected user-facing answer and do not "
                        "call tools or describe your reasoning.\n\n"
                        f"POLICY EVIDENCE\n{evidence_text}"
                    )
                ),
                HumanMessage(
                    content=(
                        "Draft answer to repair:\n"
                        f"{_message_content(final_message)}"
                    )
                ),
            ]
        )
        if not isinstance(response, AIMessage):
            raise AgentExecutionError(
                "The configured model returned an unsupported repair message."
            )
        replacement = AIMessage(
            id=final_message.id,
            content=_message_content(response),
        )
        return {
            "messages": [replacement],
            "status": "processing",
        }

    def _response_from_state(
        self,
        thread_id: str,
        state: dict[str, Any],
        *,
        request_id: str,
        latency_ms: int,
    ) -> AgentResponse:
        return AgentResponse(
            request_id=request_id,
            thread_id=thread_id,
            status=state.get("status", "answer_ready"),
            answer=state.get("final_answer", ""),
            citations=tuple(state.get("citations", ())),
            remembered_name=state.get("user_name") or None,
            turn_count=int(state.get("turn_count", 0)),
            retrieved_sections=tuple(
                EvidenceReference(
                    citation_id=item["citation_id"],
                    title=item["title"],
                    page_number=int(item["page_number"]),
                    score=float(item["score"]),
                )
                for item in state.get("retrieved_sections", ())
            ),
            tool_events=tuple(
                ToolEvent(
                    name=item["name"],
                    arguments=dict(item["arguments"]),
                    result=item["result"],
                    status=item["status"],
                )
                for item in state.get("tool_trace", ())
            ),
            provider=self.config.provider,
            model=self.config.model,
            latency_ms=latency_ms,
        )

    def _lock_for_thread(self, thread_id: str) -> threading.Lock:
        with self._thread_locks_guard:
            return self._thread_locks.setdefault(
                thread_id,
                threading.Lock(),
            )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Document agent is closed.")


def _normalize_database_path(database_path: Path | str) -> str:
    if str(database_path) == ":memory:":
        return ":memory:"
    return str(Path(database_path).expanduser().resolve())


def _build_retrieval_query(messages: Any) -> str:
    user_messages = [
        message.content
        for message in messages
        if isinstance(message, HumanMessage)
        and isinstance(message.content, str)
    ]
    return " ".join(user_messages[-2:]).strip()


def _system_prompt(
    evidence: Any,
    remembered_name: str | None,
) -> str:
    if evidence:
        evidence_text = "\n\n".join(
            f"[{item['citation_id']}] {item['title']}\n{item['text']}"
            for item in evidence
        )
    else:
        evidence_text = "No relevant policy section was retrieved."
    memory_text = (
        f"The remembered user name is {remembered_name}."
        if remembered_name
        else "No user name has been remembered yet."
    )
    return (
        "You are the Nimbus Travel and Expense Policy agent. "
        "The supplied policy evidence is the only source for policy claims. "
        "Every policy claim must cite its supporting section using the exact "
        "format [P1:S3]. Use only citation IDs shown below. If the evidence "
        "does not answer the question, say that the policy document does not "
        "provide the information. "
        f"{memory_text} You may use remembered conversation context for "
        "follow-up questions. Use calculator only when arithmetic is needed; "
        "never call it for a direct lookup. Use date_tool only for today's "
        "date or date arithmetic. Ask for missing quantities or dates instead "
        "of inventing them. Do not reveal hidden reasoning.\n\n"
        f"POLICY EVIDENCE\n{evidence_text}"
    )


def _latest_ai_message(messages: Any) -> AIMessage:
    for message in reversed(tuple(messages)):
        if isinstance(message, AIMessage):
            return message
    raise AgentExecutionError("The model did not produce an assistant message.")


def _latest_human_text(messages: Any) -> str:
    for message in reversed(tuple(messages)):
        if isinstance(message, HumanMessage) and isinstance(
            message.content,
            str,
        ):
            return message.content
    return ""


def _message_content(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    return json.dumps(
        message.content,
        ensure_ascii=True,
        sort_keys=True,
    )


def _tool_result_status(result: str) -> str:
    try:
        value = json.loads(result)
    except json.JSONDecodeError:
        return "unknown"
    return str(value.get("status", "unknown"))


def _is_social_or_memory_query(query: str) -> bool:
    normalized = re.sub(r"\s+", " ", query).strip().casefold()
    return any(pattern.search(normalized) for pattern in SOCIAL_OR_MEMORY_PATTERNS)


def _is_grounded_refusal(answer: str) -> bool:
    normalized = answer.casefold()
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def _safe_execution_error(exc: Exception) -> str:
    text = str(exc).casefold()
    if "401" in text or "authentication" in text or "api key" in text:
        return "DeepSeek authentication failed. Check DEEPSEEK_API_KEY."
    if "429" in text or "rate limit" in text:
        return "DeepSeek rate limit reached. Please retry shortly."
    if "timeout" in text or "timed out" in text:
        return "DeepSeek request timed out. Please retry."
    if isinstance(exc, AgentExecutionError):
        return str(exc)
    return "The document agent could not complete the request."
