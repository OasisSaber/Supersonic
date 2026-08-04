from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.cockpit.service import CockpitService
from app.contracts.v1 import (
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    EndpointId,
    MessageSource,
)
from app.platform.audit import AuditBuffer, InMemoryAuditSink, JsonlAuditBuffer
from app.platform.errors import AuditUnavailable, RoleForbidden
from app.platform.gateway import AuthorizedCockpitGateway
from app.platform.models import AuditRecord, AuditResult, Principal, Role


def command(name: CommandName, parameters: dict, endpoint: EndpointId) -> CommandEnvelopeV1:
    return CommandEnvelopeV1(
        message_id=uuid4(),
        correlation_id=uuid4(),
        timestamp=datetime.now(UTC),
        source=MessageSource(kind="endpoint", id=endpoint.value),
        payload=CommandPayloadV1(name=name, endpoint=endpoint, parameters=parameters),
    )


def test_jsonl_fallback_persists_sanitized_payload(tmp_path) -> None:
    buffer = JsonlAuditBuffer(tmp_path / "audit-fallback.jsonl")
    record = AuditRecord(
        audit_id="00000000-0000-0000-0000-000000000010",
        occurred_at=datetime.now(UTC),
        actor_user_id="00000000-0000-0000-0000-000000000011",
        actor_role=Role.OPERATOR,
        actor_session_id="00000000-0000-0000-0000-000000000012",
        endpoint="center",
        command_name="resolve_risk",
        correlation_id="00000000-0000-0000-0000-000000000013",
        result=AuditResult.DEGRADED,
        parameters={"eventId": "risk-1"},
    )

    buffer.append(record)

    assert buffer.read_payloads()[0]["result"] == "degraded"


async def test_viewer_is_rejected_before_authoritative_state_changes() -> None:
    authority = CockpitService()
    sink = InMemoryAuditSink()
    gateway = AuthorizedCockpitGateway(authority, sink)
    before = await authority.get_snapshot()

    with pytest.raises(RoleForbidden):
        await gateway.apply_command(
            Principal("viewer-1", Role.VIEWER, "session-viewer"),
            command(CommandName.SET_THEME, {"theme": "day"}, EndpointId.CONTROL),
            server_endpoint=EndpointId.CONTROL,
        )

    assert await authority.get_snapshot() == before
    assert sink.records[0].error_code == "role_forbidden"


async def test_operator_cannot_reset_authoritative_session() -> None:
    authority = CockpitService()
    gateway = AuthorizedCockpitGateway(authority, InMemoryAuditSink())

    with pytest.raises(RoleForbidden):
        await gateway.apply_command(
            Principal("operator-1", Role.OPERATOR, "session-operator"),
            command(CommandName.RESET_SESSION, {}, EndpointId.CONTROL),
            server_endpoint=EndpointId.CONTROL,
        )


async def test_admin_management_command_requires_audit_availability() -> None:
    authority = CockpitService()
    gateway = AuthorizedCockpitGateway(authority, InMemoryAuditSink(available=False))
    before = await authority.get_snapshot()

    with pytest.raises(AuditUnavailable):
        await gateway.apply_command(
            Principal("admin-1", Role.ADMIN, "session-admin"),
            command(CommandName.RESET_SESSION, {}, EndpointId.CONTROL),
            server_endpoint=EndpointId.CONTROL,
        )

    assert await authority.get_snapshot() == before


async def test_admin_management_command_records_intent_and_outcome() -> None:
    authority = CockpitService()
    sink = InMemoryAuditSink()
    gateway = AuthorizedCockpitGateway(authority, sink)

    result = await gateway.apply_command(
        Principal(
            "00000000-0000-0000-0000-000000000001",
            Role.ADMIN,
            "00000000-0000-0000-0000-000000000002",
        ),
        command(CommandName.SET_THEME, {"theme": "day"}, EndpointId.CONTROL),
        server_endpoint=EndpointId.CONTROL,
    )

    assert result.audit_degraded is False
    assert [record.result.value for record in sink.records] == ["attempted", "succeeded"]


async def test_safety_command_uses_bounded_fallback_when_audit_is_down() -> None:
    authority = CockpitService()
    buffer = AuditBuffer(max_records=4)
    sink = InMemoryAuditSink(available=False)
    gateway = AuthorizedCockpitGateway(authority, sink, fallback_buffer=buffer)

    takeover = await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"}, EndpointId.CONTROL),
        server_endpoint=EndpointId.CONTROL,
    )
    risk_id = takeover.payload.risks[0].event_id

    result = await gateway.apply_command(
        Principal("operator-1", Role.OPERATOR, "session-operator"),
        command(CommandName.ACKNOWLEDGE_RISK, {"eventId": risk_id}, EndpointId.CENTER),
        server_endpoint=EndpointId.CENTER,
    )

    assert result.audit_degraded is True
    assert len(buffer.records) == 1
    assert buffer.records[0].result.value == "degraded"
