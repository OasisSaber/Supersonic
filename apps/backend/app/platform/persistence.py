from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self

from .models import AuditEvent, PlatformSession, User


class PlatformPersistenceError(RuntimeError):
    """Framework-free platform persistence infrastructure failure."""


PersistenceFailure = PlatformPersistenceError


class DatabaseUnavailable(PlatformPersistenceError):
    def __init__(self) -> None:
        super().__init__("Platform database is unavailable.")


class MigrationRequired(PersistenceFailure):
    def __init__(self) -> None:
        super().__init__("Platform database migration is required.")


class PlatformReadiness(StrEnum):
    READY = "ready"


class PlatformReadinessPort(Protocol):
    async def check(self) -> PlatformReadiness: ...


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get_by_id(self, user_id: str) -> User | None: ...

    async def get_by_username_norm(self, username_norm: str) -> User | None: ...

    async def update_password_hash(
        self, user_id: str, password_hash: str, updated_at: datetime
    ) -> bool: ...


class PlatformSessionRepository(Protocol):
    async def add(self, platform_session: PlatformSession) -> None: ...

    async def get_by_token_digest(self, token_digest: str) -> PlatformSession | None: ...

    async def get_by_id(self, platform_session_id: str) -> PlatformSession | None: ...

    async def revoke(
        self,
        platform_session_id: str,
        revoked_at: datetime,
        reason: str | None,
    ) -> bool: ...


class AuditEventRepository(Protocol):
    async def append(self, event: AuditEvent) -> bool: ...


class PlatformUnitOfWork(Protocol):
    users: UserRepository
    platform_sessions: PlatformSessionRepository
    audit_events: AuditEventRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
