"""HTTP-safe views for receipt attachments and pending action state."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ActionStatus = Literal[
    "needs_clarification",
    "pending_confirmation",
    "confirmed",
    "executed",
    "cancelled",
    "expired",
    "failed",
]


class ReceiptAttachmentView(BaseModel):
    id: UUID
    filename: str
    media_type: Literal["application/pdf", "image/png", "image/jpeg"]
    byte_size: int = Field(gt=0)
    created_at: datetime
    expires_at: datetime


class PendingActionView(BaseModel):
    id: UUID
    conversation_id: UUID
    status: ActionStatus
    draft_payload: dict[str, Any]
    expires_at: datetime
    completed_at: datetime | None = None
    created_transaction_ids: list[int] | None = None


class ActionCancelResponse(BaseModel):
    id: UUID
    status: Literal["cancelled"]


class ActionConfirmResponse(BaseModel):
    id: UUID
    status: Literal["executed"]
    created_transaction_ids: list[int]
    finance_url: str = "/api/transactions"
