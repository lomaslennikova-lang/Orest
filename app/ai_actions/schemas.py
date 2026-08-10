"""HTTP-safe views for receipt attachments and pending action state."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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


class DraftRowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int | None = Field(default=None, ge=1, le=20)
    category: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, le=Decimal("100000"))


class PendingDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_at: datetime
    rows: list[DraftRowUpdate] = Field(min_length=1, max_length=20)


class ActionCancelResponse(BaseModel):
    id: UUID
    status: Literal["cancelled"]


class ActionConfirmResponse(BaseModel):
    id: UUID
    status: Literal["executed"]
    created_transaction_ids: list[int]
    finance_url: str = "/api/transactions"
