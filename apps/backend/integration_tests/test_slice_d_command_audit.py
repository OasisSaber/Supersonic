from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.postgres.audit_sink import PostgresAuditSink
from app.adapters.postgres.database import create_database_engine, create_session_factory
from app.adapters.postgres.readiness import SqlAlchemyPlatformReadiness
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from app.cockpit.errors import CommandRejected
from app.cockpit.service import CockpitService
from app.contracts.v1 import (
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    EndpointId,
    MessageSource,
)
from app.platform.command_gateway import PlatformCommandGateway
from app.platform.models import (
    AuditDelivery,
    AuditEvent,
    AuditQuery,
    AuditQueryScope,
    AuditResult,
    Principal,
    Role,
    User,
)
from app.platform.websocket_registry import WebSocketSessionRegistry

USER_ID = "11111111-1111-4111-8111-111111111111"
SESSION_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
async def slice_d_session_factory(
    migrated_database_url: str,
):
    engine = create_database_engine(migrated_database_url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def slice_d_engine(
    migrated_database_url: str,
):
    engine = create_database_engine(migrated_database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


def command(
    name: CommandName,
    *,
    endpoint: EndpointId = EndpointId.CONTROL,
    parameters: dict | None = None,
) -> CommandEnvelopeV1:
    return CommandEnvelopeV1(
        message_id=uuid4(),
        correlation_id=uuid4(),
        timestamp=datetime.now(UTC),
        source=MessageSource(kind="endpoint", id=endpoint.value),
        payload=CommandPayloadV1(
            name=name,
            endpoint=endpoint,
            parameters=parameters if parameters is not None else {},
        ),
    )


def principal(*, role: Role = Role.ADMIN) -> Principal:
    return Principal(
        user_id=USER_ID,
        role=role,
        session_id=SESSION_ID,
    )


def make_user(*, role: Role = Role.ADMIN) -> User:
    return User(
        id=USER_ID,
        username_norm="operator",
        display_name="Operator",
        password_hash="hash",
        role=role,
        disabled_at=None,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


async def seed_user(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(make_user())
        await uow.commit()


def make_gateway(
    session_factory: async_sessionmaker[AsyncSession],
    engine,
    *,
    migrated_database_url: str,
) -> PlatformCommandGateway:
    return PlatformCommandGateway(
        authority=CockpitService(),
        audit=PostgresAuditSink(
            readiness=SqlAlchemyPlatformReadiness(migrated_database_url, engine=engine),
            uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
        ),
        id_factory=lambda: str(uuid4()),
        clock=lambda: datetime(2026, 8, 15, 12, tzinfo=UTC),
    )


async def load_all_events(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[AuditEvent]:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        page = await uow.audit_events.list_page(
            AuditQuery(
                scope=AuditQueryScope.ALL,
                cursor=None,
                limit=20,
            )
        )
    return list(page.events)


async def test_command_gateway_persists_attempted_and_succeeded_facts(
    slice_d_session_factory,
    slice_d_engine,
    migrated_database_url: str,
) -> None:
    await seed_user(slice_d_session_factory)
    gateway = make_gateway(
        slice_d_session_factory,
        slice_d_engine,
        migrated_database_url=migrated_database_url,
    )
    result = await gateway.apply_command(
        principal(),
        command(CommandName.SET_THEME, parameters={"theme": "day"}),
        server_endpoint=EndpointId.CONTROL,
    )

    assert result.audit_delivery is AuditDelivery.PRIMARY

    events = await load_all_events(slice_d_session_factory)
    assert {event.result for event in events} == {
        AuditResult.ATTEMPTED,
        AuditResult.SUCCEEDED,
    }
    facts = {event.result: event for event in events}
    succeeded = facts[AuditResult.SUCCEEDED]
    assert succeeded.action == "cockpit.command"
    assert succeeded.actor_user_id == USER_ID
    assert succeeded.endpoint == "control"
    assert succeeded.command_name == "set_theme"


async def test_command_gateway_rejected_command_persists_rejected_fact(
    slice_d_session_factory,
    slice_d_engine,
    migrated_database_url: str,
) -> None:
    await seed_user(slice_d_session_factory)
    gateway = make_gateway(
        slice_d_session_factory,
        slice_d_engine,
        migrated_database_url=migrated_database_url,
    )

    with pytest.raises(CommandRejected):
        await gateway.apply_command(
            principal(),
            command(CommandName.SET_THEME, endpoint=EndpointId.HUD, parameters={"theme": "day"}),
            server_endpoint=EndpointId.HUD,
        )

    events = await load_all_events(slice_d_session_factory)
    # SET_THEME is a management command: a durable attempted fact is written
    # before the cockpit domain policy rejects the HUD endpoint.
    assert {event.result for event in events} == {
        AuditResult.ATTEMPTED,
        AuditResult.REJECTED,
    }
    facts = {event.result: event for event in events}
    assert facts[AuditResult.REJECTED].error_code == "command_forbidden"


async def test_websocket_registry_closes_connections_on_revoke() -> None:
    registry = WebSocketSessionRegistry()

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        async def close(self, code: int = 1000) -> None:
            self.closed = True

    first = FakeConnection()
    second = FakeConnection()
    registry.register("session-1", first)
    registry.register("session-1", second)

    await registry.close_all("session-1")

    assert first.closed is True
    assert second.closed is True
    assert registry.connection_count("session-1") == 0
