"""LangGraph workflow for a bounded Gemini → tool → Gemini conversation turn."""

from __future__ import annotations

import asyncio
import operator
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator, TypedDict
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from psycopg import Error as PsycopgError
from psycopg_pool import AsyncConnectionPool

from app.ai_chat.gemini import AIChatLLMError, GeminiToolCall, generate_chat_turn
from app.ai_chat.tools import FINANCIAL_TOOLS
from app.database import AsyncSessionLocal, DATABASE_URL


MAX_TOOL_STEPS = 4
SAFE_FAILURE_RESPONSE = (
    "Не вдалося завершити аналіз. Спробуйте, будь ласка, сформулювати запит коротше "
    "або уточнити період."
)


class AIChatCheckpointError(RuntimeError):
    """Raised when PostgreSQL checkpoint storage stays unavailable after a retry."""


class AIChatProviderError(RuntimeError):
    """Raised when Gemini exhausts the bounded retry budget for a chat turn."""


class ChatGraphState(TypedDict, total=False):
    """Persisted LangGraph state; contents use append-only message semantics."""

    contents: Annotated[list[dict[str, Any]], operator.add]
    tool_calls: list[GeminiToolCall]
    tool_steps: int
    response: str
    provider_unavailable: bool


def _tool_response_part(call: GeminiToolCall, response: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "user",
        "parts": [
            {
                "functionResponse": {
                    "name": call.name,
                    "response": response,
                }
            }
        ],
    }


async def assistant_node(state: ChatGraphState) -> ChatGraphState:
    try:
        turn = await generate_chat_turn(state.get("contents", []))
    except AIChatLLMError:
        return {"response": "", "tool_calls": [], "provider_unavailable": True}

    return {
        "contents": [turn.content],
        "tool_calls": turn.tool_calls,
        "response": turn.text,
        "provider_unavailable": False,
    }


async def tools_node(state: ChatGraphState) -> ChatGraphState:
    response_contents: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as session:
        for call in state.get("tool_calls", []):
            tool = FINANCIAL_TOOLS.get(call.name)
            if tool is None:
                response_contents.append(
                    _tool_response_part(call, {"error": {"code": "unknown_tool"}}),
                )
                continue
            try:
                params = tool.parameters_model.model_validate(call.arguments)
                result = await tool.handler(session, params)
            except ValidationError:
                response_contents.append(
                    _tool_response_part(call, {"error": {"code": "invalid_arguments"}}),
                )
                continue
            except Exception:
                response_contents.append(
                    _tool_response_part(call, {"error": {"code": "data_unavailable"}}),
                )
                continue
            response_contents.append(_tool_response_part(call, {"result": result}))

    return {
        "contents": response_contents,
        "tool_calls": [],
        "tool_steps": state.get("tool_steps", 0) + 1,
    }


def route_after_assistant(state: ChatGraphState) -> str:
    if state.get("provider_unavailable"):
        return "provider_error"
    if not state.get("tool_calls"):
        return "end"
    if state.get("tool_steps", 0) >= MAX_TOOL_STEPS:
        return "limit"
    return "tools"


def tool_limit_node(_state: ChatGraphState) -> ChatGraphState:
    return {"response": SAFE_FAILURE_RESPONSE, "tool_calls": []}


def build_chat_graph(checkpointer: AsyncPostgresSaver):
    builder = StateGraph(ChatGraphState)
    builder.add_node("assistant", assistant_node)
    builder.add_node("tools", tools_node)
    builder.add_node("tool_limit", tool_limit_node)
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant",
        route_after_assistant,
        {"tools": "tools", "limit": "tool_limit", "provider_error": END, "end": END},
    )
    builder.add_edge("tools", "assistant")
    builder.add_edge("tool_limit", END)
    return builder.compile(checkpointer=checkpointer)


def _checkpointer_url() -> str:
    """Convert the app's asyncpg URL to the psycopg URL used by LangGraph."""

    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def open_chat_graph() -> AsyncIterator[Any]:
    """Open and initialise the durable PostgreSQL checkpointer for the app lifespan."""

    # A pool lets LangGraph acquire a fresh healthy connection for every
    # checkpoint operation.  Holding one AsyncConnection here is fragile in
    # development: uvicorn reloads and an idle managed PostgreSQL connection
    # can leave that long-lived connection closed.
    pool = AsyncConnectionPool(
        conninfo=_checkpointer_url(),
        kwargs={"autocommit": True},
        min_size=1,
        max_size=5,
        open=False,
    )
    await pool.open()
    try:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        yield build_chat_graph(checkpointer)
    finally:
        await pool.close()


async def run_chat_turn(graph: Any, conversation_id: UUID, message: str) -> str:
    """Run one bounded chat turn; the UUID is the durable LangGraph thread ID."""

    graph_input = {
        "contents": [{"role": "user", "parts": [{"text": message}]}],
        "tool_steps": 0,
        "tool_calls": [],
        "response": "",
        "provider_unavailable": False,
    }
    graph_config = {"configurable": {"thread_id": str(conversation_id)}}

    for attempt in range(2):
        try:
            result = await graph.ainvoke(graph_input, graph_config)
            break
        except PsycopgError as error:
            if attempt:
                raise AIChatCheckpointError from error
            # Managed PostgreSQL may replace an idle connection.  The pool
            # discards it; repeating once lets the next checkout use a new one.
            await asyncio.sleep(0.2)

    if result.get("provider_unavailable"):
        raise AIChatProviderError("Gemini is temporarily unavailable.")

    response = result.get("response", "").strip()
    return response or SAFE_FAILURE_RESPONSE
