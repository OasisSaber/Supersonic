from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest

SAFE_TEST_DATABASE_URL = (
    "postgresql+psycopg://supersonic:supersonic_test@127.0.0.1:5432/supersonic_test"
)
INTEGRATION_CONFTEST = (
    Path(__file__).resolve().parents[1] / "integration_tests" / "conftest.py"
)


class _RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: object) -> None:
        self.statements.append(str(statement))


class _RecordingEngine:
    def __init__(self) -> None:
        self.connection = _RecordingConnection()
        self.disposed = False

    def begin(self) -> _RecordingEngine:
        return self

    def __enter__(self) -> _RecordingConnection:
        return self.connection

    def __exit__(self, *args: object) -> None:
        return None

    def dispose(self) -> None:
        self.disposed = True


class _StaticInspector:
    def __init__(self, table_names: list[str]) -> None:
        self.table_names = table_names

    def get_table_names(self, *, schema: str) -> list[str]:
        assert schema == "public"
        return self.table_names


def _load_integration_fixture(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("TEST_DATABASE_URL", SAFE_TEST_DATABASE_URL)
    monkeypatch.setenv("SUPERSONIC_ALLOW_TEST_DB_RESET", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    module_name = f"integration_fixture_{uuid4().hex}"
    specification = importlib.util.spec_from_file_location(module_name, INTEGRATION_CONFTEST)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("environment", "expected_message"),
    [
        ({"TEST_DATABASE_URL": None}, "TEST_DATABASE_URL is required"),
        (
            {"TEST_DATABASE_URL": "postgresql://localhost/supersonic_test"},
            "postgresql+psycopg",
        ),
        (
            {"TEST_DATABASE_URL": "postgresql+psycopg://localhost/supersonic"},
            "must end with _test",
        ),
        ({"SUPERSONIC_ALLOW_TEST_DB_RESET": None}, "SUPERSONIC_ALLOW_TEST_DB_RESET"),
        ({"SUPERSONIC_ALLOW_TEST_DB_RESET": "true"}, "SUPERSONIC_ALLOW_TEST_DB_RESET"),
        ({"DATABASE_URL": SAFE_TEST_DATABASE_URL}, "must not equal DATABASE_URL"),
    ],
    ids=[
        "missing-test-url",
        "wrong-driver",
        "unsafe-database-name",
        "missing-reset-opt-in",
        "non-exact-reset-opt-in",
        "same-process-database-url",
    ],
)
def test_reset_rejects_invalid_runtime_configuration_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str | None],
    expected_message: str,
) -> None:
    """Catches a reset path that connects before rejecting an unsafe configuration."""
    fixture = _load_integration_fixture(monkeypatch)
    connection_attempts: list[str] = []

    def record_connection(url: str) -> _RecordingEngine:
        connection_attempts.append(url)
        return _RecordingEngine()

    monkeypatch.setattr(fixture, "create_engine", record_connection)
    for name, value in environment.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    with pytest.raises(pytest.UsageError, match=re.escape(expected_message)):
        fixture.reset_public_schema(SAFE_TEST_DATABASE_URL)

    assert connection_attempts == []


@pytest.mark.parametrize(
    ("environment", "expected_message"),
    [
        ({"TEST_DATABASE_URL": None}, "TEST_DATABASE_URL is required"),
        (
            {"TEST_DATABASE_URL": "postgresql://localhost/supersonic_test"},
            "postgresql+psycopg",
        ),
        (
            {"TEST_DATABASE_URL": "postgresql+psycopg://localhost/supersonic"},
            "must end with _test",
        ),
        ({"SUPERSONIC_ALLOW_TEST_DB_RESET": None}, "SUPERSONIC_ALLOW_TEST_DB_RESET"),
        ({"SUPERSONIC_ALLOW_TEST_DB_RESET": "true"}, "SUPERSONIC_ALLOW_TEST_DB_RESET"),
        ({"DATABASE_URL": SAFE_TEST_DATABASE_URL}, "must not equal DATABASE_URL"),
    ],
    ids=[
        "missing-test-url",
        "wrong-driver",
        "unsafe-database-name",
        "missing-reset-opt-in",
        "non-exact-reset-opt-in",
        "same-process-database-url",
    ],
)
def test_cleanup_rejects_invalid_runtime_configuration_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str | None],
    expected_message: str,
) -> None:
    """Catches cleanup connecting after its destructive-reset safety gate fails."""
    fixture = _load_integration_fixture(monkeypatch)
    connection_attempts: list[str] = []

    def record_connection(url: str) -> _RecordingEngine:
        connection_attempts.append(url)
        return _RecordingEngine()

    monkeypatch.setattr(fixture, "create_engine", record_connection)
    for name, value in environment.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    with pytest.raises(pytest.UsageError, match=re.escape(expected_message)):
        fixture.clear_committed_rows(SAFE_TEST_DATABASE_URL)

    assert connection_attempts == []


def test_cleanup_rejects_a_url_that_does_not_match_the_validated_test_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches cleanup connecting to an argument that differs from TEST_DATABASE_URL."""
    fixture = _load_integration_fixture(monkeypatch)
    connection_attempts: list[str] = []

    def record_connection(url: str) -> _RecordingEngine:
        connection_attempts.append(url)
        return _RecordingEngine()

    monkeypatch.setattr(fixture, "create_engine", record_connection)

    with pytest.raises(
        pytest.UsageError,
        match=re.escape("database URL must match TEST_DATABASE_URL"),
    ):
        fixture.clear_committed_rows(f"{SAFE_TEST_DATABASE_URL}-other")

    assert connection_attempts == []


def test_cleanup_with_explicit_safe_opt_in_reaches_committed_row_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches a cleanup gate that blocks the explicit safe integration-test configuration."""
    fixture = _load_integration_fixture(monkeypatch)
    engine = _RecordingEngine()
    connection_attempts: list[str] = []

    def record_connection(url: str) -> _RecordingEngine:
        connection_attempts.append(url)
        return engine

    monkeypatch.setattr(fixture, "create_engine", record_connection)
    monkeypatch.setattr(fixture, "inspect", lambda _: _StaticInspector(["users"]))

    fixture.clear_committed_rows(SAFE_TEST_DATABASE_URL)

    assert connection_attempts == [SAFE_TEST_DATABASE_URL]
    assert engine.connection.statements == ["DELETE FROM public.users"]
    assert engine.disposed is True


def test_reset_with_explicit_safe_opt_in_reaches_schema_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches a reset gate that blocks the explicit safe integration-test configuration."""
    fixture = _load_integration_fixture(monkeypatch)
    engine = _RecordingEngine()
    connection_attempts: list[str] = []

    def record_connection(url: str) -> _RecordingEngine:
        connection_attempts.append(url)
        return engine

    monkeypatch.setattr(fixture, "create_engine", record_connection)

    fixture.reset_public_schema(SAFE_TEST_DATABASE_URL)

    assert connection_attempts == [SAFE_TEST_DATABASE_URL]
    assert engine.connection.statements == [
        "DROP SCHEMA public CASCADE",
        "CREATE SCHEMA public",
    ]
    assert engine.disposed is True


def test_migrated_fixture_restores_database_url_before_autouse_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches cleanup running while the Alembic-only database URL has leaked."""
    fixture = _load_integration_fixture(monkeypatch)
    reset_database_urls: list[str | None] = []
    cleanup_connection_attempts: list[str] = []
    cleanup_engine = _RecordingEngine()

    def record_reset(_: str) -> None:
        reset_database_urls.append(os.environ.get("DATABASE_URL"))

    monkeypatch.setattr(fixture, "reset_public_schema", record_reset)
    monkeypatch.setattr(fixture.command, "upgrade", lambda *_: None)

    def record_cleanup_connection(database_url: str) -> _RecordingEngine:
        cleanup_connection_attempts.append(database_url)
        return cleanup_engine

    monkeypatch.setattr(fixture, "create_engine", record_cleanup_connection)
    monkeypatch.setattr(fixture, "inspect", lambda _: _StaticInspector(["users"]))

    migrated_database = fixture.migrated_database_url.__wrapped__()
    try:
        assert next(migrated_database) == SAFE_TEST_DATABASE_URL
        isolated_rows = fixture.isolate_committed_database_rows.__wrapped__(
            SAFE_TEST_DATABASE_URL
        )
        assert next(isolated_rows) is None
        with pytest.raises(StopIteration):
            next(isolated_rows)
        assert "DATABASE_URL" not in os.environ
        assert cleanup_connection_attempts == [SAFE_TEST_DATABASE_URL]
        assert cleanup_engine.connection.statements == ["DELETE FROM public.users"]
        assert cleanup_engine.disposed is True
    finally:
        with pytest.raises(StopIteration):
            next(migrated_database)

    assert reset_database_urls == [None, None]
