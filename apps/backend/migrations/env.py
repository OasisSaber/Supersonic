from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.adapters.postgres.orm import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def require_database_url() -> str:
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        raise RuntimeError("DATABASE_URL is required for Alembic migrations")
    try:
        url = make_url(raw_url)
    except ArgumentError:
        raise RuntimeError(
            "DATABASE_URL must use postgresql+psycopg"
        ) from None
    if url.drivername != "postgresql+psycopg":
        raise RuntimeError("DATABASE_URL must use postgresql+psycopg")
    return raw_url


def run_migrations_offline() -> None:
    context.configure(
        url=require_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = require_database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
