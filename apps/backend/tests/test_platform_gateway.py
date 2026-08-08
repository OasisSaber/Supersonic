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
from app.platform.models import (
    AuditDelivery,
    AuditRecord,
    AuditResult,
    Principal,
    Role,
)


def command(name: CommandName, parameters: dict, endpoint: EndpointId) -> CommandEnvelopeV1:
    return CommandEnvelopeV1(
        message_id=uuid4(),
        correlation_id=uuid4(),
        timestamp=datetime.now(UTC),
        source=MessageSource(kind="endpoint", id=endpoint.value),
        payload=CommandPayloadV1(name=name, endpoint=endpoint, parameters=parameters),
    )


class ExplodingAuditSink:
    async def is_available(self) -> bool:
        return True

    async def append(self, _: AuditRecord) -> None:
        raise RuntimeError("database driver failed")


class FailingFallback:
    def append(self, _: AuditRecord) -> None:
        raise OSError("fallback disk unavailable")


def test_jsonl_fallback_preserves_result_and_redacts_payload(tmp_path) -> None:
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
        result=AuditResult.SUCCEEDED,
        delivery=AuditDelivery.FALLBACK,
        parameters={
            "eventId": "risk-1",
            "api_key": "do-not-write",
            "destinationName": "私人住址",
            "suggestion": "包含个人行程的完整建议",
            "private_path": "C:/Users/person/Pictures/private.png",
        },
    )

    buffer.append(record)
    payload = buffer.read_payloads()[0]

    assert payload["result"] == "succeeded"
    assert payload["delivery"] == "fallback"
    assert payload["parameters"] == {
        "eventId": "risk-1",
        "api_key": "[redacted]",
        "destinationName": "[redacted]",
        "suggestion": "[redacted]",
        "private_path": "[redacted]",
    }


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
    assert sink.records[0].result is AuditResult.REJECTED
    assert sink.records[0].error_code == "role_forbidden"


async def test_viewer_rejection_fallback_keeps_rejected_outcome() -> None:
    authority = CockpitService()
    buffer = AuditBuffer()
    gateway = AuthorizedCockpitGateway(
        authority,
        InMemoryAuditSink(available=False),
        fallback_buffer=buffer,
    )

    with pytest.raises(RoleForbidden):
        await gateway.apply_command(
            Principal("viewer-1", Role.VIEWER, "session-viewer"),
            command(CommandName.SET_THEME, {"theme": "day"}, EndpointId.CONTROL),
            server_endpoint=EndpointId.CONTROL,
        )

    assert buffer.records[0].result is AuditResult.REJECTED
    assert buffer.records[0].delivery is AuditDelivery.FALLBACK


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


async def test_management_append_error_is_rejected_before_mutation() -> None:
    authority = CockpitService()
    gateway = AuthorizedCockpitGateway(authority, ExplodingAuditSink())
    before = await authority.get_snapshot()

    with pytest.raises(AuditUnavailable):
        await gateway.apply_command(
            Principal("admin-1", Role.ADMIN, "session-admin"),
            command(CommandName.SET_THEME, {"theme": "day"}, EndpointId.CONTROL),
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

    assert result.audit_delivery is AuditDelivery.PRIMARY
    assert result.audit_degraded is False
    assert [record.result for record in sink.records] == [
        AuditResult.ATTEMPTED,
        AuditResult.SUCCEEDED,
    ]


async def test_normal_command_uses_fallback_without_false_failure() -> None:
    authority = CockpitService()
    buffer = AuditBuffer(max_records=4)
    gateway = AuthorizedCockpitGateway(
        authority,
        InMemoryAuditSink(available=False),
        fallback_buffer=buffer,
    )

    result = await gateway.apply_command(
        Principal("operator-1", Role.OPERATOR, "session-operator"),
        command(CommandName.SET_MEDIA_STATE, {"state": "playing"}, EndpointId.PASSENGER),
        server_endpoint=EndpointId.PASSENGER,
    )

    assert result.envelope.payload.passenger.media_state == "playing"
    assert result.audit_delivery is AuditDelivery.FALLBACK
    assert result.audit_degraded is True
    assert result.audit_recorded is True
    assert buffer.records[0].result is AuditResult.SUCCEEDED
    assert buffer.records[0].delivery is AuditDelivery.FALLBACK


async def test_command_returns_truthful_success_when_all_audit_delivery_is_lost() -> None:
    authority = CockpitService()
    gateway = AuthorizedCockpitGateway(
        authority,
        ExplodingAuditSink(),
        fallback_buffer=FailingFallback(),
    )

    result = await gateway.apply_command(
        Principal("operator-1", Role.OPERATOR, "session-operator"),
        command(CommandName.SET_MEDIA_STATE, {"state": "playing"}, EndpointId.PASSENGER),
        server_endpoint=EndpointId.PASSENGER,
    )

    assert result.envelope.payload.passenger.media_state == "playing"
    assert result.audit_delivery is AuditDelivery.LOST
    assert result.audit_degraded is True
    assert result.audit_recorded is False
