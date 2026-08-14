from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.dialects import postgresql

from app.adapters.postgres.repositories import SqlAlchemyAuditEventRepository
from app.platform.models import (
    AuditCursor,
    AuditPage,
    AuditQuery,
    AuditQueryScope,
)

NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)
CURSOR = AuditCursor(
    occurred_at=NOW - timedelta(minutes=1),
    event_id="11111111-1111-4111-8111-111111111111",
)


class _ScalarResult:
    def scalars(self) -> _ScalarResult:
        return self

    def all(self) -> list[object]:
        return []


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        return _ScalarResult()


@pytest.mark.parametrize(
    ("scope", "must_include", "must_exclude"),
    [
        (AuditQueryScope.ALL, "FROM audit_events", "action LIKE"),
        (AuditQueryScope.OPERATIONAL, "action LIKE", "auth.login"),
    ],
)
async def test_audit_repository_compiles_bounded_role_scope_query(
    scope: AuditQueryScope,
    must_include: str,
    must_exclude: str,
) -> None:
    session = _RecordingSession()
    repository = SqlAlchemyAuditEventRepository(session)  # type: ignore[arg-type]

    page = await repository.list_page(AuditQuery(scope=scope, cursor=CURSOR, limit=7))

    statement = session.statements[0]
    rendered = str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[union-attr]
    assert page == AuditPage(events=(), next_cursor=None)
    assert "ORDER BY audit_events.occurred_at DESC, audit_events.id DESC" in rendered
    assert "LIMIT %(param_1)s" in rendered
    assert "audit_events.occurred_at <" in rendered
    assert "audit_events.occurred_at =" in rendered
    assert "audit_events.id <" in rendered
    assert must_include in rendered
    assert must_exclude not in rendered
    assert statement.compile().params["param_1"] == 8  # type: ignore[union-attr]
