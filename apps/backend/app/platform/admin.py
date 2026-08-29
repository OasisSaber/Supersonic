from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from .audit_identity import AuditEventConflict, require_matching_duplicate
from .errors import AuditUnavailable
from .models import (
    AuditDelivery,
    AuditEvent,
    AuditResult,
    PlatformSession,
    Principal,
    Role,
    User,
)
from .persistence import DatabaseUnavailable, PlatformReadinessPort, PlatformUnitOfWork


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


@dataclass(frozen=True, slots=True)
class _ManagementAttempt:
    correlation_id: str
    action: str
    target_type: str
    target_id: str
    parameters: dict[str, object]


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
        async with self._uow_factory() as uow:
            candidate = await uow.users.get_by_id(user_id)
            if candidate is None:
                raise AdminUserNotFound()
            if candidate.role is new_role:
                return AdminMutationResult(changed=False)
        attempt = await self._commit_attempted(
            actor,
            action="user.role_change",
            target_type="user",
            target_id=candidate.id,
            parameters={"oldRole": candidate.role.value, "newRole": new_role.value},
        )
        try:
            result = await self._change_role_after_attempt(actor, candidate.id, new_role, attempt)
        except Exception as error:
            await self._record_failed_outcome(actor, attempt, error)
            raise

        failed_ids = await self._propagate_revokes(result.revoked_session_ids)
        return AdminMutationResult(
            changed=result.changed,
            revoked_session_ids=result.revoked_session_ids,
            revoke_propagation_failed_ids=failed_ids,
        )

    async def _change_role_after_attempt(
        self,
        actor: Principal,
        user_id: str,
        new_role: Role,
        attempt: _ManagementAttempt,
    ) -> AdminMutationResult:
        now = self._now()
        committed_result: AdminMutationResult | None = None
        try:
            async with self._uow_factory() as uow:
                user = await uow.users.get_by_id(user_id)
                if user is None:
                    raise AdminUserNotFound()
                if user.role is new_role:
                    await self._append_outcome(
                        uow,
                        actor,
                        attempt,
                        result=AuditResult.SUCCEEDED,
                        occurred_at=now,
                        parameters={
                            "oldRole": user.role.value,
                            "newRole": new_role.value,
                            "revokedSessionCount": 0,
                        },
                    )
                    await uow.commit()
                    committed_result = AdminMutationResult(changed=False)
                else:
                    if user.role is Role.ADMIN and user.disabled_at is None:
                        await self._protect_enabled_admin(uow, new_role, user.id)

                    if not await uow.users.set_role(
                        user.id,
                        new_role,
                        now,
                        expected_role=user.role,
                    ):
                        current = await uow.users.get_by_id(user.id)
                        if current is None:
                            raise AdminUserNotFound()
                        if current.role is not new_role:
                            raise AdminMutationFailed()
                        revoked_ids: tuple[str, ...] = ()
                        changed = False
                    else:
                        revoked_ids = await uow.platform_sessions.revoke_all_for_user(
                            user.id,
                            now,
                            "role_changed",
                        )
                        changed = True

                    await self._append_outcome(
                        uow,
                        actor,
                        attempt,
                        result=AuditResult.SUCCEEDED,
                        occurred_at=now,
                        parameters={
                            "oldRole": user.role.value,
                            "newRole": new_role.value,
                            "revokedSessionCount": len(revoked_ids),
                        },
                    )
                    await uow.commit()
                    committed_result = AdminMutationResult(
                        changed=changed,
                        revoked_session_ids=revoked_ids,
                    )
        except Exception:
            if committed_result is not None:
                return committed_result
            raise
        if committed_result is None:
            raise RuntimeError("role mutation exited without a committed result")
        return committed_result

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
        async with self._uow_factory() as uow:
            candidate = await uow.users.get_by_id(user_id)
            if candidate is None:
                raise AdminUserNotFound()
            if (candidate.disabled_at is not None) is disabled:
                return AdminMutationResult(changed=False)
        action = "user.disable" if disabled else "user.enable"
        attempt = await self._commit_attempted(
            actor,
            action=action,
            target_type="user",
            target_id=candidate.id,
            parameters={},
        )
        try:
            result = await self._set_disabled_after_attempt(
                actor,
                candidate.id,
                disabled=disabled,
                attempt=attempt,
            )
        except Exception as error:
            await self._record_failed_outcome(actor, attempt, error)
            raise

        failed_ids = await self._propagate_revokes(result.revoked_session_ids)
        return AdminMutationResult(
            changed=result.changed,
            revoked_session_ids=result.revoked_session_ids,
            revoke_propagation_failed_ids=failed_ids,
        )

    async def _set_disabled_after_attempt(
        self,
        actor: Principal,
        user_id: str,
        *,
        disabled: bool,
        attempt: _ManagementAttempt,
    ) -> AdminMutationResult:
        now = self._now()
        committed_result: AdminMutationResult | None = None
        try:
            async with self._uow_factory() as uow:
                user = await uow.users.get_by_id(user_id)
                if user is None:
                    raise AdminUserNotFound()
                if (user.disabled_at is not None) is disabled:
                    await self._append_outcome(
                        uow,
                        actor,
                        attempt,
                        result=AuditResult.SUCCEEDED,
                        occurred_at=now,
                        parameters={"revokedSessionCount": 0},
                    )
                    await uow.commit()
                    committed_result = AdminMutationResult(changed=False)
                else:
                    if disabled and user.role is Role.ADMIN:
                        await self._protect_enabled_admin(uow, Role.VIEWER, user.id)

                    if not await uow.users.set_disabled(
                        user.id,
                        now if disabled else None,
                        now,
                    ):
                        current = await uow.users.get_by_id(user.id)
                        if current is None:
                            raise AdminUserNotFound()
                        if (current.disabled_at is not None) is not disabled:
                            raise AdminMutationFailed()
                        changed = False
                    else:
                        changed = True

                    revoked_ids: tuple[str, ...] = ()
                    if disabled and changed:
                        revoked_ids = await uow.platform_sessions.revoke_all_for_user(
                            user.id,
                            now,
                            "user_disabled",
                        )
                    await self._append_outcome(
                        uow,
                        actor,
                        attempt,
                        result=AuditResult.SUCCEEDED,
                        occurred_at=now,
                        parameters={"revokedSessionCount": len(revoked_ids)},
                    )
                    await uow.commit()
                    committed_result = AdminMutationResult(
                        changed=changed,
                        revoked_session_ids=revoked_ids,
                    )
        except Exception:
            if committed_result is not None:
                return committed_result
            raise
        if committed_result is None:
            raise RuntimeError("disabled mutation exited without a committed result")
        return committed_result

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
        async with self._uow_factory() as uow:
            candidate = await uow.platform_sessions.get_by_id(platform_session_id)
            if candidate is None:
                raise AdminSessionNotFound()
            if candidate.revoked_at is not None:
                return AdminMutationResult(changed=False)
        attempt = await self._commit_attempted(
            actor,
            action="session.revoke",
            target_type="platform_session",
            target_id=candidate.id,
            parameters={"targetUserId": candidate.user_id, "reason": reason},
        )
        try:
            result = await self._revoke_session_after_attempt(
                actor,
                candidate.id,
                reason=reason,
                attempt=attempt,
            )
        except Exception as error:
            await self._record_failed_outcome(actor, attempt, error)
            raise

        failed_ids = await self._propagate_revokes(result.revoked_session_ids)
        return AdminMutationResult(
            changed=result.changed,
            revoked_session_ids=result.revoked_session_ids,
            revoke_propagation_failed_ids=failed_ids,
        )

    async def _revoke_session_after_attempt(
        self,
        actor: Principal,
        platform_session_id: str,
        *,
        reason: str,
        attempt: _ManagementAttempt,
    ) -> AdminMutationResult:
        now = self._now()
        committed_result: AdminMutationResult | None = None
        try:
            async with self._uow_factory() as uow:
                target = await uow.platform_sessions.get_by_id(platform_session_id)
                if target is None:
                    raise AdminSessionNotFound()
                if target.revoked_at is not None:
                    changed = False
                elif await uow.platform_sessions.revoke(target.id, now, reason):
                    changed = True
                else:
                    current = await uow.platform_sessions.get_by_id(target.id)
                    if current is None:
                        raise AdminSessionNotFound()
                    if current.revoked_at is None:
                        raise AdminMutationFailed()
                    changed = False

                await self._append_outcome(
                    uow,
                    actor,
                    attempt,
                    result=AuditResult.SUCCEEDED,
                    occurred_at=now,
                    parameters={"targetUserId": target.user_id, "reason": reason},
                )
                await uow.commit()
                committed_result = AdminMutationResult(
                    changed=changed,
                    revoked_session_ids=(target.id,) if changed else (),
                )
        except Exception:
            if committed_result is not None:
                return committed_result
            raise
        if committed_result is None:
            raise RuntimeError("session revoke exited without a committed result")
        return committed_result

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

    async def _commit_attempted(
        self,
        actor: Principal,
        *,
        action: str,
        target_type: str,
        target_id: str,
        parameters: dict[str, object],
    ) -> _ManagementAttempt:
        correlation_id = self._uuid_factory()
        attempt = _ManagementAttempt(
            correlation_id=correlation_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            parameters=dict(parameters),
        )
        event = self._audit_event(
            actor,
            attempt,
            event_id=correlation_id,
            occurred_at=self._now(),
            result=AuditResult.ATTEMPTED,
            parameters=attempt.parameters,
        )
        try:
            async with self._uow_factory() as uow:
                await self._append_audit(uow, event)
                await uow.commit()
        except AuditEventConflict:
            raise
        except AuditUnavailable:
            raise
        except Exception as error:
            raise AuditUnavailable("Primary attempted audit commit failed.") from error
        return attempt

    async def _append_outcome(
        self,
        uow: PlatformUnitOfWork,
        actor: Principal,
        attempt: _ManagementAttempt,
        *,
        result: AuditResult,
        occurred_at: datetime,
        parameters: dict[str, object],
        error_code: str | None = None,
    ) -> None:
        await self._append_audit(
            uow,
            self._audit_event(
                actor,
                attempt,
                event_id=self._uuid_factory(),
                occurred_at=occurred_at,
                result=result,
                parameters=parameters,
                error_code=error_code,
            ),
        )

    async def _record_failed_outcome(
        self,
        actor: Principal,
        attempt: _ManagementAttempt,
        error: Exception,
    ) -> None:
        result, error_code = _audit_failure(error)
        outcome_committed = False
        try:
            async with self._uow_factory() as uow:
                await self._append_outcome(
                    uow,
                    actor,
                    attempt,
                    result=result,
                    occurred_at=self._now(),
                    parameters=attempt.parameters,
                    error_code=error_code,
                )
                await uow.commit()
                outcome_committed = True
        except Exception as audit_error:
            if outcome_committed:
                return
            audit_error.add_note(
                "The management mutation also failed before this outcome audit error."
            )
            if isinstance(audit_error, AuditEventConflict):
                raise
            raise AuditUnavailable(
                "Primary management outcome audit commit failed."
            ) from audit_error

    @staticmethod
    def _audit_event(
        actor: Principal,
        attempt: _ManagementAttempt,
        *,
        event_id: str,
        occurred_at: datetime,
        result: AuditResult,
        parameters: dict[str, object],
        error_code: str | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            id=event_id,
            occurred_at=occurred_at,
            action=attempt.action,
            result=result,
            delivery=AuditDelivery.PRIMARY,
            actor_user_id=actor.user_id,
            actor_platform_session_id=actor.session_id,
            actor_role=actor.role,
            correlation_id=attempt.correlation_id,
            target_type=attempt.target_type,
            target_id=attempt.target_id,
            parameters=dict(parameters),
            error_code=error_code,
        )

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


def _audit_failure(error: Exception) -> tuple[AuditResult, str]:
    if isinstance(error, AdminServiceError):
        result = AuditResult.REJECTED if error.status_code < 500 else AuditResult.ERROR
        return result, error.code
    if isinstance(error, AuditEventConflict):
        return AuditResult.ERROR, "audit_conflict"
    if isinstance(error, DatabaseUnavailable):
        return AuditResult.ERROR, "database_unavailable"
    if isinstance(error, AuditUnavailable):
        return AuditResult.ERROR, "audit_unavailable"
    return AuditResult.ERROR, "internal_error"


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
