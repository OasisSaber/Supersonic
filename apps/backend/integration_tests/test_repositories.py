from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.postgres.database import create_database_engine, create_session_factory
from app.adapters.postgres.orm import AuditEventRow, PlatformSessionRow, UserRow
from app.adapters.postgres.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyPlatformSessionRepository,
    SqlAlchemyUserRepository,
    _audit_event_from_row,
    _platform_session_from_row,
    _user_from_row,
)
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from app.platform.models import (
    AuditDelivery,
    AuditEvent,
    AuditResult,
    PlatformSession,
    Role,
    User,
)


@pytest.fixture
async def session_factory(
    migrated_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_database_engine(migrated_database_url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


@pytest.fixture
def sample_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username_norm=f"driver-{uuid4().hex}",
        display_name="Test Driver",
        password_hash="$argon2id$test-only-hash",
        role=Role.OPERATOR,
        disabled_at=now - timedelta(minutes=5),
        created_at=now - timedelta(days=2),
        updated_at=now,
    )


@pytest.fixture
def sample_platform_session(sample_user: User) -> PlatformSession:
    now = datetime.now(UTC)
    return PlatformSession(
        id=str(uuid4()),
        user_id=sample_user.id,
        token_digest="a" * 64,
        created_at=now,
        expires_at=now + timedelta(hours=4),
        last_seen_at=now + timedelta(minutes=1),
        revoked_at=now + timedelta(minutes=2),
        revoke_reason="operator sign-out",
    )


@pytest.fixture
def sample_audit_event(
    sample_user: User,
    sample_platform_session: PlatformSession,
) -> AuditEvent:
    return AuditEvent(
        id=str(uuid4()),
        occurred_at=datetime.now(UTC),
        action="platform.session.revoke",
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.FALLBACK,
        actor_user_id=sample_user.id,
        actor_platform_session_id=sample_platform_session.id,
        actor_role=Role.ADMIN,
        endpoint="center",
        cockpit_session_id="cockpit-demo-01",
        command_name="revoke_platform_session",
        correlation_id="correlation-demo-01",
        target_type="platform_session",
        target_id="target-demo-01",
        parameters={"reason": "operator sign-out", "attempt": 1},
        error_code="operator_sign_out",
        source_type="local_hmi",
    )


async def _commit_platform_session_prerequisites(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
    sample_platform_session: PlatformSession,
) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(sample_user)
        await uow.commit()

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.platform_sessions.add(sample_platform_session)
        await uow.commit()


async def test_user_add_persists_all_fields(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    async with session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        await repository.add(sample_user)
        await session.flush()
        row = (
            await session.execute(select(UserRow).where(UserRow.id == UUID(sample_user.id)))
        ).scalar_one()

    assert row.id == UUID(sample_user.id)
    assert row.username_norm == sample_user.username_norm
    assert row.display_name == sample_user.display_name
    assert row.password_hash == sample_user.password_hash
    assert row.role == sample_user.role.value
    assert row.disabled_at == sample_user.disabled_at
    assert row.created_at == sample_user.created_at
    assert row.updated_at == sample_user.updated_at


def test_user_row_maps_all_fields_to_domain() -> None:
    disabled_at = datetime(2026, 8, 7, 4, 30, tzinfo=UTC)
    created_at = datetime(2026, 8, 6, 3, 20, tzinfo=UTC)
    updated_at = datetime(2026, 8, 9, 5, 40, tzinfo=UTC)
    row = UserRow(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        username_norm="literal-driver",
        display_name="Literal Driver",
        password_hash="$argon2id$literal-hash",
        role="admin",
        disabled_at=disabled_at,
        created_at=created_at,
        updated_at=updated_at,
    )

    assert _user_from_row(row) == User(
        id="11111111-1111-4111-8111-111111111111",
        username_norm="literal-driver",
        display_name="Literal Driver",
        password_hash="$argon2id$literal-hash",
        role=Role.ADMIN,
        disabled_at=disabled_at,
        created_at=created_at,
        updated_at=updated_at,
    )


async def test_user_get_by_id_returns_committed_user(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(sample_user)
        await uow.commit()

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        assert await verification.users.get_by_id(sample_user.id) == sample_user


async def test_user_lookup_uses_normalized_username(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(sample_user)
        await uow.commit()

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        assert (
            await verification.users.get_by_username_norm(sample_user.username_norm) == sample_user
        )
        assert (
            await verification.users.get_by_username_norm(sample_user.username_norm.upper()) is None
        )


async def test_platform_session_add_persists_all_fields(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
    sample_platform_session: PlatformSession,
) -> None:
    async with session_factory() as session:
        user_repository = SqlAlchemyUserRepository(session)
        repository = SqlAlchemyPlatformSessionRepository(session)
        await user_repository.add(sample_user)
        await session.flush()
        await repository.add(sample_platform_session)
        await session.flush()
        row = (
            await session.execute(
                select(PlatformSessionRow).where(
                    PlatformSessionRow.id == UUID(sample_platform_session.id)
                )
            )
        ).scalar_one()

    assert row.id == UUID(sample_platform_session.id)
    assert row.user_id == UUID(sample_platform_session.user_id)
    assert row.token_digest == sample_platform_session.token_digest
    assert row.created_at == sample_platform_session.created_at
    assert row.expires_at == sample_platform_session.expires_at
    assert row.last_seen_at == sample_platform_session.last_seen_at
    assert row.revoked_at == sample_platform_session.revoked_at
    assert row.revoke_reason == sample_platform_session.revoke_reason


def test_platform_session_row_maps_all_fields_to_domain() -> None:
    created_at = datetime(2026, 8, 9, 1, 10, tzinfo=UTC)
    expires_at = datetime(2026, 8, 9, 5, 20, tzinfo=UTC)
    last_seen_at = datetime(2026, 8, 9, 2, 30, tzinfo=UTC)
    revoked_at = datetime(2026, 8, 9, 3, 40, tzinfo=UTC)
    row = PlatformSessionRow(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        user_id=UUID("33333333-3333-4333-8333-333333333333"),
        token_digest="b" * 64,
        created_at=created_at,
        expires_at=expires_at,
        last_seen_at=last_seen_at,
        revoked_at=revoked_at,
        revoke_reason="literal revocation",
    )

    assert _platform_session_from_row(row) == PlatformSession(
        id="22222222-2222-4222-8222-222222222222",
        user_id="33333333-3333-4333-8333-333333333333",
        token_digest="b" * 64,
        created_at=created_at,
        expires_at=expires_at,
        last_seen_at=last_seen_at,
        revoked_at=revoked_at,
        revoke_reason="literal revocation",
    )


async def test_platform_session_lookup_accepts_digest_only(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
    sample_platform_session: PlatformSession,
) -> None:
    await _commit_platform_session_prerequisites(
        session_factory,
        sample_user,
        sample_platform_session,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        stored_session = await verification.platform_sessions.get_by_token_digest(
            sample_platform_session.token_digest
        )
        assert stored_session is not None
        assert stored_session.id == sample_platform_session.id


async def test_uow_requires_explicit_commit(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(sample_user)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        assert await verification.users.get_by_id(sample_user.id) is None


async def test_uow_keeps_committed_write_and_rolls_back_write_started_after_commit(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    second_user = User(
        id=str(uuid4()),
        username_norm=f"driver-{uuid4().hex}",
        display_name="Second Test Driver",
        password_hash="$argon2id$test-only-hash",
        role=Role.OPERATOR,
        disabled_at=sample_user.disabled_at,
        created_at=sample_user.created_at,
        updated_at=sample_user.updated_at,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(sample_user)
        await uow.commit()
        await uow.users.add(second_user)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        assert await verification.users.get_by_id(sample_user.id) == sample_user
        assert await verification.users.get_by_id(second_user.id) is None


async def test_uow_explicit_rollback_leaves_no_committed_write(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(sample_user)
        await uow.rollback()

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        assert await verification.users.get_by_id(sample_user.id) is None


async def test_uow_rolls_back_on_exception(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    with pytest.raises(RuntimeError, match="abort transaction"):
        async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
            await uow.users.add(sample_user)
            raise RuntimeError("abort transaction")

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        assert await verification.users.get_by_id(sample_user.id) is None


async def test_concurrent_uows_own_distinct_sessions_without_public_session() -> None:
    factory = async_sessionmaker(expire_on_commit=False)
    first = SqlAlchemyPlatformUnitOfWork(factory)
    second = SqlAlchemyPlatformUnitOfWork(factory)

    async with first, second:
        assert first._session is not second._session
        assert not hasattr(first, "session")
        assert not hasattr(second, "session")


async def test_audit_append_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
    sample_platform_session: PlatformSession,
    sample_audit_event: AuditEvent,
) -> None:
    await _commit_platform_session_prerequisites(
        session_factory,
        sample_user,
        sample_platform_session,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        assert await uow.audit_events.append(sample_audit_event) is True
        await uow.commit()

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        assert await uow.audit_events.append(sample_audit_event) is False
        await uow.commit()


async def test_audit_append_persists_all_fields(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
    sample_platform_session: PlatformSession,
    sample_audit_event: AuditEvent,
) -> None:
    await _commit_platform_session_prerequisites(
        session_factory,
        sample_user,
        sample_platform_session,
    )

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        assert await uow.audit_events.append(sample_audit_event) is True
        await uow.commit()

    async with session_factory() as session:
        row = (
            await session.execute(
                select(AuditEventRow).where(AuditEventRow.id == UUID(sample_audit_event.id))
            )
        ).scalar_one()

    assert row.id == UUID(sample_audit_event.id)
    assert row.occurred_at == sample_audit_event.occurred_at
    assert row.action == sample_audit_event.action
    assert row.result == sample_audit_event.result.value
    assert row.delivery == sample_audit_event.delivery.value
    assert row.actor_user_id == UUID(sample_audit_event.actor_user_id)
    assert row.actor_platform_session_id == UUID(sample_audit_event.actor_platform_session_id)
    assert row.actor_role == sample_audit_event.actor_role.value
    assert row.endpoint == sample_audit_event.endpoint
    assert row.cockpit_session_id == sample_audit_event.cockpit_session_id
    assert row.command_name == sample_audit_event.command_name
    assert row.correlation_id == sample_audit_event.correlation_id
    assert row.target_type == sample_audit_event.target_type
    assert row.target_id == sample_audit_event.target_id
    assert row.parameters == sample_audit_event.parameters
    assert row.error_code == "operator_sign_out"
    assert row.source_type == sample_audit_event.source_type


def test_audit_row_maps_all_fields_to_domain() -> None:
    occurred_at = datetime(2026, 8, 9, 4, 30, tzinfo=UTC)
    actor_user_id = UUID("11111111-1111-4111-8111-111111111111")
    actor_platform_session_id = UUID("22222222-2222-4222-8222-222222222222")
    row = AuditEventRow(
        id=UUID("33333333-3333-4333-8333-333333333333"),
        occurred_at=occurred_at,
        action="platform.command.execute",
        result="rejected",
        delivery="primary",
        actor_user_id=actor_user_id,
        actor_platform_session_id=actor_platform_session_id,
        actor_role="viewer",
        endpoint="passenger",
        cockpit_session_id="cockpit-literal-01",
        command_name="set_climate",
        correlation_id="correlation-literal-01",
        target_type="climate_zone",
        target_id="passenger-front",
        parameters={"temperature_c": 22},
        error_code="role_denied",
        source_type="local_hmi",
    )

    assert _audit_event_from_row(row) == AuditEvent(
        id="33333333-3333-4333-8333-333333333333",
        occurred_at=occurred_at,
        action="platform.command.execute",
        result=AuditResult.REJECTED,
        delivery=AuditDelivery.PRIMARY,
        actor_user_id="11111111-1111-4111-8111-111111111111",
        actor_platform_session_id="22222222-2222-4222-8222-222222222222",
        actor_role=Role.VIEWER,
        endpoint="passenger",
        cockpit_session_id="cockpit-literal-01",
        command_name="set_climate",
        correlation_id="correlation-literal-01",
        target_type="climate_zone",
        target_id="passenger-front",
        parameters={"temperature_c": 22},
        error_code="role_denied",
        source_type="local_hmi",
    )


async def test_lost_audit_delivery_is_rejected_before_sql() -> None:
    event = AuditEvent(
        id=str(uuid4()),
        occurred_at=datetime.now(UTC),
        action="audit.delivery",
        result=AuditResult.ERROR,
        delivery=AuditDelivery.LOST,
    )
    session = AsyncSession()
    try:
        repository = SqlAlchemyAuditEventRepository(session)
        with pytest.raises(ValueError, match="LOST"):
            await repository.append(event)
    finally:
        await session.close()


async def test_invalid_user_uuid_is_rejected_before_sql(sample_user: User) -> None:
    invalid_user = User(
        id="not-a-uuid",
        username_norm=sample_user.username_norm,
        display_name=sample_user.display_name,
        password_hash=sample_user.password_hash,
        role=sample_user.role,
        disabled_at=sample_user.disabled_at,
        created_at=sample_user.created_at,
        updated_at=sample_user.updated_at,
    )
    session = AsyncSession()
    try:
        repository = SqlAlchemyUserRepository(session)
        with pytest.raises(ValueError, match="user.id must be a valid UUID"):
            await repository.add(invalid_user)
    finally:
        await session.close()
