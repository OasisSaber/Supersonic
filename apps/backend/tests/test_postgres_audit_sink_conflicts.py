from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.adapters.postgres.audit_sink import PostgresAuditSink
from app.platform.audit_identity import AuditEventConflict
from app.platform.models import AuditDelivery, AuditEvent, AuditResult
from app.platform.persistence import PlatformReadiness

EVENT = AuditEvent(
    id="11111111-1111-4111-8111-111111111111",
    occurred_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
    action="cockpit.command",
    result=AuditResult.SUCCEEDED,
    delivery=AuditDelivery.PRIMARY,
    parameters={"command": "set_theme"},
)


class Readiness:
    async def check(self) -> PlatformReadiness:
        return PlatformReadiness.READY


class Repository:
    def __init__(self, *, inserted: bool, existing: AuditEvent | None) -> None:
        self.inserted = inserted
        self.existing = existing
        self.get_calls: list[str] = []

    async def append(self, event: AuditEvent) -> bool:
        return self.inserted

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        self.get_calls.append(event_id)
        return self.existing

    async def list_page(self, query: object) -> object:
        raise AssertionError(query)


class Uow:
    def __init__(self, repository: Repository) -> None:
        self.audit_events = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


async def test_duplicate_same_fact_is_idempotent() -> None:
    repository = Repository(inserted=False, existing=EVENT)
    uow = Uow(repository)
    sink = PostgresAuditSink(readiness=Readiness(), uow_factory=lambda: uow)

    assert await sink.append(EVENT) is False
    assert repository.get_calls == [EVENT.id]
    assert uow.commits == 1


async def test_duplicate_different_fact_raises_conflict_before_success() -> None:
    existing = replace(EVENT, parameters={"command": "set_system_mode"})
    repository = Repository(inserted=False, existing=existing)
    uow = Uow(repository)
    sink = PostgresAuditSink(readiness=Readiness(), uow_factory=lambda: uow)

    with pytest.raises(AuditEventConflict):
        await sink.append(EVENT)

    assert uow.commits == 0
