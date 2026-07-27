"""Validated data contracts for the AI-chat service and financial tools."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TransactionType = Literal["income", "expense"]
MessageRole = Literal["user", "assistant", "tool", "system"]
MessageStatus = Literal["completed", "failed"]


class PeriodParams(BaseModel):
    """Optional inclusive date range and user filter shared by read-only tools."""

    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None
    user: str | None = Field(default=None, max_length=255)

    @field_validator("user")
    @classmethod
    def normalize_user(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("user must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_period(self) -> "PeriodParams":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be later than date_to")
        return self


class TransactionsSummaryParams(PeriodParams):
    pass


class CategoryTotalsParams(PeriodParams):
    transaction_type: TransactionType = "expense"
    limit: int = Field(default=10, ge=1, le=20)


class TopExpensesParams(PeriodParams):
    limit: int = Field(default=5, ge=1, le=10)


class PeriodComparisonParams(BaseModel):
    """Two explicitly provided, non-overlapping inclusive periods."""

    model_config = ConfigDict(extra="forbid")

    current_from: date
    current_to: date
    previous_from: date
    previous_to: date

    @model_validator(mode="after")
    def validate_periods(self) -> "PeriodComparisonParams":
        if self.current_from > self.current_to:
            raise ValueError("current_from must not be later than current_to")
        if self.previous_from > self.previous_to:
            raise ValueError("previous_from must not be later than previous_to")
        if self.previous_to >= self.current_from:
            raise ValueError("comparison periods must not overlap")
        return self


class DailyExpensesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class ChatMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MessageRole
    content: str = Field(min_length=1, max_length=10_000)
    tool_name: str | None = Field(default=None, max_length=100)
    tool_call_id: str | None = Field(default=None, max_length=100)
    status: MessageStatus = "completed"


class ChatMessageView(BaseModel):
    id: int
    conversation_id: UUID
    role: MessageRole
    content: str
    tool_name: str | None = None
    tool_call_id: str | None = None
    status: MessageStatus


class ConversationView(BaseModel):
    id: UUID
    owner_user_id: int
    title: str | None = None
