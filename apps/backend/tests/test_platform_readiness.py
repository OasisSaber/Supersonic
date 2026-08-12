from __future__ import annotations

import ast
from pathlib import Path

import pytest
from psycopg import InterfaceError as PsycopgInterfaceError
from psycopg import OperationalError as PsycopgOperationalError
from sqlalchemy.exc import OperationalError

from app.adapters.postgres.readiness import SqlAlchemyPlatformReadiness
from app.platform.persistence import (
    DatabaseUnavailable,
    MigrationRequired,
    PlatformReadiness,
)

PLATFORM_PERSISTENCE = Path(__file__).parents[1] / "app" / "platform" / "persistence.py"


def test_platform_persistence_failures_have_no_framework_dependency() -> None:
    tree = ast.parse(PLATFORM_PERSISTENCE.read_text(encoding="utf-8"))
    roots = {
        node.module.partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert roots.isdisjoint({"alembic", "fastapi", "psycopg", "sqlalchemy"})


async def test_missing_database_url_is_unavailable_without_building_engine() -> None:
    readiness = SqlAlchemyPlatformReadiness(None)

    with pytest.raises(DatabaseUnavailable, match="Platform database is unavailable"):
        await readiness.check()


async def test_readiness_maps_known_connection_failure_without_secret_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "raw-password-must-not-leak"
    readiness = SqlAlchemyPlatformReadiness(
        f"postgresql+psycopg://user:{secret}@127.0.0.1:1/supersonic"
    )

    async def fail_probe() -> set[str] | None:
        raise OperationalError("SELECT secret", {}, RuntimeError(secret))

    monkeypatch.setattr(readiness, "_read_current_heads", fail_probe)
    with pytest.raises(DatabaseUnavailable) as caught:
        await readiness.check()

    assert str(caught.value) == "Platform database is unavailable."
    assert secret not in str(caught.value)


@pytest.mark.parametrize(
    "error_type", [PsycopgOperationalError, PsycopgInterfaceError]
)
async def test_readiness_maps_known_psycopg_connection_failure_without_secret_leak(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[PsycopgOperationalError | PsycopgInterfaceError],
) -> None:
    secret = "raw-password-must-not-leak"
    readiness = SqlAlchemyPlatformReadiness(
        f"postgresql+psycopg://user:{secret}@127.0.0.1:1/supersonic"
    )

    async def fail_probe() -> set[str] | None:
        raise error_type(secret)

    monkeypatch.setattr(readiness, "_read_current_heads", fail_probe)
    with pytest.raises(DatabaseUnavailable) as caught:
        await readiness.check()

    assert str(caught.value) == "Platform database is unavailable."
    assert secret not in str(caught.value)


async def test_missing_version_table_requires_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readiness = SqlAlchemyPlatformReadiness("postgresql+psycopg://user:p@db/app")
    monkeypatch.setattr(readiness, "_expected_heads", lambda: {"head-a"})

    async def no_version_table() -> set[str] | None:
        return None

    monkeypatch.setattr(readiness, "_read_current_heads", no_version_table)
    with pytest.raises(MigrationRequired, match="Platform database migration is required"):
        await readiness.check()


async def test_empty_version_table_requires_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readiness = SqlAlchemyPlatformReadiness("postgresql+psycopg://user:p@db/app")
    monkeypatch.setattr(readiness, "_expected_heads", lambda: {"head-a"})

    async def empty_version_table() -> set[str] | None:
        return set()

    monkeypatch.setattr(readiness, "_read_current_heads", empty_version_table)
    with pytest.raises(MigrationRequired):
        await readiness.check()


async def test_head_mismatch_requires_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = SqlAlchemyPlatformReadiness("postgresql+psycopg://user:p@db/app")
    monkeypatch.setattr(readiness, "_expected_heads", lambda: {"head-b"})

    async def stale_heads() -> set[str] | None:
        return {"head-a"}

    monkeypatch.setattr(readiness, "_read_current_heads", stale_heads)
    with pytest.raises(MigrationRequired):
        await readiness.check()


async def test_matching_heads_are_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = SqlAlchemyPlatformReadiness("postgresql+psycopg://user:p@db/app")
    monkeypatch.setattr(readiness, "_expected_heads", lambda: {"head-a", "head-b"})

    async def current_heads() -> set[str] | None:
        return {"head-b", "head-a"}

    monkeypatch.setattr(readiness, "_read_current_heads", current_heads)
    assert await readiness.check() is PlatformReadiness.READY


async def test_readiness_does_not_hide_programming_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readiness = SqlAlchemyPlatformReadiness("postgresql+psycopg://user:p@db/app")

    async def programmer_bug() -> set[str] | None:
        raise AssertionError("bug remains visible")

    monkeypatch.setattr(readiness, "_read_current_heads", programmer_bug)
    with pytest.raises(AssertionError, match="bug remains visible"):
        await readiness.check()
