from __future__ import annotations

from typing import Protocol

from app.platform.audit_identity import require_matching_duplicate
from app.platform.models import AuditEvent
from app.platform.persistence import PlatformReadinessPort, PlatformUnitOfWork


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> PlatformUnitOfWork: ...


class PostgresAuditSink:
    """Persist one audit fact in an explicit short PostgreSQL transaction."""

    def __init__(
        self,
        *,
        readiness: PlatformReadinessPort,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._readiness = readiness
        self._uow_factory = uow_factory

    async def append(self, event: AuditEvent) -> bool:
        await self._readiness.check()
        async with self._uow_factory() as uow:
            inserted = await uow.audit_events.append(event)
            if not inserted:
                existing = await uow.audit_events.get_by_id(event.id)
                require_matching_duplicate(existing, event)
            await uow.commit()
        return inserted
