"""Shared server-side transaction creation rules for manual and AI-confirmed writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Transaction, User


MAX_TRANSACTION_AMOUNT = Decimal("100000")


class TransactionValidationError(ValueError):
    """A user-correctable transaction payload error."""


@dataclass(frozen=True)
class TransactionCreateData:
    created_at: datetime
    amount: Decimal
    category: str
    transaction_type: str


def normalise_transaction_data(payload: TransactionCreateData) -> TransactionCreateData:
    """Validate and normalise data before any write reaches the database."""

    created_at = payload.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = created_at.astimezone(timezone.utc)

    if created_at > datetime.now(timezone.utc):
        raise TransactionValidationError("Transaction date and time cannot be later than now.")
    if payload.amount <= 0:
        raise TransactionValidationError("Amount must be greater than zero.")
    if payload.amount > MAX_TRANSACTION_AMOUNT:
        raise TransactionValidationError("Amount cannot exceed 100000 UAH.")
    if payload.transaction_type not in {"income", "expense"}:
        raise TransactionValidationError("Transaction type must be income or expense.")

    category = payload.category.strip().lower()
    if not category:
        raise TransactionValidationError("Category is required.")

    return TransactionCreateData(
        created_at=created_at,
        amount=payload.amount.quantize(Decimal("0.01")),
        category=category,
        transaction_type=payload.transaction_type,
    )


async def get_or_create_user_by_name(session: AsyncSession, username: str) -> User:
    """Resolve the authenticated Admin user without trusting a client user ID."""

    normalised_username = username.strip()
    if not normalised_username:
        raise TransactionValidationError("User is required.")

    result = await session.execute(
        select(User).where(
            or_(
                User.username == normalised_username,
                User.first_name == normalised_username,
            )
        )
    )
    user = result.scalars().first()
    if user:
        return user

    # This user is only created for the already authenticated Admin session.
    # The deterministic negative ID matches the existing API convention.
    import hashlib

    telegram_id = -int(hashlib.sha256(normalised_username.encode()).hexdigest()[:15], 16)
    user = User(
        telegram_id=telegram_id,
        username=normalised_username,
        first_name=normalised_username,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_category(
    session: AsyncSession,
    *,
    user: User,
    category_name: str,
) -> Category:
    """Resolve a category under the authenticated transaction owner."""

    result = await session.execute(
        select(Category).where(
            Category.user_id == user.id,
            Category.name == category_name,
        )
    )
    category = result.scalar_one_or_none()
    if category:
        return category

    category = Category(user_id=user.id, name=category_name)
    session.add(category)
    await session.flush()
    return category


async def create_transaction_for_user(
    session: AsyncSession,
    *,
    user: User,
    payload: TransactionCreateData,
) -> Transaction:
    """Create one validated transaction; the caller owns the surrounding commit."""

    normalised = normalise_transaction_data(payload)
    category = await get_or_create_category(
        session,
        user=user,
        category_name=normalised.category,
    )
    transaction = Transaction(
        user_id=user.id,
        category_id=category.id,
        amount=normalised.amount,
        transaction_type=normalised.transaction_type,
        created_at=normalised.created_at,
    )
    session.add(transaction)
    await session.flush()
    return transaction
