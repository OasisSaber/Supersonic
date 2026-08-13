from __future__ import annotations

from dataclasses import replace
from typing import Protocol, cast

from .models import (
    AuditCursor,
    AuditEvent,
    AuditPage,
    AuditQuery,
    AuditQueryScope,
    Role,
)
from .persistence import PlatformReadinessPort, PlatformUnitOfWork
from .sanitization import sanitize_audit_event


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> PlatformUnitOfWork: ...


class AuditQueryService:
    """Read bounded, role-scoped audit history without a transport dependency."""

    def __init__(
        self,
        *,
        readiness: PlatformReadinessPort,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._readiness = readiness
        self._uow_factory = uow_factory

    async def list_for_role(
        self,
        role: Role,
        *,
        cursor: AuditCursor | None = None,
        limit: int = 50,
    ) -> AuditPage:
        query = AuditQuery(
            scope=_scope_for_role(role),
            cursor=cursor,
            limit=limit,
        )
        await self._readiness.check()
        async with self._uow_factory() as uow:
            page = await uow.audit_events.list_page(query)
        return AuditPage(
            events=tuple(_sanitize_event(event) for event in page.events),
            next_cursor=page.next_cursor,
        )


def _scope_for_role(role: Role) -> AuditQueryScope:
    if role is Role.ADMIN:
        return AuditQueryScope.ALL
    if role in {Role.OPERATOR, Role.VIEWER}:
        return AuditQueryScope.OPERATIONAL
    raise ValueError("role must be an approved platform role")


def _sanitize_event(event: AuditEvent) -> AuditEvent:
    sanitized = sanitize_audit_event(event)
    return replace(sanitized, parameters=cast(dict[str, object], sanitized.parameters))
