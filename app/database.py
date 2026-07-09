import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")


def get_async_database_url(database_url: str) -> URL:
    url = make_url(database_url)

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    return url


def get_connect_args(database_url: str) -> dict[str, bool]:
    url = make_url(database_url)
    sslmode = url.query.get("sslmode")

    if sslmode in {"require", "verify-ca", "verify-full"}:
        return {"ssl": True}

    return {}


def remove_asyncpg_unsupported_query_params(database_url: str) -> URL:
    url = get_async_database_url(database_url)
    return url.difference_update_query(["sslmode"])


async_engine = create_async_engine(
    remove_asyncpg_unsupported_query_params(DATABASE_URL),
    connect_args=get_connect_args(DATABASE_URL),
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def check_database_connection() -> None:
    async with async_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
