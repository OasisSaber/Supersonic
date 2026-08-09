from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from .models import AuditEvent, PlatformSession, User


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get_by_id(self, user_id: str) -> User | None: ...

    async def get_by_username_norm(self, username_norm: str) -> User | None: ...


class PlatformSessionRepository(Protocol):
    async def add(self, platform_session: PlatformSession) -> None: ...

    async def get_by_token_digest(self, token_digest: str) -> PlatformSession | None: ...


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
