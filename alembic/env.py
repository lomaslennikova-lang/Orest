from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from app.database import Base
import app.models  # noqa: F401 -- registers all ORM tables in Base.metadata.


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

url = make_url(database_url)
if url.drivername in {"postgresql", "postgresql+asyncpg"}:
    url = url.set(drivername="postgresql+psycopg")

# URL.__str__ masks a password as "***". Alembic must receive the real URL to
# connect, while this value is never written to application logs.
database_connection_url = url.render_as_string(hide_password=False)
config.set_main_option("sqlalchemy.url", database_connection_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_connection_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
