from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.dialects import postgresql

from app.adapters.postgres.orm import PlatformSessionRow, UserRow
from app.adapters.postgres.repositories import (
    SqlAlchemyPlatformSessionRepository,
    SqlAlchemyUserRepository,
)
from app.platform.models import Role


class _Scalars:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class _RowsResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> _Scalars:
        return _Scalars(self._values)


class _UpdateResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _RecordingSession:
    def __init__(self, result: _RowsResult | _UpdateResult) -> None:
        self._result = result
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _RowsResult | _UpdateResult:
        self.statements.append(statement)
        return self._result


def _compiled(statement: object) -> tuple[str, dict[str, Any]]:
    compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[union-attr]
    return str(compiled), compiled.params


async def test_user_list_all_returns_username_ordered_users_within_limit() -> None:
    created_at = datetime(2026, 8, 12, 5, tzinfo=UTC)
    row = UserRow(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        username_norm="ada",
        display_name="Ada",
        password_hash="$argon2id$test-only",
        role=Role.ADMIN.value,
        disabled_at=None,
        created_at=created_at,
        updated_at=created_at,
    )
    session = _RecordingSession(_RowsResult([row]))
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]

    users = await repository.list_all(10)

    sql, params = _compiled(session.statements[0])
    assert tuple(user.username_norm for user in users) == ("ada",)
    assert "ORDER BY users.username_norm ASC" in sql
    assert params["param_1"] == 10


async def test_user_set_role_updates_only_role_and_timestamp() -> None:
    updated_at = datetime(2026, 8, 12, 6, tzinfo=UTC)
    session = _RecordingSession(_UpdateResult(rowcount=1))
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]

    changed = await repository.set_role(
        "11111111-1111-4111-8111-111111111111",
        Role.VIEWER,
        updated_at,
    )

    sql, params = _compiled(session.statements[0])
    assert changed is True
    assert sql.startswith("UPDATE users SET role=")
    assert set(params) == {"role", "updated_at", "id_1"}
    assert params["role"] == Role.VIEWER.value
    assert params["updated_at"] == updated_at


async def test_user_set_disabled_updates_only_disabled_timestamp() -> None:
    disabled_at = datetime(2026, 8, 12, 6, 15, tzinfo=UTC)
    updated_at = datetime(2026, 8, 12, 6, 16, tzinfo=UTC)
    session = _RecordingSession(_UpdateResult(rowcount=0))
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]

    changed = await repository.set_disabled(
        "11111111-1111-4111-8111-111111111111",
        disabled_at,
        updated_at,
    )

    sql, params = _compiled(session.statements[0])
    assert changed is False
    assert sql.startswith("UPDATE users SET disabled_at=")
    assert set(params) == {"disabled_at", "updated_at", "id_1"}
    assert params["disabled_at"] == disabled_at
    assert params["updated_at"] == updated_at


async def test_user_lock_enabled_role_holder_ids_filters_and_locks_in_id_order() -> None:
    first_id = UUID("11111111-1111-4111-8111-111111111111")
    second_id = UUID("22222222-2222-4222-8222-222222222222")
    session = _RecordingSession(_RowsResult([first_id, second_id]))
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]

    user_ids = await repository.lock_enabled_role_holder_ids(Role.ADMIN)

    sql, params = _compiled(session.statements[0])
    assert user_ids == (str(first_id), str(second_id))
    assert "users.role = %(role_1)s" in sql
    assert "users.disabled_at IS NULL" in sql
    assert "ORDER BY users.id ASC FOR UPDATE" in sql
    assert params["role_1"] == Role.ADMIN.value


async def test_platform_session_list_for_user_returns_newest_sessions_within_limit() -> None:
    created_at = datetime(2026, 8, 12, 7, tzinfo=UTC)
    row = PlatformSessionRow(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        user_id=UUID("11111111-1111-4111-8111-111111111111"),
        token_digest="a" * 64,
        created_at=created_at,
        expires_at=datetime(2026, 8, 12, 15, tzinfo=UTC),
        last_seen_at=None,
        revoked_at=None,
        revoke_reason=None,
    )
    session = _RecordingSession(_RowsResult([row]))
    repository = SqlAlchemyPlatformSessionRepository(session)  # type: ignore[arg-type]

    platform_sessions = await repository.list_for_user(
        "11111111-1111-4111-8111-111111111111", 10
    )

    sql, params = _compiled(session.statements[0])
    assert tuple(item.id for item in platform_sessions) == (str(row.id),)
    assert "platform_sessions.user_id = %(user_id_1)s" in sql
    assert "ORDER BY platform_sessions.created_at DESC, platform_sessions.id DESC" in sql
    assert params["param_1"] == 10


async def test_platform_session_revoke_all_for_user_returns_only_changed_ids() -> None:
    first_id = UUID("22222222-2222-4222-8222-222222222222")
    second_id = UUID("33333333-3333-4333-8333-333333333333")
    revoked_at = datetime(2026, 8, 12, 8, tzinfo=UTC)
    session = _RecordingSession(_RowsResult([first_id, second_id]))
    repository = SqlAlchemyPlatformSessionRepository(session)  # type: ignore[arg-type]

    changed_ids = await repository.revoke_all_for_user(
        "11111111-1111-4111-8111-111111111111",
        revoked_at,
        "user disabled",
    )

    sql, params = _compiled(session.statements[0])
    assert changed_ids == (str(first_id), str(second_id))
    assert sql.startswith("UPDATE platform_sessions SET revoked_at=")
    assert "platform_sessions.user_id = %(user_id_1)s" in sql
    assert "platform_sessions.revoked_at IS NULL" in sql
    assert "RETURNING platform_sessions.id" in sql
    assert params["revoked_at"] == revoked_at
    assert params["revoke_reason"] == "user disabled"
