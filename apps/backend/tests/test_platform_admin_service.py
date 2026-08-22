from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.platform.admin import (
    AdminForbidden,
    AdminMutationResult,
    AdminSessionNotFound,
    AdminUserNotFound,
    LastAdminProtected,
    SelfManagementForbidden,
    SessionSummary,
    UserAdminService,
    UserSummary,
)
from app.platform.audit_identity import AuditEventConflict
from app.platform.models import (
    AuditDelivery,
    AuditEvent,
    AuditResult,
    PlatformSession,
    Principal,
    Role,
    User,
)
from app.platform.persistence import DatabaseUnavailable, PlatformReadiness

NOW = datetime(2026, 8, 21, 10, tzinfo=UTC)
ADMIN_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"
SESSION_1_ID = "33333333-3333-4333-8333-333333333333"
SESSION_2_ID = "44444444-4444-4444-8444-444444444444"
AUDIT_ID = "99999999-9999-4999-8999-999999999999"


def make_user(
    user_id: str,
    role: Role,
    *,
    disabled: bool = False,
    username: str | None = None,
) -> User:
    return User(
        id=user_id,
        username_norm=username or role.value,
        display_name=(username or role.value).title(),
        password_hash="$argon2id$sensitive-test-hash",
        role=role,
        disabled_at=NOW if disabled else None,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(days=1),
    )


ADMIN = make_user(ADMIN_ID, Role.ADMIN, username="admin")
OPERATOR = make_user(OPERATOR_ID, Role.OPERATOR, username="operator")
ADMIN_PRINCIPAL = Principal(
    user_id=ADMIN_ID,
    role=Role.ADMIN,
    session_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
)
NON_ADMIN_PRINCIPAL = Principal(
    user_id=OPERATOR_ID,
    role=Role.OPERATOR,
    session_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
)


def make_session(
    session_id: str,
    user_id: str = OPERATOR_ID,
    *,
    revoked: bool = False,
) -> PlatformSession:
    return PlatformSession(
        id=session_id,
        user_id=user_id,
        token_digest="d" * 64,
        created_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=7),
        last_seen_at=NOW - timedelta(minutes=1),
        revoked_at=NOW - timedelta(seconds=1) if revoked else None,
        revoke_reason="already_revoked" if revoked else None,
    )


class Ready:
    def __init__(self) -> None:
        self.calls = 0

    async def check(self) -> PlatformReadiness:
        self.calls += 1
        return PlatformReadiness.READY


class UserRepository:
    def __init__(self, users: list[User], calls: list[str]) -> None:
        self.values = {user.id: user for user in users}
        self.calls = calls
        self.lock_calls: list[Role] = []
        self.set_role_result = True
        self.set_disabled_result = True

    async def get_by_id(self, user_id: str) -> User | None:
        self.calls.append("users.get_by_id")
        return self.values.get(user_id)

    async def list_all(self, limit: int) -> tuple[User, ...]:
        self.calls.append(f"users.list_all:{limit}")
        ordered = sorted(self.values.values(), key=lambda user: user.username_norm)
        return tuple(ordered[:limit])

    async def set_role(self, user_id: str, role: Role, updated_at: datetime) -> bool:
        self.calls.append("users.set_role")
        user = self.values.get(user_id)
        if user is None or not self.set_role_result:
            return False
        self.values[user_id] = replace(user, role=role, updated_at=updated_at)
        return True

    async def set_disabled(
        self,
        user_id: str,
        disabled_at: datetime | None,
        updated_at: datetime,
    ) -> bool:
        self.calls.append("users.set_disabled")
        user = self.values.get(user_id)
        if user is None or not self.set_disabled_result:
            return False
        self.values[user_id] = replace(
            user,
            disabled_at=disabled_at,
            updated_at=updated_at,
        )
        return True

    async def lock_enabled_role_holder_ids(self, role: Role) -> tuple[str, ...]:
        self.calls.append("users.lock_enabled_role_holder_ids")
        self.lock_calls.append(role)
        return tuple(
            user.id
            for user in self.values.values()
            if user.role is role and user.disabled_at is None
        )


class SessionRepository:
    def __init__(self, sessions: list[PlatformSession], calls: list[str]) -> None:
        self.values = {session.id: session for session in sessions}
        self.calls = calls

    async def get_by_id(self, session_id: str) -> PlatformSession | None:
        self.calls.append("sessions.get_by_id")
        return self.values.get(session_id)

    async def list_for_user(
        self,
        user_id: str,
        limit: int,
    ) -> tuple[PlatformSession, ...]:
        self.calls.append(f"sessions.list_for_user:{limit}")
        return tuple(session for session in self.values.values() if session.user_id == user_id)[
            :limit
        ]

    async def revoke(
        self,
        session_id: str,
        revoked_at: datetime,
        reason: str | None,
    ) -> bool:
        self.calls.append("sessions.revoke")
        session = self.values.get(session_id)
        if session is None or session.revoked_at is not None:
            return False
        self.values[session_id] = replace(
            session,
            revoked_at=revoked_at,
            revoke_reason=reason,
        )
        return True

    async def revoke_all_for_user(
        self,
        user_id: str,
        revoked_at: datetime,
        reason: str,
    ) -> tuple[str, ...]:
        self.calls.append("sessions.revoke_all_for_user")
        changed: list[str] = []
        for session_id, session in list(self.values.items()):
            if session.user_id == user_id and session.revoked_at is None:
                self.values[session_id] = replace(
                    session,
                    revoked_at=revoked_at,
                    revoke_reason=reason,
                )
                changed.append(session_id)
        return tuple(changed)


class AuditRepository:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.events: list[AuditEvent] = []
        self.inserted = True
        self.existing: AuditEvent | None = None

    async def append(self, event: AuditEvent) -> bool:
        self.calls.append("audit.append")
        self.events.append(event)
        return self.inserted

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        self.calls.append("audit.get_by_id")
        return self.existing


class Uow:
    def __init__(
        self,
        users: list[User],
        sessions: list[PlatformSession] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.users = UserRepository(users, self.calls)
        self.platform_sessions = SessionRepository(sessions or [], self.calls)
        self.audit_events = AuditRepository(self.calls)
        self.commit_error: Exception | None = None

    async def __aenter__(self) -> Uow:
        self.calls.append("enter")
        return self

    async def __aexit__(self, *args: object) -> None:
        self.calls.append("exit")

    async def commit(self) -> None:
        self.calls.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.calls.append("rollback")


def service(
    uow: Uow,
    *,
    readiness: Ready | None = None,
    on_revoke: Any = None,
) -> UserAdminService:
    return UserAdminService(
        readiness=readiness or Ready(),
        uow_factory=lambda: uow,
        clock=lambda: NOW,
        uuid_factory=lambda: AUDIT_ID,
        on_revoke=on_revoke,
    )


async def test_non_admin_cannot_list_or_mutate_before_database_work() -> None:
    uow = Uow([ADMIN, OPERATOR], [make_session(SESSION_1_ID)])
    subject = service(uow)

    operations = (
        subject.list_users(NON_ADMIN_PRINCIPAL),
        subject.list_sessions(NON_ADMIN_PRINCIPAL, OPERATOR_ID),
        subject.change_role(NON_ADMIN_PRINCIPAL, OPERATOR_ID, Role.VIEWER),
        subject.set_disabled(NON_ADMIN_PRINCIPAL, OPERATOR_ID, disabled=True),
        subject.revoke_session(NON_ADMIN_PRINCIPAL, SESSION_1_ID),
    )
    for operation in operations:
        with pytest.raises(AdminForbidden):
            await operation

    assert uow.calls == []


async def test_lists_sanitized_bounded_user_and_session_summaries() -> None:
    session = make_session(SESSION_1_ID)
    uow = Uow([ADMIN, OPERATOR], [session])
    subject = service(uow)

    users = await subject.list_users(ADMIN_PRINCIPAL, limit=1)
    sessions = await subject.list_sessions(ADMIN_PRINCIPAL, OPERATOR_ID, limit=1)

    assert users == (
        UserSummary(
            id=ADMIN.id,
            username_norm=ADMIN.username_norm,
            display_name=ADMIN.display_name,
            role=ADMIN.role,
            disabled_at=ADMIN.disabled_at,
            created_at=ADMIN.created_at,
            updated_at=ADMIN.updated_at,
        ),
    )
    assert sessions == (
        SessionSummary(
            id=session.id,
            user_id=session.user_id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            last_seen_at=session.last_seen_at,
            revoked_at=session.revoked_at,
            revoke_reason=session.revoke_reason,
        ),
    )
    assert "password_hash" not in {field.name for field in fields(UserSummary)}
    assert "token_digest" not in {field.name for field in fields(SessionSummary)}
    assert uow.calls == [
        "enter",
        "users.list_all:1",
        "exit",
        "enter",
        "users.get_by_id",
        "sessions.list_for_user:1",
        "exit",
    ]


@pytest.mark.parametrize("limit", [0, 101])
async def test_list_limits_reject_before_readiness(limit: int) -> None:
    uow = Uow([ADMIN])
    readiness = Ready()
    subject = service(uow, readiness=readiness)

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        await subject.list_users(ADMIN_PRINCIPAL, limit=limit)
    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        await subject.list_sessions(ADMIN_PRINCIPAL, ADMIN_ID, limit=limit)

    assert readiness.calls == 0
    assert uow.calls == []


async def test_self_role_change_and_self_disable_are_forbidden() -> None:
    uow = Uow([ADMIN])
    subject = service(uow)

    with pytest.raises(SelfManagementForbidden):
        await subject.change_role(ADMIN_PRINCIPAL, ADMIN_ID, Role.VIEWER)
    with pytest.raises(SelfManagementForbidden):
        await subject.set_disabled(ADMIN_PRINCIPAL, ADMIN_ID, disabled=True)

    assert uow.calls == []


@pytest.mark.parametrize("operation", ["demote", "disable"])
async def test_self_management_rejects_equivalent_noncanonical_uuid(
    operation: str,
) -> None:
    mixed_case_id = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    canonical_id = mixed_case_id.lower()
    actor = replace(ADMIN_PRINCIPAL, user_id=canonical_id)
    target = make_user(mixed_case_id, Role.ADMIN, username="same-admin")
    uow = Uow([target])

    with pytest.raises(SelfManagementForbidden):
        if operation == "demote":
            await service(uow).change_role(actor, mixed_case_id, Role.VIEWER)
        else:
            await service(uow).set_disabled(actor, mixed_case_id, disabled=True)

    assert uow.calls == []


@pytest.mark.parametrize("operation", ["demote", "disable"])
async def test_last_enabled_admin_mutation_is_rejected_after_row_lock(
    operation: str,
) -> None:
    target = make_user(OPERATOR_ID, Role.ADMIN, username="target-admin")
    actor = replace(ADMIN_PRINCIPAL, user_id="actor-not-in-repository")
    uow = Uow([target])
    subject = service(uow)

    with pytest.raises(LastAdminProtected):
        if operation == "demote":
            await subject.change_role(actor, target.id, Role.VIEWER)
        else:
            await subject.set_disabled(actor, target.id, disabled=True)

    assert uow.users.lock_calls == [Role.ADMIN]
    assert "commit" not in uow.calls


async def test_role_change_updates_revokes_audits_and_commits_in_one_uow() -> None:
    sessions = [make_session(SESSION_1_ID), make_session(SESSION_2_ID)]
    uow = Uow([ADMIN, OPERATOR], sessions)
    callback_observations: list[tuple[str, tuple[str, ...]]] = []

    async def on_revoke(session_id: str) -> None:
        callback_observations.append((session_id, tuple(uow.calls)))

    result = await service(uow, on_revoke=on_revoke).change_role(
        ADMIN_PRINCIPAL,
        OPERATOR_ID,
        Role.VIEWER,
    )

    assert result == AdminMutationResult(
        changed=True,
        revoked_session_ids=(SESSION_1_ID, SESSION_2_ID),
    )
    assert uow.users.values[OPERATOR_ID].role is Role.VIEWER
    assert uow.calls == [
        "enter",
        "users.get_by_id",
        "users.set_role",
        "sessions.revoke_all_for_user",
        "audit.append",
        "commit",
        "exit",
    ]
    assert [item[0] for item in callback_observations] == [SESSION_1_ID, SESSION_2_ID]
    assert all("commit" in calls and calls[-1] == "exit" for _, calls in callback_observations)
    event = uow.audit_events.events[0]
    assert event.action == "user.role_change"
    assert event.result is AuditResult.SUCCEEDED
    assert event.delivery is AuditDelivery.PRIMARY
    assert event.actor_user_id == ADMIN_PRINCIPAL.user_id
    assert event.actor_platform_session_id == ADMIN_PRINCIPAL.session_id
    assert event.actor_role is ADMIN_PRINCIPAL.role
    assert event.target_id == OPERATOR_ID


async def test_disable_and_enable_are_audited_but_only_disable_revokes() -> None:
    disable_uow = Uow([ADMIN, OPERATOR], [make_session(SESSION_1_ID)])
    disabled = await service(disable_uow).set_disabled(
        ADMIN_PRINCIPAL,
        OPERATOR_ID,
        disabled=True,
    )

    assert disabled.revoked_session_ids == (SESSION_1_ID,)
    assert disable_uow.calls[2:6] == [
        "users.set_disabled",
        "sessions.revoke_all_for_user",
        "audit.append",
        "commit",
    ]
    assert disable_uow.audit_events.events[0].action == "user.disable"

    disabled_user = make_user(OPERATOR_ID, Role.OPERATOR, disabled=True)
    enable_uow = Uow([ADMIN, disabled_user], [make_session(SESSION_2_ID)])
    enabled = await service(enable_uow).set_disabled(
        ADMIN_PRINCIPAL,
        OPERATOR_ID,
        disabled=False,
    )

    assert enabled == AdminMutationResult(changed=True)
    assert "sessions.revoke_all_for_user" not in enable_uow.calls
    assert "sessions.revoke" not in enable_uow.calls
    assert enable_uow.audit_events.events[0].action == "user.enable"
    assert enable_uow.platform_sessions.values[SESSION_2_ID].revoked_at is None


async def test_commit_failure_never_calls_revoke_callback() -> None:
    uow = Uow([ADMIN, OPERATOR], [make_session(SESSION_1_ID)])
    uow.commit_error = DatabaseUnavailable()
    callback_ids: list[str] = []

    async def on_revoke(session_id: str) -> None:
        callback_ids.append(session_id)

    with pytest.raises(DatabaseUnavailable):
        await service(uow, on_revoke=on_revoke).change_role(
            ADMIN_PRINCIPAL,
            OPERATOR_ID,
            Role.VIEWER,
        )

    assert callback_ids == []


async def test_callback_failure_reports_explicit_degraded_ids_after_durable_change() -> None:
    uow = Uow(
        [ADMIN, OPERATOR],
        [make_session(SESSION_1_ID), make_session(SESSION_2_ID)],
    )

    async def on_revoke(session_id: str) -> None:
        if session_id == SESSION_2_ID:
            raise RuntimeError("registry unavailable")

    result = await service(uow, on_revoke=on_revoke).change_role(
        ADMIN_PRINCIPAL,
        OPERATOR_ID,
        Role.VIEWER,
    )

    assert result.changed is True
    assert result.revoked_session_ids == (SESSION_1_ID, SESSION_2_ID)
    assert result.revoke_propagation_failed_ids == (SESSION_2_ID,)
    assert "commit" in uow.calls


async def test_audit_event_conflict_propagates_without_commit_or_callback() -> None:
    uow = Uow([ADMIN, OPERATOR], [make_session(SESSION_1_ID)])
    uow.audit_events.inserted = False
    callback_ids: list[str] = []

    async def on_revoke(session_id: str) -> None:
        callback_ids.append(session_id)

    with pytest.raises(AuditEventConflict) as caught:
        await service(uow, on_revoke=on_revoke).change_role(
            ADMIN_PRINCIPAL,
            OPERATOR_ID,
            Role.VIEWER,
        )

    assert caught.value.event_id == AUDIT_ID
    assert "audit.get_by_id" in uow.calls
    assert "commit" not in uow.calls
    assert callback_ids == []


async def test_not_found_and_no_op_results_do_not_commit() -> None:
    missing_user_uow = Uow([ADMIN])
    with pytest.raises(AdminUserNotFound):
        await service(missing_user_uow).list_sessions(ADMIN_PRINCIPAL, OPERATOR_ID)
    with pytest.raises(AdminUserNotFound):
        await service(missing_user_uow).change_role(
            ADMIN_PRINCIPAL,
            OPERATOR_ID,
            Role.VIEWER,
        )

    role_noop_uow = Uow([ADMIN, OPERATOR])
    role_result = await service(role_noop_uow).change_role(
        ADMIN_PRINCIPAL,
        OPERATOR_ID,
        Role.OPERATOR,
    )
    disabled = make_user(OPERATOR_ID, Role.OPERATOR, disabled=True)
    disable_noop_uow = Uow([ADMIN, disabled])
    disable_result = await service(disable_noop_uow).set_disabled(
        ADMIN_PRINCIPAL,
        OPERATOR_ID,
        disabled=True,
    )

    assert role_result == AdminMutationResult(changed=False)
    assert disable_result == AdminMutationResult(changed=False)
    assert "commit" not in role_noop_uow.calls
    assert "commit" not in disable_noop_uow.calls


async def test_revoke_session_not_found_and_noop_paths() -> None:
    missing_uow = Uow([ADMIN])
    with pytest.raises(AdminSessionNotFound):
        await service(missing_uow).revoke_session(ADMIN_PRINCIPAL, SESSION_1_ID)

    already_uow = Uow([ADMIN], [make_session(SESSION_1_ID, revoked=True)])
    already = await service(already_uow).revoke_session(
        ADMIN_PRINCIPAL,
        SESSION_1_ID,
    )
    assert already == AdminMutationResult(changed=False)
    assert "commit" not in already_uow.calls


async def test_revoke_session_commits_before_callback_with_complete_attribution() -> None:
    success_uow = Uow([ADMIN, OPERATOR], [make_session(SESSION_1_ID)])

    async def on_revoke(session_id: str) -> None:
        success_uow.calls.append(f"callback:{session_id}")

    changed = await service(success_uow, on_revoke=on_revoke).revoke_session(
        ADMIN_PRINCIPAL,
        SESSION_1_ID,
        reason="security_review",
    )

    assert changed == AdminMutationResult(
        changed=True,
        revoked_session_ids=(SESSION_1_ID,),
    )
    assert success_uow.calls == [
        "enter",
        "sessions.get_by_id",
        "sessions.revoke",
        "audit.append",
        "commit",
        "exit",
        f"callback:{SESSION_1_ID}",
    ]
    event = success_uow.audit_events.events[0]
    assert event.action == "session.revoke"
    assert event.result is AuditResult.SUCCEEDED
    assert event.delivery is AuditDelivery.PRIMARY
    assert event.actor_user_id == ADMIN_ID
    assert event.actor_platform_session_id == ADMIN_PRINCIPAL.session_id
    assert event.actor_role is Role.ADMIN
    assert event.target_type == "platform_session"
    assert event.target_id == SESSION_1_ID
    assert event.parameters == {
        "targetUserId": OPERATOR_ID,
        "reason": "security_review",
    }


async def test_revoke_session_commit_failure_does_not_call_callback() -> None:
    uow = Uow([ADMIN, OPERATOR], [make_session(SESSION_1_ID)])
    uow.commit_error = DatabaseUnavailable()
    callback_ids: list[str] = []

    async def on_revoke(session_id: str) -> None:
        callback_ids.append(session_id)

    with pytest.raises(DatabaseUnavailable):
        await service(uow, on_revoke=on_revoke).revoke_session(
            ADMIN_PRINCIPAL,
            SESSION_1_ID,
        )

    assert callback_ids == []
    assert uow.calls == [
        "enter",
        "sessions.get_by_id",
        "sessions.revoke",
        "audit.append",
        "commit",
        "exit",
    ]


async def test_revoke_session_callback_failure_reports_exact_degraded_id() -> None:
    uow = Uow([ADMIN, OPERATOR], [make_session(SESSION_1_ID)])

    async def on_revoke(session_id: str) -> None:
        assert session_id == SESSION_1_ID
        raise RuntimeError("registry unavailable")

    result = await service(uow, on_revoke=on_revoke).revoke_session(
        ADMIN_PRINCIPAL,
        SESSION_1_ID,
    )

    assert result.changed is True
    assert result.revoked_session_ids == (SESSION_1_ID,)
    assert result.revoke_propagation_failed_ids == (SESSION_1_ID,)
    assert uow.calls[-2:] == ["commit", "exit"]


@pytest.mark.parametrize("reason", ["", "   ", "x" * 65])
async def test_revoke_reason_is_bounded_before_database_work(reason: str) -> None:
    uow = Uow([ADMIN], [make_session(SESSION_1_ID)])
    with pytest.raises(ValueError, match="reason must be 1 to 64 characters"):
        await service(uow).revoke_session(
            ADMIN_PRINCIPAL,
            SESSION_1_ID,
            reason=reason,
        )
    assert uow.calls == []
