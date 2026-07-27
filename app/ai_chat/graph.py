"""LangGraph workflow for a bounded Gemini → tool → Gemini conversation turn."""

from __future__ import annotations

import operator
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator, TypedDict
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.ai_chat.gemini import AIChatLLMError, GeminiToolCall, generate_chat_turn
from app.ai_chat.tools import FINANCIAL_TOOLS
from app.database import AsyncSessionLocal, DATABASE_URL


MAX_TOOL_STEPS = 4
SAFE_FAILURE_RESPONSE = (
    "Не вдалося завершити аналіз. Спробуйте, будь ласка, сформулювати запит коротше "
    "або уточнити період."
)


class ChatGraphState(TypedDict, total=False):
    """Persisted LangGraph state; contents use append-only message semantics."""

    contents: Annotated[list[dict[str, Any]], operator.add]
    tool_calls: list[GeminiToolCall]
    tool_steps: int
    response: str


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
        return {"response": SAFE_FAILURE_RESPONSE, "tool_calls": []}

    return {
        "contents": [turn.content],
        "tool_calls": turn.tool_calls,
        "response": turn.text,
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
        {"tools": "tools", "limit": "tool_limit", "end": END},
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

    async with AsyncPostgresSaver.from_conn_string(_checkpointer_url()) as checkpointer:
        await checkpointer.setup()
        yield build_chat_graph(checkpointer)


async def run_chat_turn(graph: Any, conversation_id: UUID, message: str) -> str:
    """Run one bounded chat turn; the UUID is the durable LangGraph thread ID."""

    result = await graph.ainvoke(
        {
            "contents": [{"role": "user", "parts": [{"text": message}]}],
            "tool_steps": 0,
            "tool_calls": [],
            "response": "",
        },
        {"configurable": {"thread_id": str(conversation_id)}},
    )
    response = result.get("response", "").strip()
    return response or SAFE_FAILURE_RESPONSE
