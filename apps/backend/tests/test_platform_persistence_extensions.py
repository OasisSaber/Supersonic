from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from app.adapters.postgres.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyPlatformSessionRepository,
    SqlAlchemyUserRepository,
)
from app.platform.models import AuditDelivery, AuditEvent, AuditResult, Role
from app.platform.persistence import (
    DatabaseUnavailable,
    PlatformPersistenceError,
    PlatformSessionRepository,
    UserRepository,
)


class _Result:
    def __init__(self, *, rowcount: int = 0, scalar: object = None) -> None:
        self.rowcount = rowcount
        self._scalar = scalar

    def scalar_one_or_none(self) -> object:
        return self._scalar


class _RecordingSession:
    def __init__(self, result: _Result) -> None:
        self.result = result
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _Result:
        self.statements.append(statement)
        return self.result


def _compiled(statement: object) -> tuple[str, dict[str, Any]]:
    compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[union-attr]
    return str(compiled), compiled.params


def test_narrow_persistence_ports_expose_only_required_extensions() -> None:
    assert inspect.iscoroutinefunction(UserRepository.update_password_hash)
    assert inspect.iscoroutinefunction(PlatformSessionRepository.get_by_id)
    assert inspect.iscoroutinefunction(PlatformSessionRepository.revoke)
    assert not hasattr(UserRepository, "save")
    assert not hasattr(PlatformSessionRepository, "save")


def test_platform_failure_vocabulary_is_framework_free_and_owned_by_the_port() -> None:
    assert issubclass(DatabaseUnavailable, PlatformPersistenceError)
    assert PlatformPersistenceError.__module__ == "app.platform.persistence"


async def test_password_rehash_updates_only_hash_and_updated_at() -> None:
    session = _RecordingSession(_Result(rowcount=1))
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]
    updated_at = datetime(2026, 8, 12, 4, tzinfo=UTC)

    changed = await repository.update_password_hash(
        "11111111-1111-4111-8111-111111111111",
        "$argon2id$new-hash-without-raw-secret",
        updated_at,
    )

    sql, params = _compiled(session.statements[0])
    assert changed is True
    assert sql.startswith("UPDATE users SET password_hash=")
    assert set(params) == {"password_hash", "updated_at", "id_1"}
    assert params["password_hash"] == "$argon2id$new-hash-without-raw-secret"
    assert params["updated_at"] == updated_at
    assert "role" not in sql
    assert "disabled_at" not in sql


async def test_platform_session_revoke_preserves_first_revocation() -> None:
    session = _RecordingSession(_Result(rowcount=1))
    repository = SqlAlchemyPlatformSessionRepository(session)  # type: ignore[arg-type]
    revoked_at = datetime(2026, 8, 12, 5, tzinfo=UTC)

    changed = await repository.revoke(
        "22222222-2222-4222-8222-222222222222",
        revoked_at,
        "operator sign-out",
    )

    sql, params = _compiled(session.statements[0])
    assert changed is True
    assert sql.startswith("UPDATE platform_sessions SET revoked_at=")
    assert "platform_sessions.revoked_at IS NULL" in sql
    assert set(params) == {"revoked_at", "revoke_reason", "id_1"}
    assert params["revoked_at"] == revoked_at
    assert params["revoke_reason"] == "operator sign-out"


@pytest.mark.parametrize("reason", ["", "   ", "x" * 129, 42])
async def test_platform_session_revoke_rejects_empty_or_oversized_reason_before_sql(
    reason: object,
) -> None:
    session = _RecordingSession(_Result(rowcount=1))
    repository = SqlAlchemyPlatformSessionRepository(session)  # type: ignore[arg-type]

    with pytest.raises(
        ValueError,
        match="reason must be a non-empty string of at most 128 characters",
    ):
        await repository.revoke(
            "22222222-2222-4222-8222-222222222222",
            datetime(2026, 8, 12, 5, tzinfo=UTC),
            reason,  # type: ignore[arg-type]
        )

    assert session.statements == []


async def test_platform_session_get_by_id_rejects_invalid_uuid_before_sql() -> None:
    session = _RecordingSession(_Result())
    repository = SqlAlchemyPlatformSessionRepository(session)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="platform_session_id must be a valid UUID"):
        await repository.get_by_id("not-a-uuid")

    assert session.statements == []


async def test_platform_session_get_by_id_translates_known_database_failure() -> None:
    class _FailingSession:
        async def execute(self, statement: object) -> object:
            raise OperationalError("SELECT secret", {}, RuntimeError("driver detail"))

    repository = SqlAlchemyPlatformSessionRepository(_FailingSession())  # type: ignore[arg-type]

    with pytest.raises(DatabaseUnavailable) as caught:
        await repository.get_by_id("22222222-2222-4222-8222-222222222222")

    assert str(caught.value) == "Platform database is unavailable."


async def test_narrow_updates_report_no_changed_row_honestly() -> None:
    updated_at = datetime(2026, 8, 12, 5, tzinfo=UTC)
    user = SqlAlchemyUserRepository(_RecordingSession(_Result(rowcount=0)))  # type: ignore[arg-type]
    platform_session = SqlAlchemyPlatformSessionRepository(
        _RecordingSession(_Result(rowcount=0))  # type: ignore[arg-type]
    )
    assert (
        await user.update_password_hash(
            "11111111-1111-4111-8111-111111111111", "hash", updated_at
        )
        is False
    )
    assert (
        await platform_session.revoke(
            "22222222-2222-4222-8222-222222222222", updated_at, None
        )
        is False
    )


async def test_known_connection_failure_is_translated_without_detail() -> None:
    secret = "raw-secret"

    class _FailingSession:
        async def execute(self, statement: object) -> object:
            raise OperationalError("UPDATE secret", {}, RuntimeError(secret))

    repository = SqlAlchemyUserRepository(_FailingSession())  # type: ignore[arg-type]
    with pytest.raises(DatabaseUnavailable) as caught:
        await repository.update_password_hash(
            "11111111-1111-4111-8111-111111111111",
            "new-hash",
            datetime(2026, 8, 12, 5, tzinfo=UTC),
        )
    assert str(caught.value) == "Platform database is unavailable."
    assert secret not in str(caught.value)


async def test_repository_does_not_hide_programming_errors() -> None:
    class _BuggySession:
        async def execute(self, statement: object) -> object:
            raise AssertionError("program bug")

    repository = SqlAlchemyUserRepository(_BuggySession())  # type: ignore[arg-type]
    with pytest.raises(AssertionError, match="program bug"):
        await repository.update_password_hash(
            "11111111-1111-4111-8111-111111111111",
            "new-hash",
            datetime(2026, 8, 12, 5, tzinfo=UTC),
        )


async def test_user_reads_translate_known_database_failure_without_detail() -> None:
    secret = "SELECT connect-secret"

    class _FailingSession:
        async def execute(self, statement: object) -> object:
            raise OperationalError(secret, {}, RuntimeError("driver detail"))

    session = _FailingSession()
    for read in (
        SqlAlchemyUserRepository(session).get_by_id,  # type: ignore[arg-type]
        SqlAlchemyUserRepository(session).get_by_username_norm,  # type: ignore[arg-type]
    ):
        with pytest.raises(DatabaseUnavailable) as caught:
            await read("11111111-1111-4111-8111-111111111111")
        assert str(caught.value) == "Platform database is unavailable."
        assert secret not in str(caught.value)


@pytest.mark.parametrize("fail_on_flush", [True, False])
async def test_audit_append_translates_known_database_failure_without_detail(
    fail_on_flush: bool,
) -> None:
    secret = "INSERT connect-secret"

    class _FailingSession:
        async def flush(self) -> None:
            if fail_on_flush:
                raise OperationalError(secret, {}, RuntimeError("driver detail"))

        async def execute(self, statement: object) -> object:
            raise OperationalError(secret, {}, RuntimeError("driver detail"))

    repository = SqlAlchemyAuditEventRepository(_FailingSession())  # type: ignore[arg-type]
    event = AuditEvent(
        id="33333333-3333-4333-8333-333333333333",
        occurred_at=datetime(2026, 8, 12, 5, tzinfo=UTC),
        action="auth.login",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        actor_user_id="11111111-1111-4111-8111-111111111111",
        actor_role=Role.OPERATOR,
        parameters={},
    )

    with pytest.raises(DatabaseUnavailable) as caught:
        await repository.append(event)
    assert str(caught.value) == "Platform database is unavailable."
    assert secret not in str(caught.value)
