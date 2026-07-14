from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.database import AsyncSessionLocal, check_database_connection
from app.models import Category, Transaction, User


INCOME_CATEGORIES = {
    "income",
    "salary",
    "revenue",
    "bonus",
    "deposit",
    "дохід",
    "зарплата",
    "прибуток",
    "бонус",
    "депозит",
}

app = FastAPI(title="Orest Admin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def to_float(value: Decimal | None) -> float:
    return float(value or Decimal("0.00"))


def transaction_type(category_name: str) -> str:
    if category_name.strip().lower() in INCOME_CATEGORIES:
        return "income"

    return "expense"


@app.get("/health")
async def health() -> dict[str, str]:
    await check_database_connection()
    return {"status": "ok"}


@app.get("/api/transactions")
async def transactions() -> list[dict[str, object]]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                Transaction.id,
                Transaction.amount,
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

    items = []
    for row in rows:
        kind = transaction_type(row.category)
        amount = Decimal(row.amount or 0)
        items.append(
            {
                "id": row.id,
                "amount": to_float(amount.copy_abs()),
                "category": row.category,
                "type": kind,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "user": row.username or row.first_name or "unknown",
            }
        )

    return items


@app.get("/api/summary")
async def summary() -> dict[str, float]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Transaction.amount, Category.name)
            .join(Category, Transaction.category_id == Category.id)
        )
        rows = result.all()

    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")

    for row in rows:
        amount = Decimal(row.amount or 0).copy_abs()
        if transaction_type(row.name) == "income":
            total_income += amount
        else:
            total_expense += amount

    balance = total_income - total_expense

    return {
        "total_income": to_float(total_income),
        "total_expense": to_float(total_expense),
        "balance": to_float(balance),
    }
