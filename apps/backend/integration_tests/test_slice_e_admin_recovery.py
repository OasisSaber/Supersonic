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
from app.adapters.postgres.repositories import (
    SqlAlchemyPlatformSessionRepository,
    SqlAlchemyUserRepository,
)
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from app.api.platform_admin_router import create_platform_admin_router
from app.config import RuntimeSettings
from app.platform.admin import (
    AdminForbidden,
    AdminMutationFailed,
    LastAdminProtected,
    UserAdminService,
)
from app.platform.audit_identity import AuditEventConflict
from app.platform.audit_query import AuditQueryService
from app.platform.errors import AuditUnavailable
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
from app.platform.persistence import DatabaseUnavailable, PlatformReadiness
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
    audit_id: str | None = None,
    audit_ids: tuple[str, ...] | None = None,
    on_revoke: Callable[[str], Awaitable[None]] | None = None,
    uow_factory: Callable[[], SqlAlchemyPlatformUnitOfWork] | None = None,
) -> UserAdminService:
    if audit_ids is None:
        if audit_id is None:
            raise ValueError("audit_id or audit_ids is required")
        audit_ids = (str(uuid4()), audit_id, str(uuid4()))
    elif audit_id is not None:
        raise ValueError("audit_id and audit_ids are mutually exclusive")
    remaining_audit_ids = iter(audit_ids)
    return UserAdminService(
        readiness=Ready(),
        uow_factory=uow_factory or (lambda: SqlAlchemyPlatformUnitOfWork(session_factory)),
        clock=lambda: NOW,
        uuid_factory=lambda: next(remaining_audit_ids),
        on_revoke=on_revoke,
    )


async def test_role_change_commits_before_degraded_revoke_propagation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="role-admin")
    operator = _user(Role.OPERATOR, label="role-operator")
    admin_session = _session(admin)
    operator_sessions = (
        _session(operator),
        _session(operator, created_offset=1),
    )
    attempted_id = str(uuid4())
    audit_id = str(uuid4())
    failure_id = str(uuid4())
    propagated: list[str] = []
    committed_observations: list[tuple[Role | None, AuditResult | None]] = []

    async def on_revoke(session_id: str) -> None:
        propagated.append(session_id)
        async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
            committed_user = await uow.users.get_by_id(operator.id)
            committed_outcome = await uow.audit_events.get_by_id(audit_id)
        committed_observations.append(
            (
                committed_user.role if committed_user is not None else None,
                committed_outcome.result if committed_outcome is not None else None,
            )
        )
        if session_id == operator_sessions[1].id:
            raise RuntimeError("forced registry propagation failure")

    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
    )

    result = await _admin_service(
        session_factory,
        audit_ids=(attempted_id, audit_id, failure_id),
        on_revoke=on_revoke,
    ).change_role(_principal(admin, admin_session), operator.id, Role.VIEWER)

    expected_session_ids = {value.id for value in operator_sessions}
    assert result.changed is True
    assert set(result.revoked_session_ids) == expected_session_ids
    assert result.revoke_propagation_failed_ids == (operator_sessions[1].id,)
    assert set(propagated) == expected_session_ids
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        attempted = await uow.audit_events.get_by_id(attempted_id)
        audit = await uow.audit_events.get_by_id(audit_id)

    assert stored_user is not None and stored_user.role is Role.VIEWER
    assert {value.id for value in stored_sessions} == expected_session_ids
    assert all(value.revoked_at == NOW for value in stored_sessions)
    assert all(value.revoke_reason == "role_changed" for value in stored_sessions)
    assert attempted is not None
    assert attempted.result is AuditResult.ATTEMPTED
    assert attempted.id == attempted.correlation_id
    assert attempted.actor_user_id == admin.id
    assert attempted.actor_platform_session_id == admin_session.id
    assert attempted.actor_role is Role.ADMIN
    assert attempted.target_type == "user"
    assert attempted.target_id == operator.id
    assert committed_observations == [
        (Role.VIEWER, AuditResult.SUCCEEDED),
        (Role.VIEWER, AuditResult.SUCCEEDED),
    ]
    assert audit is not None
    assert audit.action == "user.role_change"
    assert audit.actor_user_id == admin.id
    assert audit.actor_platform_session_id == admin_session.id
    assert audit.actor_role is Role.ADMIN
    assert audit.target_id == operator.id
    assert audit.correlation_id == attempted_id
    assert audit.parameters == {
        "oldRole": "operator",
        "newRole": "viewer",
        "revokedSessionCount": 2,
    }


async def test_outcome_audit_conflict_rolls_back_role_and_session_revokes_without_callback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="conflict-admin")
    operator = _user(Role.OPERATOR, label="conflict-operator")
    admin_session = _session(admin)
    operator_sessions = (_session(operator), _session(operator, created_offset=1))
    attempted_id = str(uuid4())
    conflicting_id = str(uuid4())
    failure_id = str(uuid4())
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
            audit_ids=(attempted_id, conflicting_id, failure_id),
            on_revoke=on_revoke,
        ).change_role(actor, operator.id, Role.VIEWER)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        attempted = await uow.audit_events.get_by_id(attempted_id)
        stored_audit = await uow.audit_events.get_by_id(conflicting_id)
        failure = await uow.audit_events.get_by_id(failure_id)

    assert stored_user is not None and stored_user.role is Role.OPERATOR
    assert all(value.revoked_at is None for value in stored_sessions)
    assert all(value.revoke_reason is None for value in stored_sessions)
    assert attempted is not None and attempted.result is AuditResult.ATTEMPTED
    assert stored_audit == existing
    assert failure is not None and failure.result is AuditResult.ERROR
    assert failure.error_code == "audit_conflict"
    assert failure.correlation_id == attempted_id
    assert propagated == []


async def test_attempted_audit_conflict_stops_before_real_mutation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="attempt-conflict-admin")
    operator = _user(Role.OPERATOR, label="attempt-conflict-operator")
    admin_session = _session(admin)
    operator_session = _session(operator)
    attempted_id = str(uuid4())
    actor = _principal(admin, admin_session)
    existing = _audit_event(
        event_id=attempted_id,
        occurred_at=NOW - timedelta(minutes=1),
        action="user.disable",
        actor=actor,
        target_id=operator.id,
    )
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, operator_session),
        audit_events=(existing,),
    )

    with pytest.raises(AuditEventConflict):
        await _admin_service(
            session_factory,
            audit_ids=(attempted_id, str(uuid4()), str(uuid4())),
        ).change_role(actor, operator.id, Role.VIEWER)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_session = await uow.platform_sessions.get_by_id(operator_session.id)
        audits = await uow.audit_events.list_page(
            AuditQuery(scope=AuditQueryScope.ALL, cursor=None, limit=10)
        )

    assert stored_user is not None and stored_user.role is Role.OPERATOR
    assert stored_session is not None and stored_session.revoked_at is None
    assert len(audits.events) == 1
    assert audits.events[0].id == existing.id
    assert audits.events[0].action == existing.action
    assert audits.events[0].result is AuditResult.SUCCEEDED


async def test_attempted_commit_failure_stops_before_real_mutation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="commit-admin")
    operator = _user(Role.OPERATOR, label="commit-operator")
    admin_session = _session(admin)
    operator_sessions = (_session(operator), _session(operator, created_offset=1))
    attempted_id = str(uuid4())
    outcome_id = str(uuid4())
    failure_id = str(uuid4())
    propagated: list[str] = []

    class RejectingCommitUnitOfWork(SqlAlchemyPlatformUnitOfWork):
        async def commit(self) -> None:
            raise DatabaseUnavailable()

    async def on_revoke(session_id: str) -> None:
        propagated.append(session_id)

    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
    )

    uow_factories = iter(
        (
            lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
            lambda: RejectingCommitUnitOfWork(session_factory),
        )
    )
    with pytest.raises(AuditUnavailable):
        await _admin_service(
            session_factory,
            audit_ids=(attempted_id, outcome_id, failure_id),
            on_revoke=on_revoke,
            uow_factory=lambda: next(uow_factories)(),
        ).change_role(_principal(admin, admin_session), operator.id, Role.VIEWER)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        attempted = await uow.audit_events.get_by_id(attempted_id)

    assert stored_user is not None and stored_user.role is Role.OPERATOR
    assert all(value.revoked_at is None for value in stored_sessions)
    assert attempted is None
    assert propagated == []


async def test_mutation_commit_failure_keeps_attempted_and_rolls_back_real_writes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="mutation-failure-admin")
    operator = _user(Role.OPERATOR, label="mutation-failure-operator")
    admin_session = _session(admin)
    operator_sessions = (_session(operator), _session(operator, created_offset=1))
    attempted_id = str(uuid4())
    rolled_back_outcome_id = str(uuid4())
    failure_id = str(uuid4())
    propagated: list[str] = []

    class RejectingMutationCommitUnitOfWork(SqlAlchemyPlatformUnitOfWork):
        async def commit(self) -> None:
            raise DatabaseUnavailable()

    async def on_revoke(session_id: str) -> None:
        propagated.append(session_id)

    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
    )
    uow_factories = iter(
        (
            lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
            lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
            lambda: RejectingMutationCommitUnitOfWork(session_factory),
            lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
        )
    )

    with pytest.raises(DatabaseUnavailable):
        await _admin_service(
            session_factory,
            audit_ids=(attempted_id, rolled_back_outcome_id, failure_id),
            on_revoke=on_revoke,
            uow_factory=lambda: next(uow_factories)(),
        ).change_role(_principal(admin, admin_session), operator.id, Role.VIEWER)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        attempted = await uow.audit_events.get_by_id(attempted_id)
        rolled_back_outcome = await uow.audit_events.get_by_id(rolled_back_outcome_id)
        failure = await uow.audit_events.get_by_id(failure_id)

    assert stored_user is not None and stored_user.role is Role.OPERATOR
    assert all(value.revoked_at is None for value in stored_sessions)
    assert all(value.revoke_reason is None for value in stored_sessions)
    assert attempted is not None and attempted.result is AuditResult.ATTEMPTED
    assert rolled_back_outcome is None
    assert failure is not None and failure.result is AuditResult.ERROR
    assert failure.error_code == "database_unavailable"
    assert failure.correlation_id == attempted_id
    assert propagated == []


async def test_committed_real_mutation_survives_uow_cleanup_failure_and_propagates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="cleanup-failure-admin")
    operator = _user(Role.OPERATOR, label="cleanup-failure-operator")
    admin_session = _session(admin)
    operator_session = _session(operator)
    attempted_id = str(uuid4())
    outcome_id = str(uuid4())
    propagated: list[str] = []

    class FailingCleanupUnitOfWork(SqlAlchemyPlatformUnitOfWork):
        async def __aexit__(self, *args: object) -> None:
            await super().__aexit__(*args)  # type: ignore[arg-type]
            raise DatabaseUnavailable()

    async def on_revoke(session_id: str) -> None:
        propagated.append(session_id)

    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, operator_session),
    )
    uow_factories = iter(
        (
            lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
            lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
            lambda: FailingCleanupUnitOfWork(session_factory),
        )
    )

    result = await _admin_service(
        session_factory,
        audit_ids=(attempted_id, outcome_id, str(uuid4())),
        on_revoke=on_revoke,
        uow_factory=lambda: next(uow_factories)(),
    ).change_role(_principal(admin, admin_session), operator.id, Role.VIEWER)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_session = await uow.platform_sessions.get_by_id(operator_session.id)
        attempted = await uow.audit_events.get_by_id(attempted_id)
        outcome = await uow.audit_events.get_by_id(outcome_id)

    assert result.changed is True
    assert stored_user is not None and stored_user.role is Role.VIEWER
    assert stored_session is not None and stored_session.revoked_at == NOW
    assert attempted is not None and attempted.result is AuditResult.ATTEMPTED
    assert outcome is not None and outcome.result is AuditResult.SUCCEEDED
    assert propagated == [operator_session.id]


@pytest.mark.parametrize("operation", ["role", "disable", "enable", "revoke"])
async def test_concurrent_same_admin_mutation_has_one_change_and_one_successful_noop(
    operation: str,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user(Role.ADMIN, label=f"same-{operation}-admin")
    operator = _user(Role.OPERATOR, label=f"same-{operation}-operator")
    if operation == "enable":
        operator = replace(operator, disabled_at=NOW - timedelta(hours=1))
    admin_session = _session(admin)
    operator_session = _session(operator)
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, operator_session),
    )

    arrival_lock = asyncio.Lock()
    both_preflights_loaded = asyncio.Event()
    arrived = 0
    if operation == "revoke":
        repository_type = SqlAlchemyPlatformSessionRepository
        original_get_by_id = SqlAlchemyPlatformSessionRepository.get_by_id
        target_id = operator_session.id
    else:
        repository_type = SqlAlchemyUserRepository
        original_get_by_id = SqlAlchemyUserRepository.get_by_id
        target_id = operator.id

    async def coordinated_get_by_id(repository: object, value_id: str):
        nonlocal arrived
        value = await original_get_by_id(repository, value_id)  # type: ignore[arg-type]
        if value_id != target_id:
            return value
        async with arrival_lock:
            arrived += 1
            if arrived == 2:
                both_preflights_loaded.set()
        await asyncio.wait_for(both_preflights_loaded.wait(), timeout=5)
        return value

    monkeypatch.setattr(repository_type, "get_by_id", coordinated_get_by_id)

    async def attempt() -> bool:
        service = _admin_service(
            session_factory,
            audit_ids=(str(uuid4()), str(uuid4()), str(uuid4())),
        )
        actor = _principal(admin, admin_session)
        if operation == "role":
            result = await service.change_role(actor, operator.id, Role.VIEWER)
        elif operation == "disable":
            result = await service.set_disabled(actor, operator.id, disabled=True)
        elif operation == "enable":
            result = await service.set_disabled(actor, operator.id, disabled=False)
        else:
            result = await service.revoke_session(actor, operator_session.id)
        return result.changed

    changed_results = await asyncio.wait_for(
        asyncio.gather(attempt(), attempt()),
        timeout=10,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_session = await uow.platform_sessions.get_by_id(operator_session.id)
        audits = await uow.audit_events.list_page(
            AuditQuery(scope=AuditQueryScope.ALL, cursor=None, limit=10)
        )

    assert sorted(changed_results) == [False, True]
    assert len(audits.events) == 4
    assert sum(event.result is AuditResult.ATTEMPTED for event in audits.events) == 2
    assert sum(event.result is AuditResult.SUCCEEDED for event in audits.events) == 2
    if operation == "role":
        assert stored_user is not None and stored_user.role is Role.VIEWER
    elif operation == "disable":
        assert stored_user is not None and stored_user.disabled_at == NOW
    elif operation == "enable":
        assert stored_user is not None and stored_user.disabled_at is None
        assert stored_session is not None and stored_session.revoked_at is None
    else:
        assert stored_session is not None and stored_session.revoked_at == NOW


async def test_concurrent_divergent_role_changes_reject_stale_compare_and_set(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user(Role.ADMIN, label="divergent-admin")
    operator = _user(Role.OPERATOR, label="divergent-operator")
    admin_session = _session(admin)
    operator_session = _session(operator)
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, operator_session),
    )

    original_get_by_id = SqlAlchemyUserRepository.get_by_id
    arrival_lock = asyncio.Lock()
    both_preflights_loaded = asyncio.Event()
    arrived = 0

    async def coordinated_get_by_id(
        repository: SqlAlchemyUserRepository,
        user_id: str,
    ) -> User | None:
        nonlocal arrived
        value = await original_get_by_id(repository, user_id)
        if user_id != operator.id:
            return value
        async with arrival_lock:
            arrived += 1
            if arrived == 2:
                both_preflights_loaded.set()
        await asyncio.wait_for(both_preflights_loaded.wait(), timeout=5)
        return value

    monkeypatch.setattr(SqlAlchemyUserRepository, "get_by_id", coordinated_get_by_id)

    async def attempt(new_role: Role) -> str:
        service = _admin_service(
            session_factory,
            audit_ids=(str(uuid4()), str(uuid4()), str(uuid4())),
        )
        try:
            await service.change_role(
                _principal(admin, admin_session),
                operator.id,
                new_role,
            )
        except AdminMutationFailed:
            return "rejected"
        return "changed"

    outcomes = await asyncio.wait_for(
        asyncio.gather(attempt(Role.VIEWER), attempt(Role.ADMIN)),
        timeout=10,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_session = await uow.platform_sessions.get_by_id(operator_session.id)
        audits = await uow.audit_events.list_page(
            AuditQuery(scope=AuditQueryScope.ALL, cursor=None, limit=10)
        )

    assert sorted(outcomes) == ["changed", "rejected"]
    assert stored_user is not None and stored_user.role in {Role.ADMIN, Role.VIEWER}
    assert stored_session is not None and stored_session.revoked_at == NOW
    assert len(audits.events) == 4
    assert sum(event.result is AuditResult.ATTEMPTED for event in audits.events) == 2
    assert sum(event.result is AuditResult.SUCCEEDED for event in audits.events) == 1
    errors = [event for event in audits.events if event.result is AuditResult.ERROR]
    assert len(errors) == 1
    assert errors[0].error_code == "admin_mutation_failed"


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
    assert len(audits.events) == 4
    assert sum(event.result is AuditResult.ATTEMPTED for event in audits.events) == 2
    assert sum(event.result is AuditResult.SUCCEEDED for event in audits.events) == 1
    assert sum(event.result is AuditResult.REJECTED for event in audits.events) == 1
    rejected_error_codes = {
        event.error_code for event in audits.events if event.result is AuditResult.REJECTED
    }
    assert rejected_error_codes == {"last_admin_protected"}
    if operation == "demote":
        assert {value.role for value in stored_users} == {Role.ADMIN, Role.VIEWER}
        assert all(value.disabled_at is None for value in stored_users)
        assert {event.action for event in audits.events} == {"user.role_change"}
    else:
        assert all(value.role is Role.ADMIN for value in stored_users)
        assert sum(value.disabled_at is not None for value in stored_users) == 1
        assert {event.action for event in audits.events} == {"user.disable"}


async def test_disable_revokes_sessions_and_records_admin_actor_atomically(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="disable-admin")
    operator = _user(Role.OPERATOR, label="disable-operator")
    admin_session = _session(admin)
    operator_sessions = (_session(operator), _session(operator, created_offset=1))
    attempted_id = str(uuid4())
    audit_id = str(uuid4())
    failure_id = str(uuid4())
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, *operator_sessions),
    )

    result = await _admin_service(
        session_factory,
        audit_ids=(attempted_id, audit_id, failure_id),
    ).set_disabled(
        _principal(admin, admin_session),
        operator.id,
        disabled=True,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_sessions = await uow.platform_sessions.list_for_user(operator.id, 10)
        attempted = await uow.audit_events.get_by_id(attempted_id)
        audit = await uow.audit_events.get_by_id(audit_id)

    assert result.changed is True
    assert set(result.revoked_session_ids) == {value.id for value in operator_sessions}
    assert stored_user is not None and stored_user.disabled_at == NOW
    assert all(value.revoked_at == NOW for value in stored_sessions)
    assert all(value.revoke_reason == "user_disabled" for value in stored_sessions)
    assert attempted is not None and attempted.result is AuditResult.ATTEMPTED
    assert attempted.actor_user_id == admin.id
    assert attempted.actor_platform_session_id == admin_session.id
    assert attempted.actor_role is Role.ADMIN
    assert attempted.target_type == "user"
    assert attempted.target_id == operator.id
    assert audit is not None
    assert audit.action == "user.disable"
    assert audit.actor_user_id == admin.id
    assert audit.actor_platform_session_id == admin_session.id
    assert audit.actor_role is Role.ADMIN
    assert audit.target_type == "user"
    assert audit.target_id == operator.id
    assert audit.correlation_id == attempted_id
    assert audit.parameters == {"revokedSessionCount": 2}


async def test_enable_records_attempted_and_succeeded_without_revoking_sessions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="enable-admin")
    operator = replace(
        _user(Role.OPERATOR, label="enable-operator"),
        disabled_at=NOW - timedelta(hours=1),
    )
    admin_session = _session(admin)
    operator_session = _session(operator)
    attempted_id = str(uuid4())
    outcome_id = str(uuid4())
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, operator_session),
    )

    result = await _admin_service(
        session_factory,
        audit_ids=(attempted_id, outcome_id, str(uuid4())),
    ).set_disabled(
        _principal(admin, admin_session),
        operator.id,
        disabled=False,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_user = await uow.users.get_by_id(operator.id)
        stored_session = await uow.platform_sessions.get_by_id(operator_session.id)
        attempted = await uow.audit_events.get_by_id(attempted_id)
        outcome = await uow.audit_events.get_by_id(outcome_id)

    assert result.changed is True
    assert result.revoked_session_ids == ()
    assert stored_user is not None and stored_user.disabled_at is None
    assert stored_session is not None and stored_session.revoked_at is None
    assert attempted is not None and attempted.action == "user.enable"
    assert attempted.result is AuditResult.ATTEMPTED
    assert attempted.actor_user_id == admin.id
    assert attempted.actor_platform_session_id == admin_session.id
    assert attempted.actor_role is Role.ADMIN
    assert attempted.target_type == "user"
    assert attempted.target_id == operator.id
    assert outcome is not None and outcome.result is AuditResult.SUCCEEDED
    assert outcome.correlation_id == attempted_id
    assert outcome.actor_user_id == admin.id
    assert outcome.actor_platform_session_id == admin_session.id
    assert outcome.actor_role is Role.ADMIN
    assert outcome.target_type == "user"
    assert outcome.target_id == operator.id


async def test_admin_session_revoke_records_actor_target_and_target_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = _user(Role.ADMIN, label="revoke-admin")
    operator = _user(Role.OPERATOR, label="revoke-operator")
    admin_session = _session(admin)
    target_session = _session(operator)
    attempted_id = str(uuid4())
    audit_id = str(uuid4())
    failure_id = str(uuid4())
    await _seed(
        session_factory,
        users=(admin, operator),
        sessions=(admin_session, target_session),
    )

    result = await _admin_service(
        session_factory,
        audit_ids=(attempted_id, audit_id, failure_id),
    ).revoke_session(
        _principal(admin, admin_session),
        target_session.id,
        reason="security_review",
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        stored_session = await uow.platform_sessions.get_by_id(target_session.id)
        attempted = await uow.audit_events.get_by_id(attempted_id)
        audit = await uow.audit_events.get_by_id(audit_id)

    assert result.revoked_session_ids == (target_session.id,)
    assert stored_session is not None and stored_session.revoked_at == NOW
    assert stored_session.revoke_reason == "security_review"
    assert attempted is not None and attempted.result is AuditResult.ATTEMPTED
    assert attempted.actor_user_id == admin.id
    assert attempted.actor_platform_session_id == admin_session.id
    assert attempted.actor_role is Role.ADMIN
    assert attempted.target_type == "platform_session"
    assert attempted.target_id == target_session.id
    assert audit is not None
    assert audit.action == "session.revoke"
    assert audit.actor_user_id == admin.id
    assert audit.actor_platform_session_id == admin_session.id
    assert audit.actor_role is Role.ADMIN
    assert audit.actor_user_id != operator.id
    assert audit.target_type == "platform_session"
    assert audit.target_id == target_session.id
    assert audit.correlation_id == attempted_id
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
