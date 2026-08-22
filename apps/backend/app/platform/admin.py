from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from .audit_identity import require_matching_duplicate
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


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> PlatformUnitOfWork: ...


class AdminServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AdminForbidden(AdminServiceError):
    def __init__(self) -> None:
        super().__init__("admin_forbidden", "Administrator access is required.", 403)


class AdminUserNotFound(AdminServiceError):
    def __init__(self) -> None:
        super().__init__("user_not_found", "Platform user was not found.", 404)


class AdminSessionNotFound(AdminServiceError):
    def __init__(self) -> None:
        super().__init__("session_not_found", "Platform session was not found.", 404)


class SelfManagementForbidden(AdminServiceError):
    def __init__(self) -> None:
        super().__init__(
            "self_management_forbidden",
            "The current administrator cannot remove its own administrator access.",
            409,
        )


class LastAdminProtected(AdminServiceError):
    def __init__(self) -> None:
        super().__init__(
            "last_admin_protected",
            "The last enabled administrator cannot be removed.",
            409,
        )


class AdminMutationFailed(AdminServiceError):
    def __init__(self) -> None:
        super().__init__(
            "admin_mutation_failed",
            "The requested platform administration change could not be committed.",
            503,
        )


@dataclass(frozen=True, slots=True)
class UserSummary:
    id: str
    username_norm: str
    display_name: str
    role: Role
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SessionSummary:
    id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None
    revoke_reason: str | None


@dataclass(frozen=True, slots=True)
class AdminMutationResult:
    changed: bool
    revoked_session_ids: tuple[str, ...] = ()
    revoke_propagation_failed_ids: tuple[str, ...] = ()


class UserAdminService:
    """Framework-free administration of platform users and sessions."""

    def __init__(
        self,
        *,
        readiness: PlatformReadinessPort,
        uow_factory: UnitOfWorkFactory,
        clock: Callable[[], datetime],
        uuid_factory: Callable[[], str],
        on_revoke: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._readiness = readiness
        self._uow_factory = uow_factory
        self._clock = clock
        self._uuid_factory = uuid_factory
        self._on_revoke = on_revoke

    async def list_users(
        self,
        actor: Principal,
        *,
        limit: int = 100,
    ) -> tuple[UserSummary, ...]:
        self._require_admin(actor)
        self._validate_limit(limit)
        await self._readiness.check()
        async with self._uow_factory() as uow:
            users = await uow.users.list_all(limit)
        return tuple(_user_summary(user) for user in users)

    async def list_sessions(
        self,
        actor: Principal,
        user_id: str,
        *,
        limit: int = 100,
    ) -> tuple[SessionSummary, ...]:
        self._require_admin(actor)
        self._validate_limit(limit)
        await self._readiness.check()
        async with self._uow_factory() as uow:
            if await uow.users.get_by_id(user_id) is None:
                raise AdminUserNotFound()
            sessions = await uow.platform_sessions.list_for_user(user_id, limit)
        return tuple(_session_summary(session) for session in sessions)

    async def change_role(
        self,
        actor: Principal,
        user_id: str,
        new_role: Role,
    ) -> AdminMutationResult:
        self._require_admin(actor)
        if _same_identifier(user_id, actor.user_id):
            raise SelfManagementForbidden()

        await self._readiness.check()
        now = self._now()
        revoked_ids: tuple[str, ...]
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None:
                raise AdminUserNotFound()
            if user.role is new_role:
                return AdminMutationResult(changed=False)
            if user.role is Role.ADMIN and user.disabled_at is None:
                await self._protect_enabled_admin(uow, new_role, user.id)

            if not await uow.users.set_role(user.id, new_role, now):
                raise AdminMutationFailed()
            revoked_ids = await uow.platform_sessions.revoke_all_for_user(
                user.id,
                now,
                "role_changed",
            )
            await self._append_audit(
                uow,
                AuditEvent(
                    id=self._uuid_factory(),
                    occurred_at=now,
                    action="user.role_change",
                    result=AuditResult.SUCCEEDED,
                    delivery=AuditDelivery.PRIMARY,
                    actor_user_id=actor.user_id,
                    actor_platform_session_id=actor.session_id,
                    actor_role=actor.role,
                    target_type="user",
                    target_id=user.id,
                    parameters={
                        "oldRole": user.role.value,
                        "newRole": new_role.value,
                        "revokedSessionCount": len(revoked_ids),
                    },
                ),
            )
            await uow.commit()

        failed_ids = await self._propagate_revokes(revoked_ids)
        return AdminMutationResult(
            changed=True,
            revoked_session_ids=revoked_ids,
            revoke_propagation_failed_ids=failed_ids,
        )

    async def set_disabled(
        self,
        actor: Principal,
        user_id: str,
        *,
        disabled: bool,
    ) -> AdminMutationResult:
        self._require_admin(actor)
        if disabled and _same_identifier(user_id, actor.user_id):
            raise SelfManagementForbidden()

        await self._readiness.check()
        now = self._now()
        revoked_ids: tuple[str, ...] = ()
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None:
                raise AdminUserNotFound()
            if (user.disabled_at is not None) is disabled:
                return AdminMutationResult(changed=False)
            if disabled and user.role is Role.ADMIN:
                await self._protect_enabled_admin(uow, Role.VIEWER, user.id)

            if not await uow.users.set_disabled(
                user.id,
                now if disabled else None,
                now,
            ):
                raise AdminMutationFailed()
            if disabled:
                revoked_ids = await uow.platform_sessions.revoke_all_for_user(
                    user.id,
                    now,
                    "user_disabled",
                )
            await self._append_audit(
                uow,
                AuditEvent(
                    id=self._uuid_factory(),
                    occurred_at=now,
                    action="user.disable" if disabled else "user.enable",
                    result=AuditResult.SUCCEEDED,
                    delivery=AuditDelivery.PRIMARY,
                    actor_user_id=actor.user_id,
                    actor_platform_session_id=actor.session_id,
                    actor_role=actor.role,
                    target_type="user",
                    target_id=user.id,
                    parameters={"revokedSessionCount": len(revoked_ids)},
                ),
            )
            await uow.commit()

        failed_ids = await self._propagate_revokes(revoked_ids)
        return AdminMutationResult(
            changed=True,
            revoked_session_ids=revoked_ids,
            revoke_propagation_failed_ids=failed_ids,
        )

    async def revoke_session(
        self,
        actor: Principal,
        platform_session_id: str,
        *,
        reason: str = "admin_revoke",
    ) -> AdminMutationResult:
        self._require_admin(actor)
        _validate_reason(reason)
        await self._readiness.check()
        now = self._now()

        async with self._uow_factory() as uow:
            target = await uow.platform_sessions.get_by_id(platform_session_id)
            if target is None:
                raise AdminSessionNotFound()
            if target.revoked_at is not None:
                return AdminMutationResult(changed=False)
            if not await uow.platform_sessions.revoke(target.id, now, reason):
                return AdminMutationResult(changed=False)
            await self._append_audit(
                uow,
                AuditEvent(
                    id=self._uuid_factory(),
                    occurred_at=now,
                    action="session.revoke",
                    result=AuditResult.SUCCEEDED,
                    delivery=AuditDelivery.PRIMARY,
                    actor_user_id=actor.user_id,
                    actor_platform_session_id=actor.session_id,
                    actor_role=actor.role,
                    target_type="platform_session",
                    target_id=target.id,
                    parameters={
                        "targetUserId": target.user_id,
                        "reason": reason,
                    },
                ),
            )
            await uow.commit()

        failed_ids = await self._propagate_revokes((target.id,))
        return AdminMutationResult(
            changed=True,
            revoked_session_ids=(target.id,),
            revoke_propagation_failed_ids=failed_ids,
        )

    @staticmethod
    async def _protect_enabled_admin(
        uow: PlatformUnitOfWork,
        new_role: Role,
        target_id: str,
    ) -> None:
        if new_role is Role.ADMIN:
            return
        enabled_admin_ids = await uow.users.lock_enabled_role_holder_ids(Role.ADMIN)
        if target_id in enabled_admin_ids and len(enabled_admin_ids) <= 1:
            raise LastAdminProtected()

    async def _append_audit(
        self,
        uow: PlatformUnitOfWork,
        event: AuditEvent,
    ) -> None:
        if await uow.audit_events.append(event):
            return
        existing = await uow.audit_events.get_by_id(event.id)
        require_matching_duplicate(existing, event)

    async def _propagate_revokes(
        self,
        session_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        if self._on_revoke is None:
            return ()
        failed_ids: list[str] = []
        for session_id in session_ids:
            try:
                await self._on_revoke(session_id)
            except Exception:
                failed_ids.append(session_id)
        return tuple(failed_ids)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return an aware datetime")
        return now.astimezone(UTC)

    @staticmethod
    def _require_admin(actor: Principal) -> None:
        if actor.role is not Role.ADMIN:
            raise AdminForbidden()

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")


def _validate_reason(reason: str) -> None:
    if not reason or not reason.strip() or len(reason) > 64:
        raise ValueError("reason must be 1 to 64 characters")


def _same_identifier(left: str, right: str) -> bool:
    try:
        return UUID(left) == UUID(right)
    except ValueError:
        return left == right


def _user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username_norm=user.username_norm,
        display_name=user.display_name,
        role=user.role,
        disabled_at=user.disabled_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _session_summary(session: PlatformSession) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        user_id=session.user_id,
        created_at=session.created_at,
        expires_at=session.expires_at,
        last_seen_at=session.last_seen_at,
        revoked_at=session.revoked_at,
        revoke_reason=session.revoke_reason,
    )
