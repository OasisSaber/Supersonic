from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.platform.audit_query import AuditQueryService
from app.platform.models import (
    AuditCursor,
    AuditDelivery,
    AuditEvent,
    AuditPage,
    AuditQuery,
    AuditQueryScope,
    AuditResult,
    Role,
)
from app.platform.persistence import PlatformReadiness

NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)
EVENT_ID = "11111111-1111-4111-8111-111111111111"


def audit_event(*, event_id: str = EVENT_ID) -> AuditEvent:
    return AuditEvent(
        id=event_id,
        occurred_at=NOW,
        action="cockpit.command",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        parameters={"api_key": "must-not-leak", "command": "set_theme"},
    )


class _Readiness:
    def __init__(self) -> None:
        self.calls = 0

    async def check(self) -> PlatformReadiness:
        self.calls += 1
        return PlatformReadiness.READY


class _Repository:
    def __init__(self, page: AuditPage) -> None:
        self.page = page
        self.queries: list[AuditQuery] = []

    async def append(self, event: AuditEvent) -> bool:
        raise AssertionError(f"append must not be called for audit reads: {event.id}")

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        raise AssertionError(f"get_by_id must not be called for audit reads: {event_id}")

    async def list_page(self, query: AuditQuery) -> AuditPage:
        self.queries.append(query)
        return self.page


class _UnitOfWork:
    def __init__(self, repository: _Repository) -> None:
        self.audit_events = repository
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> _UnitOfWork:
        self.entered = True
        return self

    async def __aexit__(self, *args: object) -> None:
        self.exited = True

    async def commit(self) -> None:
        raise AssertionError("audit reads must not commit")

    async def rollback(self) -> None:
        raise AssertionError("audit reads must not roll back explicitly")


@pytest.mark.parametrize(
    ("role", "expected_scope"),
    [
        (Role.ADMIN, AuditQueryScope.ALL),
        (Role.OPERATOR, AuditQueryScope.OPERATIONAL),
        (Role.VIEWER, AuditQueryScope.OPERATIONAL),
    ],
)
async def test_query_service_maps_role_to_scoped_keyset_query(
    role: Role,
    expected_scope: AuditQueryScope,
) -> None:
    cursor = AuditCursor(
        occurred_at=NOW - timedelta(seconds=1),
        event_id="22222222-2222-4222-8222-222222222222",
    )
    event = audit_event()
    raw_page = AuditPage(events=(event,), next_cursor=cursor)
    repository = _Repository(raw_page)
    uow = _UnitOfWork(repository)
    readiness = _Readiness()
    service = AuditQueryService(readiness=readiness, uow_factory=lambda: uow)

    page = await service.list_for_role(role, cursor=cursor, limit=7)

    assert readiness.calls == 1
    assert uow.entered is True
    assert uow.exited is True
    assert repository.queries == [
        AuditQuery(scope=expected_scope, cursor=cursor, limit=7)
    ]
    assert page.next_cursor == cursor
    assert page.events == (
        replace(
            event,
            parameters={"api_key": "[redacted]", "command": "set_theme"},
        ),
    )


@pytest.mark.parametrize("limit", [0, 101])
async def test_query_service_rejects_out_of_range_limit_before_database_work(
    limit: int,
) -> None:
    repository = _Repository(AuditPage(events=(), next_cursor=None))
    uow = _UnitOfWork(repository)
    readiness = _Readiness()
    service = AuditQueryService(readiness=readiness, uow_factory=lambda: uow)

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        await service.list_for_role(Role.ADMIN, limit=limit)

    assert readiness.calls == 0
    assert uow.entered is False
    assert repository.queries == []


def test_cursor_rejects_naive_time_and_invalid_uuid() -> None:
    with pytest.raises(ValueError, match="cursor.occurred_at must be timezone-aware"):
        AuditCursor(occurred_at=datetime(2026, 8, 13, 12), event_id=EVENT_ID)

    with pytest.raises(ValueError, match="cursor.event_id must be a valid UUID"):
        AuditCursor(occurred_at=NOW, event_id="not-a-uuid")
