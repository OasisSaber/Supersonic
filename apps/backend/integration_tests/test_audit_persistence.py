from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.postgres.database import create_database_engine, create_session_factory
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from app.platform.audit_reconciliation import AuditReconciler
from app.platform.models import (
    AuditCursor,
    AuditDelivery,
    AuditEvent,
    AuditQuery,
    AuditQueryScope,
    AuditResult,
)


@pytest.fixture
async def session_factory(
    migrated_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_database_engine(migrated_database_url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def event(
    *,
    occurred_at: datetime,
    action: str,
    event_id: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        id=event_id or str(uuid4()),
        occurred_at=occurred_at,
        action=action,
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.FALLBACK,
        parameters={"command": "set_theme"},
    )


async def test_audit_query_uses_descending_keyset_and_operational_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    timestamp = datetime(2026, 8, 13, 12, tzinfo=UTC)
    newest = event(
        event_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
        occurred_at=timestamp,
        action="cockpit.command",
    )
    middle = event(
        event_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        occurred_at=timestamp,
        action="risk.detected",
    )
    oldest = event(
        event_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        occurred_at=timestamp - timedelta(seconds=1),
        action="recovery.completed",
    )
    private = event(
        occurred_at=timestamp + timedelta(seconds=1),
        action="auth.login",
    )
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        for audit_event in (oldest, private, middle, newest):
            assert await uow.audit_events.append(audit_event) is True
        await uow.commit()

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        first = await uow.audit_events.list_page(
            AuditQuery(scope=AuditQueryScope.OPERATIONAL, cursor=None, limit=2)
        )
    assert [item.id for item in first.events] == [newest.id, middle.id]
    assert first.next_cursor == AuditCursor(
        occurred_at=middle.occurred_at,
        event_id=middle.id,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        second = await uow.audit_events.list_page(
            AuditQuery(
                scope=AuditQueryScope.OPERATIONAL,
                cursor=first.next_cursor,
                limit=2,
            )
        )
    assert [item.id for item in second.events] == [oldest.id]
    assert second.next_cursor is None


async def test_reconciliation_is_idempotent_after_a_committed_first_import(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    audit_event = event(
        event_id="11111111-1111-4111-8111-111111111111",
        occurred_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
        action="cockpit.command",
    )
    reconciler = AuditReconciler(
        uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(session_factory)
    )

    first = await reconciler.reconcile([audit_event], dry_run=False)
    second = await reconciler.reconcile([audit_event], dry_run=False)

    assert (first.imported, first.duplicates) == (1, 0)
    assert (second.imported, second.duplicates) == (0, 1)
