from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.cockpit.broker import SnapshotBroker
from app.cockpit.errors import CommandRejected
from app.cockpit.service import CockpitService
from app.contracts.v1 import (
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    EndpointId,
    MessageSource,
    SystemMode,
)


def command(
    name: CommandName,
    parameters: dict,
    *,
    endpoint: EndpointId = EndpointId.CONTROL,
) -> CommandEnvelopeV1:
    return CommandEnvelopeV1(
        message_id=uuid4(),
        correlation_id=uuid4(),
        timestamp=datetime.now(UTC),
        source=MessageSource(kind="endpoint", id=endpoint.value),
        payload=CommandPayloadV1(
            name=name,
            endpoint=endpoint,
            parameters=parameters,
        ),
    )


async def test_transition_failure_is_transactional() -> None:
    authority = CockpitService()
    before = await authority.get_snapshot()

    with pytest.raises(CommandRejected) as captured:
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


async def test_unresolved_critical_risk_locks_takeover_mode() -> None:
    authority = CockpitService()
    await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )

    with pytest.raises(CommandRejected) as captured:
        await authority.apply_command(
            command(CommandName.SET_SYSTEM_MODE, {"mode": "normal"})
        )

    snapshot = await authority.get_snapshot()
    assert captured.value.code == "invalid_transition"
    assert snapshot.system_mode is SystemMode.TAKEOVER
    assert snapshot.passenger.media_state == "suppressed"


async def test_reset_rebuilds_live_endpoint_connectivity() -> None:
    authority = CockpitService()
    queue = await authority.connect_endpoint(EndpointId.HUD)
    before = await authority.get_snapshot()

    reset = await authority.apply_command(
        command(CommandName.RESET_SESSION, {})
    )

    assert reset.payload.session_id != before.session_id
    assert reset.payload.endpoint_connectivity[EndpointId.HUD].status.value == "fresh"
    await authority.disconnect_endpoint(EndpointId.HUD, queue)


def test_broker_keeps_only_latest_snapshot_per_subscriber() -> None:
    broker = SnapshotBroker()
    queue, first = broker.subscribe(EndpointId.CLUSTER)

    assert first is True
    assert queue.maxsize == 1
    assert broker.count(EndpointId.CLUSTER) == 1
