from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.cockpit_state import CockpitStateAuthority, CommandRejected
from app.contracts.v1 import (
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    DataFreshness,
    EndpointId,
    MessageSource,
    SystemMode,
    ThemeMode,
)


def command(
    name: CommandName,
    parameters: dict,
    *,
    endpoint: EndpointId = EndpointId.CONTROL,
    source_id: str | None = None,
) -> CommandEnvelopeV1:
    return CommandEnvelopeV1(
        message_id=uuid4(),
        correlation_id=uuid4(),
        timestamp=datetime.now(UTC),
        source=MessageSource(kind="endpoint", id=source_id or endpoint.value),
        payload=CommandPayloadV1(name=name, endpoint=endpoint, parameters=parameters),
    )


async def test_supported_commands_are_authoritative_and_idempotent() -> None:
    authority = CockpitStateAuthority()
    initial = await authority.get_snapshot()
    request = command(CommandName.SET_THEME, {"theme": "day"})

    changed = await authority.apply_command(request)
    unchanged = await authority.apply_command(request)

    assert changed.correlation_id == request.correlation_id
    assert changed.payload.theme is ThemeMode.DAY
    assert changed.payload.revision == initial.revision + 1
    assert unchanged.payload.revision == changed.payload.revision


async def test_rejected_command_does_not_change_snapshot() -> None:
    authority = CockpitStateAuthority()
    before = await authority.get_snapshot()

    with pytest.raises(CommandRejected, match="source") as captured:
        await authority.apply_command(
            command(CommandName.SET_THEME, {"theme": "day"}, source_id="passenger")
        )

    after = await authority.get_snapshot()
    assert captured.value.code == "source_mismatch"
    assert after == before


async def test_navigation_handoff_is_authoritative_and_requires_a_preview() -> None:
    authority = CockpitStateAuthority()

    with pytest.raises(CommandRejected) as captured:
        await authority.apply_command(command(CommandName.CONFIRM_ROUTE, {}))

    assert captured.value.code == "invalid_transition"

    preview = await authority.apply_command(
        command(CommandName.SELECT_DESTINATION, {"destinationName": "城市艺术中心"})
    )
    active = await authority.apply_command(command(CommandName.CONFIRM_ROUTE, {}))

    assert preview.payload.navigation.status.value == "preview"
    assert active.payload.navigation.status.value == "active"
    assert active.payload.navigation.destination_name == "城市艺术中心"


async def test_passenger_commands_are_server_authoritative() -> None:
    authority = CockpitStateAuthority()
    media = await authority.apply_command(
        command(CommandName.SET_MEDIA_STATE, {"state": "playing"}, endpoint=EndpointId.PASSENGER)
    )
    privacy = await authority.apply_command(
        command(
            CommandName.SET_CABIN_CONTROL,
            {"privacyEnabled": False},
            endpoint=EndpointId.PASSENGER,
        )
    )
    suggested = await authority.apply_command(
        command(
            CommandName.SUBMIT_TRIP_SUGGESTION,
            {"suggestion": "建议在城市艺术中心短暂停留"},
            endpoint=EndpointId.PASSENGER,
        )
    )

    assert media.payload.passenger.media_state == "playing"
    assert privacy.payload.passenger.privacy_enabled is False
    assert suggested.payload.passenger.trip_suggestions == ["建议在城市艺术中心短暂停留"]


async def test_control_takeover_is_a_labelled_simulated_risk_lifecycle() -> None:
    authority = CockpitStateAuthority()
    takeover = await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )
    risk = takeover.payload.risks[0]

    assert risk.source.value == "simulated_event"
    assert risk.lifecycle.value == "active"
    assert takeover.payload.passenger.media_state == "suppressed"

    acknowledged = await authority.apply_command(
        command(CommandName.ACKNOWLEDGE_RISK, {"eventId": risk.event_id})
    )
    resolved = await authority.apply_command(
        command(CommandName.RESOLVE_RISK, {"eventId": risk.event_id})
    )

    assert acknowledged.payload.risks[0].lifecycle.value == "acknowledged"
    assert resolved.payload.risks[0].lifecycle.value == "resolved"
    assert resolved.payload.system_mode.value == "recovery"


async def test_endpoint_permission_is_enforced_before_execution() -> None:
    authority = CockpitStateAuthority()

    with pytest.raises(CommandRejected) as captured:
        await authority.apply_command(
            command(
                CommandName.SET_THEME,
                {"theme": "day"},
                endpoint=EndpointId.CLUSTER,
            )
        )

    assert captured.value.code == "command_forbidden"
    assert (await authority.get_snapshot()).revision == 0


async def test_reset_changes_session_and_keeps_revision_monotonic() -> None:
    authority = CockpitStateAuthority()
    changed = await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )

    reset = await authority.apply_command(command(CommandName.RESET_SESSION, {}))

    assert reset.payload.session_id != changed.payload.session_id
    assert reset.payload.revision == changed.payload.revision + 1
    assert reset.payload.system_mode is SystemMode.NORMAL
    assert reset.payload.theme is ThemeMode.NIGHT


async def test_slow_subscriber_only_retains_latest_snapshot() -> None:
    authority = CockpitStateAuthority()
    queue = await authority.connect_endpoint(EndpointId.CLUSTER)
    connected = await authority.get_snapshot()

    await authority.apply_command(command(CommandName.SET_THEME, {"theme": "day"}))
    latest = await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "warning"})
    )

    assert queue.maxsize == 1
    assert queue.qsize() == 1
    queued = queue.get_nowait()
    assert queued.payload.revision == latest.payload.revision
    assert queued.payload.revision > connected.revision
    assert queued.payload.system_mode is SystemMode.WARNING

    await authority.disconnect_endpoint(EndpointId.CLUSTER, queue)
    disconnected = await authority.get_snapshot()
    assert disconnected.endpoint_connectivity[EndpointId.CLUSTER].status is DataFreshness.OFFLINE


async def test_endpoint_connection_counts_do_not_report_early_offline() -> None:
    authority = CockpitStateAuthority()
    first = await authority.connect_endpoint(EndpointId.CENTER)
    second = await authority.connect_endpoint(EndpointId.CENTER)
    revision = (await authority.get_snapshot()).revision

    await authority.disconnect_endpoint(EndpointId.CENTER, first)
    still_connected = await authority.get_snapshot()
    assert still_connected.revision == revision
    assert still_connected.endpoint_connectivity[EndpointId.CENTER].status is DataFreshness.FRESH

    await authority.disconnect_endpoint(EndpointId.CENTER, second)
    assert (await authority.get_snapshot()).revision == revision + 1
