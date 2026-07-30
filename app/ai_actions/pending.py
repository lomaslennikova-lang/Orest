"""Server-only state machine for confirmable AI expense actions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_actions.audit import AuditLogWriter
from app.ai_actions.transactions import (
    TransactionCreateData,
    TransactionValidationError,
    create_transaction_for_user,
    normalise_transaction_data,
)
from app.models import AIConversation, AIPendingAction, AIReceiptAttachment, User


PENDING_ACTION_STATUSES = {"needs_clarification", "pending_confirmation"}


class PendingActionError(RuntimeError):
    """Base error for a pending action that cannot be processed."""


class PendingActionNotFoundError(PendingActionError):
    pass


class PendingActionExpiredError(PendingActionError):
    pass


class PendingActionStateError(PendingActionError):
    pass


class ExpenseTransactionDraft(BaseModel):
    """Strict, user-confirmable form of one AI-proposed expense transaction."""

    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    amount: Decimal = Field(gt=0, le=Decimal("100000"))
    category: str = Field(min_length=1, max_length=255)
    type: Literal["expense"] = "expense"

    @field_validator("category")
    @classmethod
    def normalise_category(cls, value: str) -> str:
        normalised = value.strip()
        if not normalised:
            raise ValueError("category must not be blank")
        return normalised


class ExpenseActionDraft(BaseModel):
    """The immutable JSON snapshot presented to the user for confirmation."""

    model_config = ConfigDict(extra="forbid")

    transactions: list[ExpenseTransactionDraft] = Field(min_length=1, max_length=20)


class ConfirmedActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID
    status: Literal["executed"]
    created_transaction_ids: list[int]


def _current_time(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def create_pending_expense_action(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    owner_user_id: int,
    draft: ExpenseActionDraft,
    expires_at: datetime,
    attachment_id: UUID | None = None,
) -> AIPendingAction:
    """Persist a server-validated draft only for the owning conversation and receipt."""

    conversation = await session.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.owner_user_id == owner_user_id,
        )
    )
    if not conversation:
        raise PendingActionNotFoundError("Chat not found.")

    if attachment_id is not None:
        attachment = await session.scalar(
            select(AIReceiptAttachment).where(
                AIReceiptAttachment.id == attachment_id,
                AIReceiptAttachment.owner_user_id == owner_user_id,
            )
        )
        if not attachment:
            raise PendingActionNotFoundError("Receipt attachment not found.")

    try:
        normalised_transactions = []
        for transaction in draft.transactions:
            normalised = normalise_transaction_data(
                TransactionCreateData(
                    created_at=transaction.created_at,
                    amount=transaction.amount,
                    category=transaction.category,
                    transaction_type=transaction.type,
                )
            )
            normalised_transactions.append(
                ExpenseTransactionDraft(
                    created_at=normalised.created_at,
                    amount=normalised.amount,
                    category=normalised.category,
                )
            )
    except TransactionValidationError as error:
        raise PendingActionStateError("Pending action contains an invalid draft.") from error

    normalised_draft = ExpenseActionDraft(transactions=normalised_transactions)
    action = AIPendingAction(
        conversation_id=conversation_id,
        owner_user_id=owner_user_id,
        attachment_id=attachment_id,
        status="pending_confirmation",
        draft_payload=normalised_draft.model_dump(mode="json"),
        expires_at=_current_time(expires_at),
    )
    session.add(action)
    await session.flush()
    return action


async def create_clarification_action(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    owner_user_id: int,
    clarification: str,
    expires_at: datetime,
    attachment_id: UUID | None = None,
) -> AIPendingAction:
    """Persist a no-write state that records the exact information still needed."""

    conversation = await session.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.owner_user_id == owner_user_id,
        )
    )
    if not conversation:
        raise PendingActionNotFoundError("Chat not found.")
    if attachment_id is not None:
        attachment = await session.scalar(
            select(AIReceiptAttachment).where(
                AIReceiptAttachment.id == attachment_id,
                AIReceiptAttachment.owner_user_id == owner_user_id,
            )
        )
        if not attachment:
            raise PendingActionNotFoundError("Receipt attachment not found.")

    action = AIPendingAction(
        conversation_id=conversation_id,
        owner_user_id=owner_user_id,
        attachment_id=attachment_id,
        status="needs_clarification",
        draft_payload={"clarification": clarification, "transactions": []},
        expires_at=_current_time(expires_at),
    )
    session.add(action)
    await session.flush()
    return action


async def expire_open_actions_for_new_message(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    owner_user_id: int,
    now: datetime | None = None,
) -> int:
    """Invalidate previous unconfirmed actions before processing a new chat message."""

    result = await session.execute(
        update(AIPendingAction)
        .where(
            AIPendingAction.conversation_id == conversation_id,
            AIPendingAction.owner_user_id == owner_user_id,
            AIPendingAction.status.in_(PENDING_ACTION_STATUSES),
        )
        .values(status="expired", completed_at=_current_time(now)),
    )
    return int(result.rowcount or 0)


async def _get_owned_action_for_update(
    session: AsyncSession,
    *,
    action_id: UUID,
    owner_user_id: int,
) -> AIPendingAction:
    action = await session.scalar(
        select(AIPendingAction)
        .where(
            AIPendingAction.id == action_id,
            AIPendingAction.owner_user_id == owner_user_id,
        )
        .with_for_update(),
    )
    if not action:
        raise PendingActionNotFoundError("Pending action not found.")
    return action


async def cancel_pending_action(
    session: AsyncSession,
    *,
    action_id: UUID,
    owner_user_id: int,
    now: datetime | None = None,
) -> AIPendingAction:
    """Cancel only a still-open, owned action; callers commit the state change."""

    action = await _get_owned_action_for_update(
        session,
        action_id=action_id,
        owner_user_id=owner_user_id,
    )
    current_time = _current_time(now)
    if action.expires_at <= current_time:
        action.status = "expired"
        action.completed_at = current_time
        raise PendingActionExpiredError("Pending action has expired.")
    if action.status not in PENDING_ACTION_STATUSES:
        raise PendingActionStateError("Pending action cannot be cancelled.")
    action.status = "cancelled"
    action.completed_at = current_time
    await session.flush()
    return action


def _confirmed_result(action: AIPendingAction) -> ConfirmedActionResult:
    result = action.execution_result or {}
    identifiers = result.get("created_transaction_ids")
    if not isinstance(identifiers, list) or not all(isinstance(value, int) for value in identifiers):
        raise PendingActionStateError("Executed action has no valid idempotency result.")
    return ConfirmedActionResult(
        action_id=action.id,
        status="executed",
        created_transaction_ids=identifiers,
    )


async def confirm_pending_action(
    session: AsyncSession,
    *,
    action_id: UUID,
    owner: User,
    audit_writer: AuditLogWriter,
    now: datetime | None = None,
) -> ConfirmedActionResult:
    """Execute an owned expense draft once and write its audit record before commit.

    The caller must use a database transaction and roll it back when this function
    raises. A repeated confirm for an executed action returns its saved result.
    """

    action = await _get_owned_action_for_update(
        session,
        action_id=action_id,
        owner_user_id=owner.id,
    )
    current_time = _current_time(now)
    if action.status == "executed":
        return _confirmed_result(action)
    if action.expires_at <= current_time:
        action.status = "expired"
        action.completed_at = current_time
        raise PendingActionExpiredError("Pending action has expired.")
    if action.status != "pending_confirmation":
        raise PendingActionStateError("Pending action cannot be confirmed.")

    try:
        draft = ExpenseActionDraft.model_validate(action.draft_payload)
    except ValueError as error:
        action.status = "failed"
        action.completed_at = current_time
        raise PendingActionStateError("Pending action contains an invalid draft.") from error

    transaction_ids: list[int] = []
    for transaction_draft in draft.transactions:
        try:
            transaction = await create_transaction_for_user(
                session,
                user=owner,
                payload=TransactionCreateData(
                    created_at=transaction_draft.created_at,
                    amount=transaction_draft.amount,
                    category=transaction_draft.category,
                    transaction_type=transaction_draft.type,
                ),
            )
        except TransactionValidationError as error:
            action.status = "failed"
            action.completed_at = current_time
            raise PendingActionStateError("Pending action did not pass transaction validation.") from error
        transaction_ids.append(transaction.id)

    attachment_sha256: str | None = None
    if action.attachment_id:
        attachment = await session.scalar(
            select(AIReceiptAttachment.content_sha256).where(
                AIReceiptAttachment.id == action.attachment_id,
            )
        )
        attachment_sha256 = attachment

    audit_writer.append_executed_action(
        action_id=action.id,
        conversation_id=action.conversation_id,
        actor_username=owner.username or owner.first_name or "admin",
        payload=draft.model_dump(mode="json"),
        created_transaction_ids=transaction_ids,
        attachment_sha256=attachment_sha256,
        executed_at=current_time,
    )
    action.execution_result = {"created_transaction_ids": transaction_ids}
    action.status = "executed"
    action.completed_at = current_time
    await session.flush()
    return _confirmed_result(action)
