from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from app.database import AsyncSessionLocal, check_database_connection, init_database
from app.models import Category, Transaction, User


app = FastAPI(title="Orest Admin API")
SESSION_COOKIE_NAME = "orest_admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 8

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


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


@app.on_event("startup")
async def startup() -> None:
    await check_database_connection()
    await init_database()


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

    items = []
    for row in rows:
        amount = Decimal(row.amount or 0)
        items.append(
            {
                "id": row.id,
                "amount": to_float(amount.copy_abs()),
                "category": row.category,
                "type": row.transaction_type,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "user": row.username or row.first_name or "unknown",
            }
        )

    return items


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
