from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

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


class Repository:
    def __init__(
        self,
        *,
        append_results: list[bool],
        existing: AuditEvent | None,
    ) -> None:
        self.results = iter(append_results)
        self.existing = existing

    async def append(self, event: AuditEvent) -> bool:
        return next(self.results)

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        return self.existing

    async def list_page(self, query: object) -> object:
        raise AssertionError(query)


class Uow:
    def __init__(self, repository: Repository) -> None:
        self.audit_events = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


async def test_same_file_conflict_fails_before_uow() -> None:
    different = replace(EVENT, parameters={"command": "set_system_mode"})
    reconciler = AuditReconciler(
        uow_factory=lambda: (_ for _ in ()).throw(AssertionError("no uow"))
    )

    with pytest.raises(AuditEventConflict):
        await reconciler.reconcile([EVENT, different], dry_run=False)


async def test_database_duplicate_same_fact_counts_duplicate() -> None:
    repository = Repository(append_results=[False], existing=EVENT)
    uow = Uow(repository)
    reconciler = AuditReconciler(uow_factory=lambda: uow)

    report = await reconciler.reconcile([EVENT], dry_run=False)

    assert report.imported == 0
    assert report.duplicates == 1
    assert uow.committed is True


async def test_database_duplicate_different_fact_fails() -> None:
    existing = replace(EVENT, parameters={"command": "set_system_mode"})
    repository = Repository(append_results=[False], existing=existing)
    uow = Uow(repository)
    reconciler = AuditReconciler(uow_factory=lambda: uow)

    with pytest.raises(AuditEventConflict):
        await reconciler.reconcile([EVENT], dry_run=False)

    assert uow.committed is False
