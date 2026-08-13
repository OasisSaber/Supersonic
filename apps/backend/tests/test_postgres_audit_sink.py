from __future__ import annotations

from datetime import UTC, datetime

from app.adapters.postgres.audit_sink import PostgresAuditSink
from app.platform.models import AuditDelivery, AuditEvent, AuditResult
from app.platform.persistence import PlatformReadiness

EVENT = AuditEvent(
    id="11111111-1111-4111-8111-111111111111",
    occurred_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
    action="cockpit.command",
    result=AuditResult.SUCCEEDED,
    delivery=AuditDelivery.PRIMARY,
)


class _Readiness:
    def __init__(self) -> None:
        self.calls = 0

    async def check(self) -> PlatformReadiness:
        self.calls += 1
        return PlatformReadiness.READY


class _Repository:
    def __init__(self, inserted: bool, *, existing: AuditEvent | None = None) -> None:
        self.inserted = inserted
        self.events: list[AuditEvent] = []
        self.existing = existing

    async def append(self, event: AuditEvent) -> bool:
        self.events.append(event)
        return self.inserted

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        return self.existing

    async def list_page(self, query: object) -> object:
        raise AssertionError(f"sink must not query audit history: {query}")


class _UnitOfWork:
    def __init__(self, repository: _Repository) -> None:
        self.audit_events = repository
        self.commits = 0

    async def __aenter__(self) -> _UnitOfWork:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


async def test_primary_sink_checks_readiness_commits_and_preserves_idempotency_result() -> None:
    readiness = _Readiness()
    repository = _Repository(inserted=False, existing=EVENT)
    uow = _UnitOfWork(repository)
    sink = PostgresAuditSink(readiness=readiness, uow_factory=lambda: uow)

    inserted = await sink.append(EVENT)

    assert inserted is False
    assert readiness.calls == 1
    assert repository.events == [EVENT]
    assert uow.commits == 1
