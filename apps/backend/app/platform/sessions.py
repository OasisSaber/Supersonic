from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from .models import (
    AuditDelivery,
    AuditEvent,
    AuditResult,
    PlatformSession,
    Principal,
    Role,
    User,
)
from .persistence import PlatformReadinessPort, PlatformUnitOfWork
from .security import (
    CredentialStoreError,
    PasswordHasher,
    digest_session_token,
    issue_session_token,
)
from .throttle import LoginThrottle


class SessionServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidCredentials(SessionServiceError):
    def __init__(self) -> None:
        super().__init__("invalid_credentials", "Invalid username or password.", 401)


class LoginThrottled(SessionServiceError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("login_throttled", "Too many login attempts.", 429)
        self.retry_after = retry_after


class CredentialStoreInvalid(SessionServiceError):
    def __init__(self) -> None:
        super().__init__(
            "credential_store_invalid",
            "Stored credentials cannot be safely verified.",
            503,
        )


class AuditPersistenceFailure(SessionServiceError):
    def __init__(self) -> None:
        super().__init__(
            "audit_persistence_failure",
            "The result could not be durably audited.",
            503,
        )


class InvalidSession(SessionServiceError):
    """A session secret that cannot identify a currently valid user session."""

    def __init__(self) -> None:
        super().__init__("invalid_session", "Invalid or expired session.", 401)


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    platform_session_id: str
    user_id: str
    display_name: str
    role: Role
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    """Current server-side identity resolved from a platform session secret."""

    principal: Principal
    display_name: str
    expires_at: datetime


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> PlatformUnitOfWork: ...


class SessionService:
    def __init__(
        self,
        *,
        readiness: PlatformReadinessPort,
        uow_factory: UnitOfWorkFactory,
        password_hasher: PasswordHasher,
        throttle: LoginThrottle,
        session_ttl: timedelta,
        clock: Callable[[], datetime],
        uuid_factory: Callable[[], str],
        token_factory: Callable[[], str] = issue_session_token,
    ) -> None:
        if session_ttl <= timedelta(0):
            raise ValueError("session_ttl must be positive")
        self._readiness = readiness
        self._uow_factory = uow_factory
        self._password_hasher = password_hasher
        self._throttle = throttle
        self._session_ttl = session_ttl
        self._clock = clock
        self._uuid_factory = uuid_factory
        self._token_factory = token_factory

    async def resolve(self, raw_secret: str) -> SessionIdentity:
        """Read a current identity without extending or otherwise writing the session."""
        await self._readiness.check()
        token_digest = digest_session_token(raw_secret)
        now = self._now()
        async with self._uow_factory() as uow:
            platform_session = await uow.platform_sessions.get_by_token_digest(token_digest)
            user = await self._resolve_current_user(uow, platform_session, now)
            return SessionIdentity(
                principal=Principal(
                    user_id=user.id,
                    role=user.role,
                    session_id=platform_session.id,
                ),
                display_name=user.display_name,
                expires_at=platform_session.expires_at,
            )

    async def logout(self, raw_secret: str) -> bool:
        """Revoke a valid session. A previously revoked secret is invalid, not success."""
        await self._readiness.check()
        token_digest = digest_session_token(raw_secret)
        now = self._now()
        async with self._uow_factory() as uow:
            platform_session = await uow.platform_sessions.get_by_token_digest(token_digest)
            user = await self._resolve_current_user(uow, platform_session, now)
            revoked = await uow.platform_sessions.revoke(platform_session.id, now, "logout")
            if not revoked:
                raise InvalidSession()
            await self._append_logout_audit(uow, now, user, platform_session.id)
            await uow.commit()
        return True

    async def revoke(self, platform_session_id: str, reason: str) -> bool:
        """Idempotently revoke a session for trusted internal callers.

        This is deliberately not a router-facing administrative API. It returns
        ``False`` for a missing or already revoked session. A successful revoke
        is attributed to the current session user and durably audited.
        """
        self._validate_revoke_reason(reason)
        await self._readiness.check()
        now = self._now()
        async with self._uow_factory() as uow:
            platform_session = await uow.platform_sessions.get_by_id(platform_session_id)
            if platform_session is None or platform_session.revoked_at is not None:
                return False
            user = await self._resolve_current_user(uow, platform_session, now)
            revoked = await uow.platform_sessions.revoke(platform_session.id, now, reason)
            if not revoked:
                return False
            await self._append_revoke_audit(uow, now, user, platform_session.id)
            await uow.commit()
        return True

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return an aware UTC datetime")
        return now.astimezone(UTC)

    @staticmethod
    def _validate_revoke_reason(reason: str) -> None:
        if not reason or not reason.strip() or len(reason) > 64:
            raise ValueError("revoke reason must be 1 to 64 characters")

    @staticmethod
    async def _resolve_current_user(
        uow: PlatformUnitOfWork,
        platform_session: PlatformSession | None,
        now: datetime,
    ) -> User:
        if (
            platform_session is None
            or platform_session.revoked_at is not None
            or platform_session.expires_at <= now
        ):
            raise InvalidSession()
        user = await uow.users.get_by_id(platform_session.user_id)
        if user is None or user.disabled_at is not None:
            raise InvalidSession()
        return user

    async def _append_logout_audit(
        self,
        uow: PlatformUnitOfWork,
        now: datetime,
        user: User,
        platform_session_id: str,
    ) -> None:
        inserted = await uow.audit_events.append(
            AuditEvent(
                id=self._uuid_factory(),
                occurred_at=now,
                action="auth.logout",
                result=AuditResult.SUCCEEDED,
                delivery=AuditDelivery.PRIMARY,
                actor_user_id=user.id,
                actor_platform_session_id=platform_session_id,
                actor_role=user.role,
                parameters={},
            )
        )
        if not inserted:
            raise AuditPersistenceFailure()

    async def _append_revoke_audit(
        self,
        uow: PlatformUnitOfWork,
        now: datetime,
        user: User,
        platform_session_id: str,
    ) -> None:
        inserted = await uow.audit_events.append(
            AuditEvent(
                id=self._uuid_factory(),
                occurred_at=now,
                action="session.revoke",
                result=AuditResult.SUCCEEDED,
                delivery=AuditDelivery.PRIMARY,
                actor_user_id=user.id,
                actor_platform_session_id=platform_session_id,
                actor_role=user.role,
                parameters={},
            )
        )
        if not inserted:
            raise AuditPersistenceFailure()

    async def login(
        self,
        username: str,
        password: str,
        remote_client_key: str,
    ) -> IssuedSession:
        username_norm = username.strip().casefold()
        decision = self._throttle.check(username_norm, remote_client_key)
        if not decision.allowed:
            raise LoginThrottled(decision.retry_after or 1)

        await self._readiness.check()
        now = self._now()
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_username_norm(username_norm)
            if user is None:
                self._password_hasher.dummy_verify(password)
                await self._reject(uow, now, username_norm, remote_client_key)

            try:
                verification = self._password_hasher.verify_and_update(
                    password,
                    user.password_hash,
                )
            except CredentialStoreError:
                raise CredentialStoreInvalid() from None

            if not verification.verified or user.disabled_at is not None:
                await self._reject(uow, now, username_norm, remote_client_key)

            if verification.updated_hash is not None:
                updated = await uow.users.update_password_hash(
                    user.id,
                    verification.updated_hash,
                    now,
                )
                if not updated:
                    raise CredentialStoreInvalid()

            raw_token = self._token_factory()
            platform_session_id = self._uuid_factory()
            expires_at = now + self._session_ttl
            await uow.platform_sessions.add(
                PlatformSession(
                    id=platform_session_id,
                    user_id=user.id,
                    token_digest=digest_session_token(raw_token),
                    created_at=now,
                    expires_at=expires_at,
                )
            )
            inserted = await uow.audit_events.append(
                AuditEvent(
                    id=self._uuid_factory(),
                    occurred_at=now,
                    action="auth.login",
                    result=AuditResult.SUCCEEDED,
                    delivery=AuditDelivery.PRIMARY,
                    actor_user_id=user.id,
                    actor_platform_session_id=platform_session_id,
                    actor_role=user.role,
                    parameters={},
                )
            )
            if not inserted:
                raise AuditPersistenceFailure()
            await uow.commit()

        self._throttle.record_success(username_norm, remote_client_key)
        return IssuedSession(
            token=raw_token,
            platform_session_id=platform_session_id,
            user_id=user.id,
            display_name=user.display_name,
            role=user.role,
            expires_at=expires_at,
        )

    async def _reject(
        self,
        uow: PlatformUnitOfWork,
        now: datetime,
        username_norm: str,
        remote_client_key: str,
    ) -> None:
        self._throttle.record_failure(username_norm, remote_client_key)
        inserted = await uow.audit_events.append(
            AuditEvent(
                id=self._uuid_factory(),
                occurred_at=now,
                action="auth.login",
                result=AuditResult.REJECTED,
                delivery=AuditDelivery.PRIMARY,
                parameters={},
            )
        )
        if not inserted:
            raise AuditPersistenceFailure()
        await uow.commit()
        raise InvalidCredentials()
