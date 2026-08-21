from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.postgres.database import create_database_engine, create_session_factory
from app.adapters.postgres.repositories import SqlAlchemyUserRepository
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from app.api.platform_admin_router import create_platform_admin_router
from app.config import RuntimeSettings
from app.platform.admin import AdminForbidden, LastAdminProtected, UserAdminService
from app.platform.audit_identity import AuditEventConflict
from app.platform.audit_query import AuditQueryService
from app.platform.models import (
    AuditDelivery,
    AuditEvent,
    AuditQuery,
    AuditQueryScope,
    AuditResult,
    PlatformSession,
    Principal,
    Role,
    User,
)
from app.platform.persistence import PlatformReadiness
from app.platform.sessions import SessionIdentity

NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)
ORIGIN = "http://127.0.0.1:5173"
COOKIE = "supersonic_platform_session_dev"


class Ready:
    async def check(self) -> PlatformReadiness:
        return PlatformReadiness.READY


@dataclass(frozen=True, slots=True)
class StaticSessionResolver:
    identity: SessionIdentity

    async def resolve(self, raw_secret: str) -> SessionIdentity:
        assert raw_secret == "integration-secret"
        return self.identity


@pytest.fixture
async def session_factory(
    migrated_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_database_engine(migrated_database_url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _user(role: Role, *, label: str) -> User:
    return User(
        id=str(uuid4()),
        username_norm=f"slice-e-{label}-{uuid4().hex}",
        display_name=f"Slice E {label.title()}",
        password_hash="$argon2id$integration-test-only",
        role=role,
        disabled_at=None,
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
    )


def _session(user: User, *, created_offset: int = 0) -> PlatformSession:
    return PlatformSession(
        id=str(uuid4()),
        user_id=user.id,
        token_digest=uuid4().hex + uuid4().hex,
        created_at=NOW - timedelta(minutes=10 - created_offset),
        expires_at=NOW + timedelta(hours=1),
    )


def _principal(user: User, platform_session: PlatformSession) -> Principal:
    return Principal(
        user_id=user.id,
        role=user.role,
        session_id=platform_session.id,
    )


def _audit_event(
    *,
    event_id: str,
    occurred_at: datetime,
    action: str,
    actor: Principal,
    target_id: str,
) -> AuditEvent:
    return AuditEvent(
        id=event_id,
        occurred_at=occurred_at,
        action=action,
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.PRIMARY,
        actor_user_id=actor.user_id,
        actor_platform_session_id=actor.session_id,
        actor_role=actor.role,
        target_type="user",
        target_id=target_id,
        parameters={"integration": True},
    )


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    users: tuple[User, ...],
    sessions: tuple[PlatformSession, ...] = (),
    audit_events: tuple[AuditEvent, ...] = (),
) -> None:
    # The ORM rows intentionally do not carry relationship attributes, so SQLAlchemy
    # cannot infer a flush dependency between newly added users and sessions. Persist
    # principals first, then add their dependent sessions/audits in a fresh UoW.
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        for user in users:
            await uow.users.add(user)
        await uow.commit()
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        for platform_session in sessions:
            await uow.platform_sessions.add(platform_session)
        for event in audit_events:
            assert await uow.audit_events.append(event) is True
        await uow.commit()


def _admin_service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    audit_id: str,
    on_revoke: Callable[[str], Awaitable[None]] | None = None,
    uow_factory: Callable[[], SqlAlchemyPlatformUnitOfWork] | None = None,
) -> UserAdminService:
    return UserAdminService(
        readiness=Ready(),
        uow_factory=uow_factory or (lambda: SqlAlchemyPlatformUnitOfWork(session_factory)),
        clock=lambda: NOW,
        uuid_factory=lambda: audit_id,
        on_revoke=on_revoke,
    )


async def test_role_change_revokes_two_sessions_and_audits_admin_atomically(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="role-admin")
    operator = _user(Role.OPERATOR, label="role-operator")
    admin_session = _session(admin)
    operator_sessions = (
        _session(operator),
        _session(operator, created_offset=1),
    )
    audit_id = str(uuid4())
    propagated: list[str] = []

    async def on_revoke(session_id: str) -> None:
        propagated.append(session_id)

    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
    )

    result = await _admin_service(
        session_factory,
        audit_id=audit_id,
        on_revoke=on_revoke,
    ).change_role(_principal(admin, admin_session), operator.id, Role.VIEWER)

    expected_session_ids = {value.id for value in operator_sessions}
    assert result.changed is True
    assert set(result.revoked_session_ids) == expected_session_ids
    assert set(propagated) == expected_session_ids
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        audit = await uow.audit_events.get_by_id(audit_id)

    assert stored_user is not None and stored_user.role is Role.VIEWER
    assert {value.id for value in stored_sessions} == expected_session_ids
    assert all(value.revoked_at == NOW for value in stored_sessions)
    assert all(value.revoke_reason == "role_changed" for value in stored_sessions)
    assert audit is not None
    assert audit.action == "user.role_change"
    assert audit.actor_user_id == admin.id
    assert audit.actor_platform_session_id == admin_session.id
    assert audit.actor_role is Role.ADMIN
    assert audit.target_id == operator.id
    assert audit.parameters == {
        "oldRole": "operator",
        "newRole": "viewer",
        "revokedSessionCount": 2,
    }


async def test_audit_conflict_rolls_back_role_and_session_revokes_without_callback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="conflict-admin")
    operator = _user(Role.OPERATOR, label="conflict-operator")
    admin_session = _session(admin)
    operator_sessions = (_session(operator), _session(operator, created_offset=1))
    conflicting_id = str(uuid4())
    actor = _principal(admin, admin_session)
    existing = _audit_event(
        event_id=conflicting_id,
        occurred_at=NOW - timedelta(minutes=1),
        action="user.disable",
        actor=actor,
        target_id=operator.id,
    )
    existing = replace(existing, parameters={"revokedSessionCount": 0})
    propagated: list[str] = []

    async def on_revoke(session_id: str) -> None:
        propagated.append(session_id)

    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
        audit_events=(existing,),
    )

    with pytest.raises(AuditEventConflict):
        await _admin_service(
            session_factory,
            audit_id=conflicting_id,
            on_revoke=on_revoke,
        ).change_role(actor, operator.id, Role.VIEWER)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        stored_audit = await uow.audit_events.get_by_id(conflicting_id)

    assert stored_user is not None and stored_user.role is Role.OPERATOR
    assert all(value.revoked_at is None for value in stored_sessions)
    assert all(value.revoke_reason is None for value in stored_sessions)
    assert stored_audit == existing
    assert propagated == []


async def test_commit_failure_rolls_back_real_writes_without_callback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="commit-admin")
    operator = _user(Role.OPERATOR, label="commit-operator")
    admin_session = _session(admin)
    operator_sessions = (_session(operator), _session(operator, created_offset=1))
    audit_id = str(uuid4())
    propagated: list[str] = []

    class RejectingCommitUnitOfWork(SqlAlchemyPlatformUnitOfWork):
        async def commit(self) -> None:
            raise RuntimeError("forced integration commit failure")

    async def on_revoke(session_id: str) -> None:
        propagated.append(session_id)

    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
    )

    with pytest.raises(RuntimeError, match="forced integration commit failure"):
        await _admin_service(
            session_factory,
            audit_id=audit_id,
            on_revoke=on_revoke,
            uow_factory=lambda: RejectingCommitUnitOfWork(session_factory),
        ).change_role(_principal(admin, admin_session), operator.id, Role.VIEWER)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        stored_audit = await uow.audit_events.get_by_id(audit_id)

    assert stored_user is not None and stored_user.role is Role.OPERATOR
    assert all(value.revoked_at is None for value in stored_sessions)
    assert stored_audit is None
    assert propagated == []


@pytest.mark.parametrize("operation", ["demote", "disable"])
async def test_concurrent_two_admin_mutations_preserve_one_enabled_admin(
    operation: str,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _user(Role.ADMIN, label=f"concurrent-{operation}-first")
    second = _user(Role.ADMIN, label=f"concurrent-{operation}-second")
    first_session = _session(first)
    second_session = _session(second)
    await _seed(
        session_factory,
        users=(first, second),
        sessions=(first_session, second_session),
    )

    original_get_by_id = SqlAlchemyUserRepository.get_by_id
    arrival_lock = asyncio.Lock()
    both_targets_loaded = asyncio.Event()
    arrived = 0

    async def coordinated_get_by_id(
        repository: SqlAlchemyUserRepository,
        user_id: str,
    ) -> User | None:
        nonlocal arrived
        value = await original_get_by_id(repository, user_id)
        async with arrival_lock:
            arrived += 1
            if arrived == 2:
                both_targets_loaded.set()
        await asyncio.wait_for(both_targets_loaded.wait(), timeout=5)
        return value

    monkeypatch.setattr(SqlAlchemyUserRepository, "get_by_id", coordinated_get_by_id)

    async def attempt(actor: Principal, target_id: str, audit_id: str) -> str:
        service = _admin_service(session_factory, audit_id=audit_id)
        try:
            if operation == "demote":
                await service.change_role(actor, target_id, Role.VIEWER)
            else:
                await service.set_disabled(actor, target_id, disabled=True)
        except LastAdminProtected:
            return "protected"
        return "changed"

    outcomes = await asyncio.wait_for(
        asyncio.gather(
            attempt(_principal(first, first_session), second.id, str(uuid4())),
            attempt(_principal(second, second_session), first.id, str(uuid4())),
        ),
        timeout=10,
    )

    assert sorted(outcomes) == ["changed", "protected"]
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_users = await uow.users.list_all(10)
        audits = await uow.audit_events.list_page(
            AuditQuery(scope=AuditQueryScope.ALL, cursor=None, limit=10)
        )

    enabled_admins = [
        value for value in stored_users if value.role is Role.ADMIN and value.disabled_at is None
    ]
    assert len(enabled_admins) == 1
    assert len(audits.events) == 1
    if operation == "demote":
        assert {value.role for value in stored_users} == {Role.ADMIN, Role.VIEWER}
        assert all(value.disabled_at is None for value in stored_users)
        assert audits.events[0].action == "user.role_change"
    else:
        assert all(value.role is Role.ADMIN for value in stored_users)
        assert sum(value.disabled_at is not None for value in stored_users) == 1
        assert audits.events[0].action == "user.disable"


async def test_disable_revokes_sessions_and_records_admin_actor_atomically(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="disable-admin")
    operator = _user(Role.OPERATOR, label="disable-operator")
    admin_session = _session(admin)
    operator_sessions = (_session(operator), _session(operator, created_offset=1))
    audit_id = str(uuid4())
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
    )

    result = await _admin_service(session_factory, audit_id=audit_id).set_disabled(
        _principal(admin, admin_session),
        operator.id,
        disabled=True,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        audit = await uow.audit_events.get_by_id(audit_id)

    assert result.changed is True
    assert set(result.revoked_session_ids) == {value.id for value in operator_sessions}
    assert stored_user is not None and stored_user.disabled_at == NOW
    assert all(value.revoked_at == NOW for value in stored_sessions)
    assert all(value.revoke_reason == "user_disabled" for value in stored_sessions)
    assert audit is not None
    assert audit.action == "user.disable"
    assert audit.actor_user_id == admin.id
    assert audit.actor_platform_session_id == admin_session.id
    assert audit.target_id == operator.id
    assert audit.parameters == {"revokedSessionCount": 2}


async def test_admin_session_revoke_records_actor_target_and_target_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="revoke-admin")
    operator = _user(Role.OPERATOR, label="revoke-operator")
    admin_session = _session(admin)
    target_session = _session(operator)
    audit_id = str(uuid4())
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, target_session),
    )

    result = await _admin_service(session_factory, audit_id=audit_id).revoke_session(
        _principal(admin, admin_session),
        target_session.id,
        reason="security_review",
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_session = await uow.platform_sessions.get_by_id(target_session.id)
        audit = await uow.audit_events.get_by_id(audit_id)

    assert result.revoked_session_ids == (target_session.id,)
    assert stored_session is not None and stored_session.revoked_at == NOW
    assert stored_session.revoke_reason == "security_review"
    assert audit is not None
    assert audit.action == "session.revoke"
    assert audit.actor_user_id == admin.id
    assert audit.actor_platform_session_id == admin_session.id
    assert audit.actor_user_id != operator.id
    assert audit.target_type == "platform_session"
    assert audit.target_id == target_session.id
    assert audit.parameters == {
        "targetUserId": operator.id,
        "reason": "security_review",
    }


async def test_security_audit_is_admin_only_through_service_and_router(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="scope-admin")
    operator = _user(Role.OPERATOR, label="scope-operator")
    viewer = _user(Role.VIEWER, label="scope-viewer")
    admin_session = _session(admin)
    operator_session = _session(operator)
    viewer_session = _session(viewer)
    actor = _principal(admin, admin_session)
    operational = _audit_event(
        event_id=str(uuid4()),
        occurred_at=NOW,
        action="recovery.completed",
        actor=actor,
        target_id=operator.id,
    )
    security = _audit_event(
        event_id=str(uuid4()),
        occurred_at=NOW + timedelta(seconds=1),
        action="user.disable",
        actor=actor,
        target_id=operator.id,
    )
    await _seed(
        session_factory,
        users=(admin, operator, viewer),
        sessions=(admin_session, operator_session, viewer_session),
        audit_events=(operational, security),
    )

    def uow_factory() -> SqlAlchemyPlatformUnitOfWork:
        return SqlAlchemyPlatformUnitOfWork(session_factory)

    audit_service = AuditQueryService(readiness=Ready(), uow_factory=uow_factory)
    admin_service = UserAdminService(
        readiness=Ready(),
        uow_factory=uow_factory,
        clock=lambda: NOW,
        uuid_factory=lambda: str(uuid4()),
    )
    admin_page = await audit_service.list_for_role(Role.ADMIN)
    operator_page = await audit_service.list_for_role(Role.OPERATOR)
    viewer_page = await audit_service.list_for_role(Role.VIEWER)

    assert [event.id for event in admin_page.events] == [security.id, operational.id]
    assert [event.id for event in operator_page.events] == [operational.id]
    assert [event.id for event in viewer_page.events] == [operational.id]
    for principal in (
        _principal(operator, operator_session),
        _principal(viewer, viewer_session),
    ):
        with pytest.raises(AdminForbidden):
            await admin_service.list_users(principal)

    async def router_responses(user: User, platform_session: PlatformSession):
        identity = SessionIdentity(
            principal=_principal(user, platform_session),
            display_name=user.display_name,
            expires_at=platform_session.expires_at,
        )
        app = FastAPI()
        app.include_router(
            create_platform_admin_router(
                sessions=StaticSessionResolver(identity),
                admin=admin_service,
                audit=audit_service,
                settings=RuntimeSettings(platform_ui_origin=ORIGIN),
            )
        )
        transport = httpx.ASGITransport(app=app)
        headers = {"Cookie": f"{COOKIE}=integration-secret"}
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://integration.test",
        ) as client:
            audit_response = await client.get(
                "/api/platform/audit?scope=all",
                headers=headers,
            )
            users_response = await client.get(
                "/api/platform/admin/users",
                headers=headers,
            )
        return audit_response, users_response

    admin_audit, admin_users = await router_responses(admin, admin_session)
    operator_audit, operator_users = await router_responses(operator, operator_session)
    viewer_audit, viewer_users = await router_responses(viewer, viewer_session)

    assert admin_audit.status_code == 200
    assert [event["id"] for event in admin_audit.json()["events"]] == [
        security.id,
        operational.id,
    ]
    assert admin_users.status_code == 200
    for audit_response, users_response in (
        (operator_audit, operator_users),
        (viewer_audit, viewer_users),
    ):
        assert audit_response.status_code == 200
        assert [event["id"] for event in audit_response.json()["events"]] == [operational.id]
        assert users_response.status_code == 403
        assert users_response.json()["error"]["code"] == "admin_forbidden"
