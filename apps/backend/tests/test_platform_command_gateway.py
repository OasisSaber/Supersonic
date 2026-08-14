from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.cockpit.errors import CommandRejected
from app.cockpit.service import CockpitService
from app.contracts.v1 import (
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    EndpointId,
    MessageSource,
)
from app.platform.audit_identity import AuditEventConflict
from app.platform.command_gateway import PlatformCommandGateway
from app.platform.errors import AuditUnavailable, RoleForbidden
from app.platform.models import AuditDelivery, AuditEvent, AuditResult, Principal, Role


def command(
    name: CommandName,
    *,
    endpoint: EndpointId = EndpointId.CENTER,
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
        user_id="11111111-1111-4111-8111-111111111111",
        role=role,
        session_id="22222222-2222-4222-8222-222222222222",
    )


class RecordingAudit:
    def __init__(self, *, available: bool = True, conflict: bool = False) -> None:
        self.available = available
        self.conflict = conflict
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> bool:
        if self.conflict:
            raise AuditEventConflict(event.id)
        if not self.available:
            raise AuditUnavailable("sink unavailable")
        self.events.append(event)
        return True


class RecordingFallback:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        if self.fails:
            raise OSError("fallback disk unavailable")
        self.events.append(event)


def make_gateway(
    *,
    audit: RecordingAudit | None = None,
    fallback: RecordingFallback | None = None,
) -> tuple[PlatformCommandGateway, RecordingAudit, RecordingFallback | None]:
    audit = audit or RecordingAudit()
    authority = CockpitService()
    gateway = PlatformCommandGateway(
        authority=authority,
        audit=audit,
        fallback=fallback,
        id_factory=lambda: str(uuid4()),
        clock=lambda: datetime(2026, 8, 15, 12, tzinfo=UTC),
    )
    return gateway, audit, fallback


async def test_successful_command_records_succeeded_primary() -> None:
    gateway, audit, _ = make_gateway()
    sent = command(
        CommandName.SET_THEME,
        endpoint=EndpointId.CONTROL,
        parameters={"theme": "day"},
    )

    result = await gateway.apply_command(
        principal(),
        sent,
        server_endpoint=EndpointId.CONTROL,
    )

    assert result.audit_delivery is AuditDelivery.PRIMARY
    assert result.audit_recorded is True
    assert result.audit_degraded is False
    assert len(audit.events) == 2
    attempted, succeeded = audit.events
    assert attempted.result is AuditResult.ATTEMPTED
    assert succeeded.result is AuditResult.SUCCEEDED
    assert succeeded.action == "cockpit.command"
    assert succeeded.actor_user_id == principal().user_id
    assert succeeded.actor_role is Role.ADMIN
    assert succeeded.endpoint == "control"
    assert succeeded.command_name == "set_theme"
    assert succeeded.correlation_id == str(sent.correlation_id)


async def test_role_forbidden_records_rejected_and_reraises() -> None:
    gateway, audit, _ = make_gateway()

    with pytest.raises(RoleForbidden):
        await gateway.apply_command(
            principal(role=Role.VIEWER),
            command(
                CommandName.SET_THEME,
                endpoint=EndpointId.CONTROL,
                parameters={"theme": "day"},
            ),
            server_endpoint=EndpointId.CONTROL,
        )

    assert len(audit.events) == 1
    assert audit.events[0].result is AuditResult.REJECTED
    assert audit.events[0].error_code == "role_forbidden"


async def test_management_command_records_attempted_before_mutation() -> None:
    gateway, audit, _ = make_gateway()

    await gateway.apply_command(
        principal(),
        command(
            CommandName.SET_SYSTEM_MODE,
            endpoint=EndpointId.CONTROL,
            parameters={"mode": "normal"},
        ),
        server_endpoint=EndpointId.CONTROL,
    )

    assert [event.result for event in audit.events] == [
        AuditResult.ATTEMPTED,
        AuditResult.SUCCEEDED,
    ]


async def test_non_management_command_without_attempted() -> None:
    gateway, audit, _ = make_gateway()

    await gateway.apply_command(
        principal(),
        command(
            CommandName.SET_MEDIA_STATE,
            endpoint=EndpointId.PASSENGER,
            parameters={"state": "paused"},
        ),
        server_endpoint=EndpointId.PASSENGER,
    )

    assert [event.result for event in audit.events] == [AuditResult.SUCCEEDED]


async def test_command_rejected_by_cockpit_records_rejected_and_reraises() -> None:
    gateway, audit, _ = make_gateway()

    with pytest.raises(CommandRejected):
        await gateway.apply_command(
            principal(),
            command(
                CommandName.SET_THEME,
                endpoint=EndpointId.HUD,
                parameters={"theme": "day"},
            ),
            server_endpoint=EndpointId.HUD,
        )

    assert audit.events[-1].result is AuditResult.REJECTED
    assert audit.events[-1].error_code == "command_forbidden"


async def test_primary_outage_uses_fallback_for_non_management() -> None:
    fallback = RecordingFallback()
    gateway, _, _ = make_gateway(
        audit=RecordingAudit(available=False),
        fallback=fallback,
    )

    result = await gateway.apply_command(
        principal(),
        command(
            CommandName.SET_MEDIA_STATE,
            endpoint=EndpointId.PASSENGER,
            parameters={"state": "paused"},
        ),
        server_endpoint=EndpointId.PASSENGER,
    )

    assert result.audit_delivery is AuditDelivery.FALLBACK
    assert len(fallback.events) == 1
    assert fallback.events[0].result is AuditResult.SUCCEEDED


async def test_primary_outage_fails_management_command_visibly() -> None:
    gateway, _, _ = make_gateway(audit=RecordingAudit(available=False))

    with pytest.raises(AuditUnavailable):
        await gateway.apply_command(
            principal(),
            command(
                CommandName.SET_THEME,
                endpoint=EndpointId.CONTROL,
                parameters={"theme": "day"},
            ),
            server_endpoint=EndpointId.CONTROL,
        )


async def test_lost_delivery_when_fallback_also_fails() -> None:
    gateway, _, _ = make_gateway(
        audit=RecordingAudit(available=False),
        fallback=RecordingFallback(fails=True),
    )

    result = await gateway.apply_command(
        principal(),
        command(
            CommandName.SET_MEDIA_STATE,
            endpoint=EndpointId.PASSENGER,
            parameters={"state": "paused"},
        ),
        server_endpoint=EndpointId.PASSENGER,
    )

    assert result.audit_delivery is AuditDelivery.LOST
    assert result.audit_recorded is False


async def test_audit_conflict_propagates_never_falls_back() -> None:
    fallback = RecordingFallback()
    gateway, _, _ = make_gateway(
        audit=RecordingAudit(conflict=True),
        fallback=fallback,
    )

    with pytest.raises(AuditEventConflict):
        await gateway.apply_command(
            principal(),
            command(
                CommandName.SET_MEDIA_STATE,
                endpoint=EndpointId.PASSENGER,
                parameters={"state": "paused"},
            ),
            server_endpoint=EndpointId.PASSENGER,
        )

    assert fallback.events == []
