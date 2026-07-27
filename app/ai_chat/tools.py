"""Controlled, read-only financial tools for the future LangGraph agent."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Awaitable, Callable

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_chat.schemas import (
    CategoryTotalsParams,
    DailyExpensesParams,
    PeriodComparisonParams,
    PeriodParams,
    TopExpensesParams,
    TransactionsSummaryParams,
)
from app.models import Category, Transaction, User


def _as_float(value: Decimal | int | float | None) -> float:
    return float(value or 0)


def _apply_period_filters(statement, params: PeriodParams):
    if params.date_from:
        statement = statement.where(func.date(Transaction.created_at) >= params.date_from)
    if params.date_to:
        statement = statement.where(func.date(Transaction.created_at) <= params.date_to)
    if params.user:
        statement = statement.where(
            or_(User.username == params.user, User.first_name == params.user)
        )
    return statement


async def get_transactions_summary(
    session: AsyncSession,
    params: TransactionsSummaryParams,
) -> dict[str, Any]:
    """Return minimal income, expense and balance aggregates for a period."""

    amount = func.abs(Transaction.amount)
    statement = select(
        func.count(Transaction.id).label("transactions_count"),
        func.coalesce(
            func.sum(case((Transaction.transaction_type == "income", amount), else_=0)),
            0,
        ).label("total_income"),
        func.coalesce(
            func.sum(case((Transaction.transaction_type == "expense", amount), else_=0)),
            0,
        ).label("total_expense"),
        func.min(func.date(Transaction.created_at)).label("period_from"),
        func.max(func.date(Transaction.created_at)).label("period_to"),
    ).join(User, Transaction.user_id == User.id)
    row = (await session.execute(_apply_period_filters(statement, params))).one()
    total_income = _as_float(row.total_income)
    total_expense = _as_float(row.total_expense)
    return {
        "currency": "UAH",
        "transactions_count": int(row.transactions_count or 0),
        "period": {
            "from": row.period_from.isoformat() if row.period_from else None,
            "to": row.period_to.isoformat() if row.period_to else None,
        },
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
    }


async def get_category_totals(
    session: AsyncSession,
    params: CategoryTotalsParams,
) -> dict[str, Any]:
    """Return category totals without exposing individual transactions."""

    statement = (
        select(
            Category.name.label("category"),
            func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label("amount"),
            func.count(Transaction.id).label("transactions_count"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .join(User, Transaction.user_id == User.id)
        .where(Transaction.transaction_type == params.transaction_type)
        .group_by(Category.name)
        .order_by(func.sum(func.abs(Transaction.amount)).desc(), Category.name)
        .limit(params.limit)
    )
    rows = (await session.execute(_apply_period_filters(statement, params))).all()
    return {
        "currency": "UAH",
        "transaction_type": params.transaction_type,
        "categories": [
            {
                "category": row.category,
                "amount": _as_float(row.amount),
                "transactions_count": int(row.transactions_count),
            }
            for row in rows
        ],
    }


async def get_top_expenses(
    session: AsyncSession,
    params: TopExpensesParams,
) -> dict[str, Any]:
    """Return a small, date/category/amount-only list of the largest expenses."""

    statement = (
        select(
            func.date(Transaction.created_at).label("date"),
            Category.name.label("category"),
            func.abs(Transaction.amount).label("amount"),
        )
        .join(Category, Transaction.category_id == Category.id)
        .join(User, Transaction.user_id == User.id)
        .where(Transaction.transaction_type == "expense")
        .order_by(func.abs(Transaction.amount).desc(), Transaction.created_at.desc())
        .limit(params.limit)
    )
    rows = (await session.execute(_apply_period_filters(statement, params))).all()
    return {
        "currency": "UAH",
        "expenses": [
            {
                "date": row.date.isoformat(),
                "category": row.category,
                "amount": _as_float(row.amount),
            }
            for row in rows
        ],
    }


async def _summary_for_dates(
    session: AsyncSession,
    *,
    date_from: date,
    date_to: date,
) -> dict[str, float | int]:
    return await get_transactions_summary(
        session,
        TransactionsSummaryParams(date_from=date_from, date_to=date_to),
    )


async def get_period_comparison(
    session: AsyncSession,
    params: PeriodComparisonParams,
) -> dict[str, Any]:
    """Compare aggregate income, expense and balance for two periods."""

    current = await _summary_for_dates(
        session,
        date_from=params.current_from,
        date_to=params.current_to,
    )
    previous = await _summary_for_dates(
        session,
        date_from=params.previous_from,
        date_to=params.previous_to,
    )
    return {
        "currency": "UAH",
        "current": current,
        "previous": previous,
        "difference": {
            key: float(current[key]) - float(previous[key])
            for key in ("total_income", "total_expense", "balance")
        },
    }


async def get_daily_expenses(
    session: AsyncSession,
    params: DailyExpensesParams,
) -> dict[str, Any]:
    """Return daily expense totals for exactly one calendar month."""

    year, month = map(int, params.month.split("-"))
    date_from = date(year, month, 1)
    date_to = date(year, month, monthrange(year, month)[1])
    statement = (
        select(
            func.date(Transaction.created_at).label("date"),
            func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label("amount"),
        )
        .join(User, Transaction.user_id == User.id)
        .where(Transaction.transaction_type == "expense")
        .where(func.date(Transaction.created_at) >= date_from)
        .where(func.date(Transaction.created_at) <= date_to)
        .group_by(func.date(Transaction.created_at))
        .order_by(func.date(Transaction.created_at))
    )
    rows = (await session.execute(statement)).all()
    return {
        "currency": "UAH",
        "month": params.month,
        "daily_expenses": [
            {"date": row.date.isoformat(), "amount": _as_float(row.amount)}
            for row in rows
        ],
    }


ToolHandler = Callable[[AsyncSession, Any], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters_model: type[PeriodParams] | type[PeriodComparisonParams] | type[DailyExpensesParams]
    handler: ToolHandler

    @property
    def json_schema(self) -> dict[str, Any]:
        return self.parameters_model.model_json_schema()


FINANCIAL_TOOLS: dict[str, ToolDefinition] = {
    "get_transactions_summary": ToolDefinition(
        name="get_transactions_summary",
        description="Повертає доходи, витрати, баланс і кількість транзакцій за період.",
        parameters_model=TransactionsSummaryParams,
        handler=get_transactions_summary,
    ),
    "get_category_totals": ToolDefinition(
        name="get_category_totals",
        description="Повертає підсумки транзакцій за категоріями.",
        parameters_model=CategoryTotalsParams,
        handler=get_category_totals,
    ),
    "get_top_expenses": ToolDefinition(
        name="get_top_expenses",
        description="Повертає найбільші окремі витрати за період.",
        parameters_model=TopExpensesParams,
        handler=get_top_expenses,
    ),
    "get_period_comparison": ToolDefinition(
        name="get_period_comparison",
        description="Порівнює доходи, витрати та баланс двох неперетинних періодів.",
        parameters_model=PeriodComparisonParams,
        handler=get_period_comparison,
    ),
    "get_daily_expenses": ToolDefinition(
        name="get_daily_expenses",
        description="Повертає щоденну суму витрат за один календарний місяць.",
        parameters_model=DailyExpensesParams,
        handler=get_daily_expenses,
    ),
}
