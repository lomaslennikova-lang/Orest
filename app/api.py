from __future__ import annotations

import base64
import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, or_, select

from app.ai_actions.audit import AuditLogWriter
from app.ai_actions.pending import (
    PendingActionError,
    PendingActionExpiredError,
    PendingActionNotFoundError,
    PendingActionStateError,
    ClarificationActionDraft,
    ExpenseActionDraft,
    cancel_pending_action,
    confirm_pending_action,
    create_clarification_action,
    create_pending_expense_action,
    expire_open_actions_for_new_message,
    update_pending_action_draft,
)
from app.ai_actions.receipt_llm import ReceiptDraftLLMError, analyse_receipt_to_draft
from app.ai_actions.receipts import MAX_RECEIPT_BYTES, ReceiptStorageRouter, ReceiptValidationError
from app.ai_actions.runtime import ensure_ai_runtime_directories, get_ai_runtime_settings
from app.ai_actions.schemas import (
    ActionCancelResponse,
    ActionConfirmResponse,
    PendingActionView,
    PendingDraftUpdate,
    ReceiptAttachmentView,
)
from app.ai_actions.transactions import (
    TransactionCreateData,
    TransactionValidationError,
    create_transaction_for_user,
    get_or_create_user_by_name,
    normalise_transaction_data,
)
from app.ai_chat.graph import AIChatCheckpointError, AIChatProviderError, open_chat_graph, run_chat_turn
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
from app.models import AIPendingAction, AIReceiptAttachment, Category, Transaction, User
from app.google_drive import (
    GoogleDriveConfigurationError,
    GoogleDriveOAuthError,
    build_authorization_url,
    exchange_code,
    get_google_drive_settings,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await check_database_connection()
    await init_database()
    ai_runtime_settings = get_ai_runtime_settings()
    ensure_ai_runtime_directories(ai_runtime_settings)
    app.state.ai_runtime_settings = ai_runtime_settings
    app.state.receipt_storage = ReceiptStorageRouter(ai_runtime_settings)
    app.state.ai_chat_rate_limiter = ChatRateLimiter()
    async with open_chat_graph() as graph:
        app.state.ai_chat_graph = graph
        yield


app = FastAPI(title="Orest Admin API", lifespan=lifespan)
SESSION_COOKIE_NAME = "orest_admin_session"
GOOGLE_OAUTH_STATE_COOKIE_NAME = "orest_google_oauth_state"
SESSION_TTL_SECONDS = 60 * 60 * 8
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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


def use_secure_session_cookie() -> bool:
    """Enable Secure cookies only when the deployment explicitly requests it."""

    return os.getenv("ADMIN_SESSION_COOKIE_SECURE", "false").lower() in {
        "1",
        "true",
        "yes",
    }


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
    try:
        return await get_or_create_user_by_name(session, username)
    except TransactionValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


def validate_transaction_payload(payload: TransactionCreateRequest) -> None:
    try:
        normalise_transaction_data(
            TransactionCreateData(
                created_at=payload.created_at,
                amount=payload.amount,
                category=payload.category,
                transaction_type=payload.type,
            )
        )
    except TransactionValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


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
        secure=use_secure_session_cookie(),
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


def serialize_receipt_attachment(attachment: AIReceiptAttachment) -> ReceiptAttachmentView:
    return ReceiptAttachmentView(
        id=attachment.id,
        filename=attachment.original_filename,
        media_type=attachment.media_type,
        byte_size=attachment.byte_size,
        created_at=attachment.created_at,
        expires_at=attachment.expires_at,
    )


def serialize_pending_action(action: AIPendingAction) -> PendingActionView:
    execution_result = action.execution_result or {}
    transaction_ids = execution_result.get("created_transaction_ids")
    return PendingActionView(
        id=action.id,
        conversation_id=action.conversation_id,
        status=action.status,
        draft_payload=action.draft_payload,
        expires_at=action.expires_at,
        completed_at=action.completed_at,
        created_transaction_ids=transaction_ids if isinstance(transaction_ids, list) else None,
    )


async def get_admin_chat_user(session, admin_session: dict[str, object]) -> User:
    return await get_or_create_admin_user(session, str(admin_session["username"]))


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _pending_action_http_error(error: PendingActionError) -> HTTPException:
    if isinstance(error, PendingActionNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чернетку не знайдено.")
    if isinstance(error, PendingActionExpiredError):
        return HTTPException(status_code=status.HTTP_410_GONE, detail="Строк дії чернетки минув.")
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Чернетка вже оброблена або недоступна для цієї дії.",
    )


@app.post("/api/ai/attachments", response_model=ReceiptAttachmentView, status_code=status.HTTP_201_CREATED)
async def upload_ai_receipt(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    admin_session: dict[str, object] = Depends(require_admin),
) -> ReceiptAttachmentView:
    """Store one bounded receipt file privately for the authenticated Admin."""

    _no_store(response)
    filename = file.filename or "receipt"
    content = await file.read(MAX_RECEIPT_BYTES + 1)
    await file.close()
    if len(content) > MAX_RECEIPT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Розмір файла чеку не може перевищувати 5 МіБ.",
        )

    storage = request.app.state.receipt_storage
    try:
        stored = await asyncio.to_thread(storage.store, content, filename)
    except ReceiptValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    try:
        async with AsyncSessionLocal() as session:
            admin_user = await get_admin_chat_user(session, admin_session)
            attachment = AIReceiptAttachment(
                owner_user_id=admin_user.id,
                original_filename=stored.original_filename,
                media_type=stored.media_type,
                byte_size=stored.byte_size,
                content_sha256=stored.content_sha256,
                storage_key=stored.storage_key,
                storage_backend="google_drive" if stored.drive_file_id else "local",
                drive_file_id=stored.drive_file_id,
                expires_at=stored.stored_at
                + timedelta(days=request.app.state.ai_runtime_settings.receipt_retention_days),
            )
            session.add(attachment)
            await session.commit()
            await session.refresh(attachment)
    except Exception:
        await asyncio.to_thread(storage.delete, stored.storage_key, stored.drive_file_id)
        raise

    return serialize_receipt_attachment(attachment)


@app.get("/api/ai/actions/{action_id}", response_model=PendingActionView)
async def get_ai_action(
    action_id: UUID,
    response: Response,
    admin_session: dict[str, object] = Depends(require_admin),
) -> PendingActionView:
    """Return only an action owned by the current Admin session."""

    _no_store(response)
    async with AsyncSessionLocal() as session:
        admin_user = await get_admin_chat_user(session, admin_session)
        action = await session.scalar(
            select(AIPendingAction).where(
                AIPendingAction.id == action_id,
                AIPendingAction.owner_user_id == admin_user.id,
            )
        )
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чернетку не знайдено.")
        return serialize_pending_action(action)


@app.put("/api/ai/actions/{action_id}/draft", response_model=PendingActionView)
async def update_ai_action_draft(
    action_id: UUID,
    payload: PendingDraftUpdate,
    admin_session: dict[str, object] = Depends(require_admin),
) -> PendingActionView:
    action_error: PendingActionError | None = None
    action = None
    async with AsyncSessionLocal() as session:
        async with session.begin():
            admin_user = await get_admin_chat_user(session, admin_session)
            draft = ExpenseActionDraft(
                transactions=[
                    {
                        "created_at": payload.operation_at,
                        "amount": row.amount,
                        "category": row.category,
                        "line_number": row.line_number,
                    }
                    for row in payload.rows
                ]
            )
            try:
                action = await update_pending_action_draft(
                    session,
                    action_id=action_id,
                    owner_user_id=admin_user.id,
                    draft=draft,
                )
            except (PendingActionNotFoundError, PendingActionExpiredError, PendingActionStateError) as error:
                # Keep an expired state written by the action service instead of
                # rolling it back by raising from inside the transaction.
                action_error = error
        if action_error:
            raise _pending_action_http_error(action_error)
    assert action is not None
    return serialize_pending_action(action)


@app.get("/api/ai/actions/{action_id}/receipt")
async def get_ai_action_receipt(
    action_id: UUID,
    request: Request,
    admin_session: dict[str, object] = Depends(require_admin),
) -> Response:
    async with AsyncSessionLocal() as session:
        admin_user = await get_admin_chat_user(session, admin_session)
        action = await session.scalar(
            select(AIPendingAction).where(
                AIPendingAction.id == action_id,
                AIPendingAction.owner_user_id == admin_user.id,
            )
        )
        if not action or not action.attachment_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек не знайдено.")
        attachment = await session.scalar(
            select(AIReceiptAttachment).where(
                AIReceiptAttachment.id == action.attachment_id,
                AIReceiptAttachment.owner_user_id == admin_user.id,
            )
        )
        if not attachment or attachment.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Строк зберігання чеку минув.")
        content = await asyncio.to_thread(
            request.app.state.receipt_storage.read,
            attachment.storage_key,
            attachment.drive_file_id,
        )
    return Response(
        content=content,
        media_type=attachment.media_type,
        headers={"Content-Disposition": f'inline; filename="{attachment.original_filename}"'},
    )


@app.post("/api/ai/actions/{action_id}/confirm", response_model=ActionConfirmResponse)
async def confirm_ai_action(
    action_id: UUID,
    request: Request,
    response: Response,
    admin_session: dict[str, object] = Depends(require_admin),
) -> ActionConfirmResponse:
    """Execute one owned draft; a repeated confirm returns its saved result."""

    _no_store(response)
    action_error: PendingActionError | None = None
    result = None
    async with AsyncSessionLocal() as session:
        async with session.begin():
            admin_user = await get_admin_chat_user(session, admin_session)
            try:
                result = await confirm_pending_action(
                    session,
                    action_id=action_id,
                    owner=admin_user,
                    audit_writer=AuditLogWriter(request.app.state.ai_runtime_settings),
                )
            except (PendingActionNotFoundError, PendingActionExpiredError, PendingActionStateError) as error:
                # The service can persist expired/failed state before raising.
                # Catching inside this transaction intentionally commits that state.
                action_error = error
        if action_error:
            raise _pending_action_http_error(action_error)

    assert result is not None
    return ActionConfirmResponse(
        id=result.action_id,
        status=result.status,
        created_transaction_ids=result.created_transaction_ids,
    )


@app.post("/api/ai/actions/{action_id}/cancel", response_model=ActionCancelResponse)
async def cancel_ai_action(
    action_id: UUID,
    response: Response,
    admin_session: dict[str, object] = Depends(require_admin),
) -> ActionCancelResponse:
    """Cancel one owned, not-yet-executed action."""

    _no_store(response)
    action_error: PendingActionError | None = None
    cancelled_action = None
    async with AsyncSessionLocal() as session:
        async with session.begin():
            admin_user = await get_admin_chat_user(session, admin_session)
            try:
                cancelled_action = await cancel_pending_action(
                    session,
                    action_id=action_id,
                    owner_user_id=admin_user.id,
                )
            except (PendingActionNotFoundError, PendingActionExpiredError, PendingActionStateError) as error:
                action_error = error
        if action_error:
            raise _pending_action_http_error(action_error)

    assert cancelled_action is not None
    return ActionCancelResponse(id=cancelled_action.id, status="cancelled")


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

    attachment_meta: tuple[str, str | None, str, str] | None = None
    action_attachment_id: UUID | None = payload.attachment_id
    is_clarification_retry = payload.clarification_action_id is not None
    admin_user_id: int
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

        if payload.clarification_action_id:
            clarification_action = await session.scalar(
                select(AIPendingAction).where(
                    AIPendingAction.id == payload.clarification_action_id,
                    AIPendingAction.conversation_id == conversation.id,
                    AIPendingAction.owner_user_id == admin_user.id,
                    AIPendingAction.status == "needs_clarification",
                )
            )
            if not clarification_action or not clarification_action.attachment_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Чернетка вже недоступна для уточнення.")
            action_attachment_id = clarification_action.attachment_id

        if action_attachment_id:
            attachment = await session.scalar(
                select(AIReceiptAttachment).where(
                    AIReceiptAttachment.id == action_attachment_id,
                    AIReceiptAttachment.owner_user_id == admin_user.id,
                )
            )
            if not attachment:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек не знайдено.")
            if attachment.expires_at <= datetime.now(timezone.utc):
                raise HTTPException(status_code=status.HTTP_410_GONE, detail="Строк зберігання чеку минув.")
            attachment_meta = (
                attachment.storage_key,
                attachment.drive_file_id,
                attachment.media_type,
                attachment.original_filename,
            )

        if not is_clarification_retry:
            await expire_open_actions_for_new_message(
                session,
                conversation_id=conversation.id,
                owner_user_id=admin_user.id,
            )

        await add_message(
            session,
            conversation=conversation,
            payload=ChatMessageCreate(role="user", content=payload.message),
        )
        conversation_id = conversation.id
        admin_user_id = admin_user.id
        await session.commit()

    pending_action = None
    if attachment_meta is not None and action_attachment_id is not None:
        storage_key, drive_file_id, media_type, filename = attachment_meta
        try:
            content = await asyncio.to_thread(
                request.app.state.receipt_storage.read,
                storage_key,
                drive_file_id,
            )
            receipt_turn = await analyse_receipt_to_draft(
                content=content,
                media_type=media_type,
                filename=filename,
                user_message=payload.message,
            )
        except (RuntimeError, ReceiptDraftLLMError) as error:
            logger.warning("Receipt analysis failed: %s", error)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не вдалося проаналізувати чек. Спробуйте ще раз трохи згодом.",
            ) from error

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        try:
            async with AsyncSessionLocal() as session:
                if is_clarification_retry:
                    await expire_open_actions_for_new_message(
                        session,
                        conversation_id=conversation_id,
                        owner_user_id=admin_user_id,
                    )
                if receipt_turn.result.status == "pending_confirmation":
                    pending_action = await create_pending_expense_action(
                        session,
                        conversation_id=conversation_id,
                        owner_user_id=admin_user_id,
                        draft=ExpenseActionDraft(
                            transactions=receipt_turn.result.transactions,
                        ),
                        attachment_id=action_attachment_id,
                        expires_at=expires_at,
                    )
                else:
                    pending_action = await create_clarification_action(
                        session,
                        conversation_id=conversation_id,
                        owner_user_id=admin_user_id,
                        draft=ClarificationActionDraft(
                            transactions=receipt_turn.result.transactions,
                            issues=receipt_turn.result.issues,
                        ),
                        attachment_id=action_attachment_id,
                        expires_at=expires_at,
                    )
                await session.commit()
        except PendingActionStateError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Чернетка з чеку містить невалідні дані. Уточніть, будь ласка, дані чеку.",
            ) from error
        answer = receipt_turn.result.message
    else:
        try:
            answer = await run_chat_turn(request.app.state.ai_chat_graph, conversation_id, payload.message)
        except (AIChatCheckpointError, AIChatProviderError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI-помічник тимчасово недоступний. Спробуйте ще раз трохи згодом.",
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
            payload=ChatMessageCreate(
                role="assistant",
                content=answer,
                tool_name="pending_action" if pending_action else None,
                tool_call_id=str(pending_action.id) if pending_action else None,
            ),
        )
        await session.commit()
        await session.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation_id,
        message=serialize_chat_message(assistant_message),
        pending_action_id=pending_action.id if pending_action else None,
        pending_action_status=pending_action.status if pending_action else None,
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
    async with AsyncSessionLocal() as session:
        user = await get_or_create_admin_user(session, str(admin_session["username"]))
        transaction = await create_transaction_for_user(
            session,
            user=user,
            payload=TransactionCreateData(
                created_at=payload.created_at,
                amount=payload.amount,
                category=payload.category,
                transaction_type=payload.type,
            ),
        )
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


@app.get("/api/admin/google-drive/connect")
async def start_google_drive_connect(
    response: Response,
    admin_session: dict[str, object] = Depends(require_admin),
) -> RedirectResponse:
    """Start an Admin-only OAuth flow with a one-time CSRF state cookie."""

    del admin_session
    try:
        settings = get_google_drive_settings(require_refresh_token=False)
    except GoogleDriveConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    if not settings:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google Drive is not configured.")
    state = secrets.token_urlsafe(32)
    redirect = RedirectResponse(build_authorization_url(settings, state), status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        GOOGLE_OAUTH_STATE_COOKIE_NAME, state, httponly=True, samesite="lax",
        secure=use_secure_session_cookie(), max_age=600,
    )
    return redirect


@app.get("/api/admin/google-drive/callback")
async def complete_google_drive_connect(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    admin_session: dict[str, object] = Depends(require_admin),
) -> HTMLResponse:
    """Exchange the code and expose the bootstrap token once over Admin HTTPS."""

    del admin_session
    expected_state = request.cookies.get(GOOGLE_OAUTH_STATE_COOKIE_NAME)
    if error or not code or not state or not expected_state or not hmac.compare_digest(state, expected_state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google Drive authorization was not completed safely.")
    try:
        settings = get_google_drive_settings(require_refresh_token=False)
        if not settings:
            raise GoogleDriveConfigurationError("Google Drive is not configured.")
        refresh_token = await asyncio.to_thread(exchange_code, settings, code)
    except (GoogleDriveConfigurationError, GoogleDriveOAuthError) as oauth_error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google Drive authorization failed.") from oauth_error
    response = HTMLResponse(
        "<html><body><h1>Google Drive connected</h1>"
        "<p>Copy this one-time token into Render as <code>GOOGLE_DRIVE_REFRESH_TOKEN</code>, then close this page. "
        "Do not save it in Git or share it.</p><pre style='white-space:pre-wrap;word-break:break-all'>"
        f"{refresh_token}</pre></body></html>",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    response.delete_cookie(GOOGLE_OAUTH_STATE_COOKIE_NAME)
    return response


if FRONTEND_DIST_DIR.is_dir():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")


@app.get("/{frontend_path:path}", include_in_schema=False)
async def frontend_application(frontend_path: str) -> FileResponse:
    """Return the React SPA for browser routes while preserving API 404s."""

    if frontend_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frontend build is not available.",
        )

    return FileResponse(index_file)
