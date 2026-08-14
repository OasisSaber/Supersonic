from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.postgres.database import create_database_engine, create_session_factory
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from app.platform.audit_fallback import JsonlAuditFallback
from app.platform.audit_identity import AuditEventConflict
from app.platform.audit_reconciliation import AuditReconciler
from app.platform.models import AuditDelivery, AuditEvent, AuditResult

EVENT = AuditEvent(
    id="11111111-1111-4111-8111-111111111111",
    occurred_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
    action="cockpit.command",
    result=AuditResult.SUCCEEDED,
    delivery=AuditDelivery.FALLBACK,
    parameters={"command": "set_theme"},
)


@pytest.fixture
async def audit_session_factory(
    migrated_database_url: str,
):
    engine = create_database_engine(migrated_database_url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def test_same_uuid_same_canonical_event_is_idempotent(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    reconciler = AuditReconciler(
        uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(audit_session_factory)
    )

    first = await reconciler.reconcile([EVENT], dry_run=False)
    second = await reconciler.reconcile([EVENT], dry_run=False)

    assert (first.imported, first.duplicates) == (1, 0)
    assert (second.imported, second.duplicates) == (0, 1)


async def test_same_uuid_different_canonical_event_is_conflict(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    reconciler = AuditReconciler(
        uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(audit_session_factory)
    )
    await reconciler.reconcile([EVENT], dry_run=False)

    conflicting = replace(EVENT, parameters={"command": "set_system_mode"})
    with pytest.raises(AuditEventConflict):
        await reconciler.reconcile([conflicting], dry_run=False)


async def test_reconcile_file_conflict_keeps_source_unarchived(
    audit_session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    reconciler = AuditReconciler(
        uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(audit_session_factory)
    )
    await reconciler.reconcile([EVENT], dry_run=False)

    fallback = JsonlAuditFallback(tmp_path / "audit-fallback.jsonl")
    fallback.append(replace(EVENT, parameters={"command": "set_system_mode"}))

    with pytest.raises(AuditEventConflict):
        await reconciler.reconcile_file(fallback, dry_run=False)

    assert fallback.path.is_file()
    assert not list(tmp_path.glob("audit-fallback.jsonl.reconciled-*"))
