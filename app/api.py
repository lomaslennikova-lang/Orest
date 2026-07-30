from __future__ import annotations

import base64
import asyncio
import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, or_, select

from app.ai_chat.graph import AIChatCheckpointError, open_chat_graph, run_chat_turn
from app.ai_chat.rate_limit import ChatRateLimiter
from app.ai_chat.repository import (
    add_message,
    create_conversation,
    get_last_owned_conversation,
    get_owned_conversation,
    get_recent_messages,
)
from app.ai_chat.schemas import ChatMessageCreate, ChatMessageView, ChatRequest, ChatResponse, ConversationView
from app.database import AsyncSessionLocal, check_database_connection, init_database
from app.llm import LLMRequestError, analyze_transactions
from app.models import Category, Transaction, User


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await check_database_connection()
    await init_database()
    app.state.ai_chat_rate_limiter = ChatRateLimiter()
    async with open_chat_graph() as graph:
        app.state.ai_chat_graph = graph
        yield


app = FastAPI(title="Orest Admin API", lifespan=lifespan)
SESSION_COOKIE_NAME = "orest_admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 8

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class TransactionCreateRequest(BaseModel):
    created_at: datetime
    amount: Decimal
    category: str
    type: str


class TransactionAnalysisRequest(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    transaction_type: Literal["income", "expense"] | None = None
    user: str | None = Field(default=None, max_length=255)


class FinancialAnalysisResponse(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    top_expense_categories: list[str] = Field(max_length=5)
    risks: list[str] = Field(max_length=10)
    advice: list[str] = Field(min_length=3, max_length=3)


def to_float(value: Decimal | None) -> float:
    return float(value or Decimal("0.00"))


def get_auth_settings() -> tuple[str, str, str]:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD")
    session_secret = os.getenv("ADMIN_SESSION_SECRET")

    if not password or not session_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured.",
        )

    return username, password, session_secret


def encode_session(payload: dict[str, object], session_secret: str) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    payload_token = base64.urlsafe_b64encode(payload_json).decode().rstrip("=")
    signature = hmac.new(
        session_secret.encode(),
        payload_token.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_token}.{signature}"


def decode_session(token: str, session_secret: str) -> dict[str, object] | None:
    try:
        payload_token, signature = token.split(".", maxsplit=1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        session_secret.encode(),
        payload_token.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return None

    padding = "=" * (-len(payload_token) % 4)
    try:
        payload_json = base64.urlsafe_b64decode(f"{payload_token}{padding}")
        payload = json.loads(payload_json)
    except (ValueError, json.JSONDecodeError):
        return None

    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        return None

    return payload


def require_admin(request: Request) -> dict[str, object]:
    username, _password, session_secret = get_auth_settings()
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    session = decode_session(token, session_secret)
    if not session or session.get("username") != username or session.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return session


def get_admin_telegram_id(username: str) -> int:
    digest = hashlib.sha256(username.encode()).hexdigest()
    return -int(digest[:15], 16)


def serialize_transaction(row) -> dict[str, object]:
    amount = Decimal(row.amount or 0)
    return {
        "id": row.id,
        "amount": to_float(amount.copy_abs()),
        "category": row.category,
        "type": row.transaction_type,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "user": row.username or row.first_name or "unknown",
    }


def build_analysis_data(rows) -> dict[str, object]:
    """Aggregate database rows before sending financial data to Gemini."""
    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")
    expense_categories: dict[str, Decimal] = {}
    transaction_dates = [row.created_at.date() for row in rows if row.created_at]

    for row in rows:
        amount = Decimal(row.amount or 0).copy_abs()
        if row.transaction_type == "income":
            total_income += amount
            continue

        total_expense += amount
        expense_categories[row.category] = expense_categories.get(
            row.category,
            Decimal("0.00"),
        ) + amount

    categories = sorted(
        expense_categories.items(),
        key=lambda category: category[1],
        reverse=True,
    )
    return {
        "currency": "UAH",
        "transactions_count": len(rows),
        "period": {
            "from": min(transaction_dates).isoformat() if transaction_dates else None,
            "to": max(transaction_dates).isoformat() if transaction_dates else None,
        },
        "total_income": to_float(total_income),
        "total_expense": to_float(total_expense),
        "balance": to_float(total_income - total_expense),
        "expense_categories": [
            {"category": category, "amount": to_float(amount)}
            for category, amount in categories
        ],
    }


async def get_or_create_admin_user(session, username: str) -> User:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User is required.",
        )

    result = await session.execute(
        select(User).where(
            or_(
                User.username == normalized_username,
                User.first_name == normalized_username,
            )
        )
    )
    user = result.scalars().first()

    if user:
        return user

    user = User(
        telegram_id=get_admin_telegram_id(normalized_username),
        username=normalized_username,
        first_name=normalized_username,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_admin_category(
    session,
    user: User,
    category_name: str,
) -> Category:
    normalized_category = category_name.strip().lower()
    if not normalized_category:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category is required.",
        )

    result = await session.execute(
        select(Category).where(
            Category.user_id == user.id,
            Category.name == normalized_category,
        )
    )
    category = result.scalar_one_or_none()

    if category:
        return category

    category = Category(user_id=user.id, name=normalized_category)
    session.add(category)
    await session.flush()
    return category


def validate_transaction_payload(payload: TransactionCreateRequest) -> None:
    current_datetime = datetime.now(payload.created_at.tzinfo)
    if payload.created_at > current_datetime:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transaction date and time cannot be later than now.",
        )

    if payload.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Amount must be greater than zero.",
        )

    if payload.amount > Decimal("100000"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Amount cannot exceed 100000 UAH.",
        )

    if payload.type not in {"income", "expense"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transaction type must be income or expense.",
        )


@app.get("/health")
async def health() -> dict[str, str]:
    await check_database_connection()
    return {"status": "ok"}


@app.post("/api/login")
async def login(credentials: LoginRequest, response: Response) -> dict[str, str]:
    username, password, session_secret = get_auth_settings()

    valid_username = hmac.compare_digest(credentials.username, username)
    valid_password = hmac.compare_digest(credentials.password, password)

    if not valid_username or not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    session = {
        "username": username,
        "role": "admin",
        "expires_at": int(time.time()) + SESSION_TTL_SECONDS,
    }
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=encode_session(session, session_secret),
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return {"username": username, "role": "admin"}


@app.post("/api/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "ok"}


@app.get("/api/me")
async def me(session: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return {
        "username": session["username"],
        "role": session["role"],
    }


def serialize_chat_message(message) -> ChatMessageView:
    return ChatMessageView(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        tool_name=message.tool_name,
        tool_call_id=message.tool_call_id,
        status=message.status,
        created_at=message.created_at,
    )


def serialize_conversation(conversation) -> ConversationView:
    return ConversationView(
        id=conversation.id,
        owner_user_id=conversation.owner_user_id,
        title=conversation.title,
        updated_at=conversation.updated_at,
    )


async def get_admin_chat_user(session, admin_session: dict[str, object]) -> User:
    return await get_or_create_admin_user(session, str(admin_session["username"]))


@app.post("/api/ai/chat", response_model=ChatResponse)
async def ai_chat(
    payload: ChatRequest,
    request: Request,
    admin_session: dict[str, object] = Depends(require_admin),
) -> ChatResponse:
    """Persist a user message, run its durable graph thread, and save the answer."""

    retry_after = await request.app.state.ai_chat_rate_limiter.consume(
        str(admin_session["username"]),
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Забагато запитів до AI-помічника. Спробуйте ще раз трохи згодом.",
            headers={"Retry-After": str(retry_after)},
        )

    async with AsyncSessionLocal() as session:
        admin_user = await get_admin_chat_user(session, admin_session)
        if payload.conversation_id:
            conversation = await get_owned_conversation(
                session,
                conversation_id=payload.conversation_id,
                owner_user_id=admin_user.id,
            )
            if not conversation:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
        else:
            conversation = await get_last_owned_conversation(
                session,
                owner_user_id=admin_user.id,
            )
            if not conversation:
                conversation = await create_conversation(
                    session,
                    owner_user_id=admin_user.id,
                )

        await add_message(
            session,
            conversation=conversation,
            payload=ChatMessageCreate(role="user", content=payload.message),
        )
        conversation_id = conversation.id
        await session.commit()

    try:
        answer = await run_chat_turn(request.app.state.ai_chat_graph, conversation_id, payload.message)
    except AIChatCheckpointError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сховище діалогу тимчасово недоступне. Спробуйте ще раз за кілька секунд.",
        ) from error

    async with AsyncSessionLocal() as session:
        conversation = await get_owned_conversation(
            session,
            conversation_id=conversation_id,
            owner_user_id=admin_user.id,
        )
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
        assistant_message = await add_message(
            session,
            conversation=conversation,
            payload=ChatMessageCreate(role="assistant", content=answer),
        )
        await session.commit()
        await session.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation_id,
        message=serialize_chat_message(assistant_message),
    )


@app.get("/api/ai/conversations/last", response_model=ConversationView)
async def last_ai_conversation(
    admin_session: dict[str, object] = Depends(require_admin),
) -> ConversationView:
    async with AsyncSessionLocal() as session:
        admin_user = await get_admin_chat_user(session, admin_session)
        conversation = await get_last_owned_conversation(
            session,
            owner_user_id=admin_user.id,
        )
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
        return serialize_conversation(conversation)


@app.get(
    "/api/ai/conversations/{conversation_id}/messages",
    response_model=list[ChatMessageView],
)
async def ai_conversation_messages(
    conversation_id: UUID,
    limit: int = 50,
    admin_session: dict[str, object] = Depends(require_admin),
) -> list[ChatMessageView]:
    if not 1 <= limit <= 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 50.",
        )

    async with AsyncSessionLocal() as session:
        admin_user = await get_admin_chat_user(session, admin_session)
        conversation = await get_owned_conversation(
            session,
            conversation_id=conversation_id,
            owner_user_id=admin_user.id,
        )
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
        messages = await get_recent_messages(
            session,
            conversation_id=conversation.id,
            limit=limit,
        )

    return [
        serialize_chat_message(message)
        for message in messages
        if message.role in {"user", "assistant"}
    ]


@app.get("/api/transactions")
async def transactions(
    _session: dict[str, object] = Depends(require_admin),
) -> list[dict[str, object]]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                Transaction.id,
                Transaction.amount,
                Transaction.transaction_type,
                Transaction.created_at,
                Category.name.label("category"),
                User.username,
                User.first_name,
            )
            .join(Category, Transaction.category_id == Category.id)
            .join(User, Transaction.user_id == User.id)
            .order_by(Transaction.created_at.desc())
        )

        rows = result.all()

    return [serialize_transaction(row) for row in rows]


@app.post(
    "/api/ai/analyze-transactions",
    response_model=FinancialAnalysisResponse,
)
async def analyze_financial_transactions(
    filters: TransactionAnalysisRequest | None = None,
    _session: dict[str, object] = Depends(require_admin),
) -> FinancialAnalysisResponse:
    """Generate an AI financial overview from the selected database records."""
    filters = filters or TransactionAnalysisRequest()
    query = (
        select(
            Transaction.amount,
            Transaction.transaction_type,
            Transaction.created_at,
            Category.name.label("category"),
        )
        .join(Category, Transaction.category_id == Category.id)
        .join(User, Transaction.user_id == User.id)
    )

    if filters.date_from:
        query = query.where(Transaction.created_at >= filters.date_from)
    if filters.date_to:
        query = query.where(func.date(Transaction.created_at) <= filters.date_to)
    if filters.transaction_type:
        query = query.where(Transaction.transaction_type == filters.transaction_type)
    if filters.user:
        query = query.where(
            or_(
                User.username == filters.user,
                User.first_name == filters.user,
            )
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(query.order_by(Transaction.created_at.desc()))
        rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No transactions match the selected filters.",
        )

    if not any(row.transaction_type == "expense" for row in rows):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one expense transaction is required for financial analysis.",
        )

    try:
        analysis = await asyncio.to_thread(analyze_transactions, build_analysis_data(rows))
        return FinancialAnalysisResponse.model_validate(analysis)
    except LLMRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned an unexpected analysis format.",
        ) from error


@app.post("/api/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreateRequest,
    admin_session: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    validate_transaction_payload(payload)
    created_at = payload.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        user = await get_or_create_admin_user(session, str(admin_session["username"]))
        category = await get_or_create_admin_category(session, user, payload.category)
        transaction = Transaction(
            user_id=user.id,
            category_id=category.id,
            amount=payload.amount.quantize(Decimal("0.01")),
            transaction_type=payload.type,
            created_at=created_at,
        )
        session.add(transaction)
        await session.flush()
        transaction_id = transaction.id
        await session.commit()

    return {"status": "created", "id": transaction_id}


@app.delete("/api/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    _session: dict[str, object] = Depends(require_admin),
) -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )

        await session.delete(transaction)
        await session.commit()

    return {"status": "deleted"}


@app.get("/api/summary")
async def summary(
    _session: dict[str, object] = Depends(require_admin),
) -> dict[str, float]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Transaction.amount, Transaction.transaction_type)
        )
        rows = result.all()

    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")

    for row in rows:
        amount = Decimal(row.amount or 0).copy_abs()
        if row.transaction_type == "income":
            total_income += amount
        else:
            total_expense += amount

    balance = total_income - total_expense

    return {
        "total_income": to_float(total_income),
        "total_expense": to_float(total_expense),
        "balance": to_float(balance),
    }
