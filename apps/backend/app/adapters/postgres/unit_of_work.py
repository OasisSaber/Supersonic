from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.platform.persistence import DatabaseUnavailable, PlatformUnitOfWork

from .failures import KNOWN_DATABASE_FAILURES, database_unavailable
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

        try:
            self._session = self._session_factory()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
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
        rollback_failure: tuple[DatabaseUnavailable, BaseException] | None = None
        try:
            if session.in_transaction():
                try:
                    await session.rollback()
                except KNOWN_DATABASE_FAILURES as exc:
                    rollback_failure = (database_unavailable(exc), exc)
        finally:
            try:
                try:
                    await session.close()
                except KNOWN_DATABASE_FAILURES as exc:
                    if rollback_failure is None:
                        raise database_unavailable(exc) from exc
            finally:
                self._session = None
                self._committed = False
        if rollback_failure is not None:
            translated, cause = rollback_failure
            raise translated from cause

    async def commit(self) -> None:
        session = self._require_session()
        try:
            await session.commit()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        self._committed = True

    async def rollback(self) -> None:
        session = self._require_session()
        try:
            await session.rollback()
        except KNOWN_DATABASE_FAILURES as exc:
            raise database_unavailable(exc) from exc
        self._committed = False

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
