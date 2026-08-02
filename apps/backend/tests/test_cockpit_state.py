from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.cockpit_state import (
    CockpitStateAuthority,
    CommandRejected,
    navigation_data_freshness,
)
from app.contracts.v1 import (
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    DataFreshness,
    EndpointId,
    MapServiceStatus,
    MessageSource,
    NavigationStateV1,
    RouteProvider,
    RouteStatus,
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


async def test_select_destination_rejects_overlong_name_without_mutation() -> None:
    authority = CockpitStateAuthority()
    before = await authority.get_snapshot()

    with pytest.raises(CommandRejected, match="destinationName") as captured:
        await authority.apply_command(
            command(
                CommandName.SELECT_DESTINATION,
                {"destinationName": "x" * 161},
                endpoint=EndpointId.CENTER,
            )
        )

    after = await authority.get_snapshot()
    assert captured.value.code == "invalid_parameters"
    assert after == before


async def test_select_destination_accepts_name_at_contract_max_length() -> None:
    authority = CockpitStateAuthority()
    initial = await authority.get_snapshot()

    changed = await authority.apply_command(
        command(
            CommandName.SELECT_DESTINATION,
            {"destinationName": "x" * 160},
            endpoint=EndpointId.CENTER,
        )
    )

    assert changed.payload.revision == initial.revision + 1
    assert changed.payload.navigation.destination_name == "x" * 160


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
    assert preview.payload.data_health["navigation"].status is DataFreshness.STALE
    assert (
        preview.payload.data_health["navigation"].updated_at
        == preview.payload.navigation.updated_at
    )
    assert active.payload.navigation.status.value == "active"
    assert active.payload.data_health["navigation"].status is DataFreshness.STALE
    assert (
        active.payload.data_health["navigation"].updated_at
        == active.payload.navigation.updated_at
    )
    assert active.payload.navigation.destination_name == "城市艺术中心"


@pytest.mark.parametrize(
    ("provider", "service", "status", "expected"),
    [
        (RouteProvider.NONE, MapServiceStatus.UNAVAILABLE, RouteStatus.IDLE, DataFreshness.OFFLINE),
        (
            RouteProvider.LOCAL_FALLBACK,
            MapServiceStatus.DEGRADED,
            RouteStatus.PREVIEW,
            DataFreshness.STALE,
        ),
        (
            RouteProvider.LOCAL_FALLBACK,
            MapServiceStatus.DEGRADED,
            RouteStatus.ACTIVE,
            DataFreshness.STALE,
        ),
        (RouteProvider.AMAP, MapServiceStatus.LIVE, RouteStatus.ACTIVE, DataFreshness.FRESH),
        (
            RouteProvider.AMAP,
            MapServiceStatus.UNAVAILABLE,
            RouteStatus.UNAVAILABLE,
            DataFreshness.OFFLINE,
        ),
    ],
)
def test_navigation_health_policy_is_deterministic(
    provider: RouteProvider,
    service: MapServiceStatus,
    status: RouteStatus,
    expected: DataFreshness,
) -> None:
    navigation = NavigationStateV1(
        provider=provider,
        service_status=service,
        status=status,
        updated_at=datetime.now(UTC),
    )

    assert navigation_data_freshness(navigation) is expected


async def test_navigation_health_is_identical_for_every_subscriber() -> None:
    authority = CockpitStateAuthority()
    cluster = await authority.connect_endpoint(EndpointId.CLUSTER)
    passenger = await authority.connect_endpoint(EndpointId.PASSENGER)

    changed = await authority.apply_command(
        command(CommandName.SELECT_DESTINATION, {"destinationName": "城市艺术中心"})
    )
    cluster_snapshot = cluster.get_nowait()
    passenger_snapshot = passenger.get_nowait()

    assert changed.payload.data_health["navigation"].status is DataFreshness.STALE
    assert cluster_snapshot.payload == changed.payload
    assert passenger_snapshot.payload == changed.payload

    await authority.disconnect_endpoint(EndpointId.CLUSTER, cluster)
    await authority.disconnect_endpoint(EndpointId.PASSENGER, passenger)


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
        command(CommandName.SELECT_DESTINATION, {"destinationName": "城市艺术中心"})
    )

    reset = await authority.apply_command(command(CommandName.RESET_SESSION, {}))

    assert reset.payload.session_id != changed.payload.session_id
    assert reset.payload.revision == changed.payload.revision + 1
    assert reset.payload.system_mode is SystemMode.NORMAL
    assert reset.payload.theme is ThemeMode.NIGHT
    assert reset.payload.navigation.status is RouteStatus.IDLE
    assert reset.payload.data_health["navigation"].status is DataFreshness.OFFLINE
    assert (
        reset.payload.data_health["navigation"].updated_at
        == reset.payload.navigation.updated_at
    )


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

async def test_reset_rebuilds_connectivity_with_zero_active_connections() -> None:
    authority = CockpitStateAuthority()

    reset = await authority.apply_command(command(CommandName.RESET_SESSION, {}))

    assert all(
        conn.status is DataFreshness.OFFLINE
        for conn in reset.payload.endpoint_connectivity.values()
    )


async def test_reset_preserves_fresh_for_single_active_connection() -> None:
    authority = CockpitStateAuthority()
    queue = await authority.connect_endpoint(EndpointId.CLUSTER)

    reset = await authority.apply_command(command(CommandName.RESET_SESSION, {}))

    assert reset.payload.endpoint_connectivity[EndpointId.CLUSTER].status is DataFreshness.FRESH
    assert reset.payload.endpoint_connectivity[EndpointId.HUD].status is DataFreshness.OFFLINE

    await authority.disconnect_endpoint(EndpointId.CLUSTER, queue)
    after = await authority.get_snapshot()
    assert after.endpoint_connectivity[EndpointId.CLUSTER].status is DataFreshness.OFFLINE


async def test_reset_preserves_fresh_for_multiple_active_connections() -> None:
    authority = CockpitStateAuthority()
    center_first = await authority.connect_endpoint(EndpointId.CENTER)
    center_second = await authority.connect_endpoint(EndpointId.CENTER)
    passenger = await authority.connect_endpoint(EndpointId.PASSENGER)

    reset = await authority.apply_command(command(CommandName.RESET_SESSION, {}))

    assert reset.payload.endpoint_connectivity[EndpointId.CENTER].status is DataFreshness.FRESH
    assert reset.payload.endpoint_connectivity[EndpointId.PASSENGER].status is DataFreshness.FRESH
    assert reset.payload.endpoint_connectivity[EndpointId.HUD].status is DataFreshness.OFFLINE

    await authority.disconnect_endpoint(EndpointId.CENTER, center_first)
    still_connected = await authority.get_snapshot()
    assert still_connected.endpoint_connectivity[EndpointId.CENTER].status is DataFreshness.FRESH
    await authority.disconnect_endpoint(EndpointId.CENTER, center_second)
    after_center = await authority.get_snapshot()
    assert after_center.endpoint_connectivity[EndpointId.CENTER].status is DataFreshness.OFFLINE
    assert after_center.endpoint_connectivity[EndpointId.PASSENGER].status is DataFreshness.FRESH

    await authority.disconnect_endpoint(EndpointId.PASSENGER, passenger)
    last = await authority.get_snapshot()
    assert last.endpoint_connectivity[EndpointId.PASSENGER].status is DataFreshness.OFFLINE


async def test_reset_publishes_one_coherent_post_reset_snapshot() -> None:
    authority = CockpitStateAuthority()
    queue = await authority.connect_endpoint(EndpointId.CLUSTER)
    previous_session = (await authority.get_snapshot()).session_id

    reset = await authority.apply_command(command(CommandName.RESET_SESSION, {}))

    assert queue.qsize() == 1
    queued = queue.get_nowait()
    assert queued.payload.session_id == reset.payload.session_id
    assert queued.payload.session_id != previous_session
    assert queued.payload.endpoint_connectivity[EndpointId.CLUSTER].status is DataFreshness.FRESH
