from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
COMMITTED_ROW_DELETE_ORDER = ("audit_events", "platform_sessions", "users")


def require_test_database_url() -> str:
    raw_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not raw_url:
        raise pytest.UsageError(
            "TEST_DATABASE_URL is required for PostgreSQL integration tests"
        )
    try:
        url = make_url(raw_url)
    except ArgumentError:
        raise pytest.UsageError(
            "TEST_DATABASE_URL must use postgresql+psycopg"
        ) from None
    if url.drivername != "postgresql+psycopg":
        raise pytest.UsageError("TEST_DATABASE_URL must use postgresql+psycopg")
    if not url.database or not url.database.endswith("_test"):
        raise pytest.UsageError("TEST_DATABASE_URL database name must end with _test")
    if os.environ.get("SUPERSONIC_ALLOW_TEST_DB_RESET") != "1":
        raise pytest.UsageError(
            "SUPERSONIC_ALLOW_TEST_DB_RESET must be exactly 1 for PostgreSQL integration tests"
        )
    if raw_url == os.environ.get("DATABASE_URL", "").strip():
        raise pytest.UsageError("TEST_DATABASE_URL must not equal DATABASE_URL")
    return raw_url


TEST_DATABASE_URL = require_test_database_url()


def make_alembic_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def require_matching_test_database_url(database_url: str) -> str:
    validated_database_url = require_test_database_url()
    if database_url != validated_database_url:
        raise pytest.UsageError("database URL must match TEST_DATABASE_URL")
    return validated_database_url


def reset_public_schema(database_url: str) -> None:
    validated_database_url = require_matching_test_database_url(database_url)

    engine = create_engine(validated_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def clear_committed_rows(database_url: str) -> None:
    validated_database_url = require_matching_test_database_url(database_url)

    engine = create_engine(validated_database_url)
    try:
        with engine.begin() as connection:
            existing_tables = set(
                inspect(connection).get_table_names(schema="public")
            )
            for table_name in COMMITTED_ROW_DELETE_ORDER:
                if table_name in existing_tables:
                    connection.execute(text(f"DELETE FROM public.{table_name}"))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def migrated_database_url() -> Iterator[str]:
    reset_public_schema(TEST_DATABASE_URL)
    previous_database_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = TEST_DATABASE_URL
        try:
            command.upgrade(make_alembic_config(), "head")
        finally:
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url
        yield TEST_DATABASE_URL
    finally:
        reset_public_schema(TEST_DATABASE_URL)


@pytest.fixture(autouse=True)
def isolate_committed_database_rows(
    migrated_database_url: str,
) -> Iterator[None]:
    yield
    clear_committed_rows(migrated_database_url)
