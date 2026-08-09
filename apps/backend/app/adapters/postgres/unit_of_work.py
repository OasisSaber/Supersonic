from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.platform.persistence import PlatformUnitOfWork

from .repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyPlatformSessionRepository,
    SqlAlchemyUserRepository,
)


class SqlAlchemyPlatformUnitOfWork(PlatformUnitOfWork):
    users: SqlAlchemyUserRepository
    platform_sessions: SqlAlchemyPlatformSessionRepository
    audit_events: SqlAlchemyAuditEventRepository

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("unit of work is already active")

        self._session = self._session_factory()
        self._committed = False
        self.users = SqlAlchemyUserRepository(self._session)
        self.platform_sessions = SqlAlchemyPlatformSessionRepository(self._session)
        self.audit_events = SqlAlchemyAuditEventRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if exc_type is not None or not self._committed:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._committed = False

    async def commit(self) -> None:
        session = self._require_session()
        await session.commit()
        self._committed = True

    async def rollback(self) -> None:
        session = self._require_session()
        await session.rollback()
        self._committed = False

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
