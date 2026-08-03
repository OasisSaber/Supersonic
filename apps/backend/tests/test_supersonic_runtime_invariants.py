from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.cockpit_state import CockpitStateAuthority, CommandRejected
from app.contracts.v1 import (
    CockpitSnapshotV1,
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    DataFreshness,
    EndpointId,
    FlowId,
    MessageSource,
    PassengerStateV1,
    RiskEventV1,
    RiskLifecycle,
    RiskSeverity,
    RiskSource,
    RiskType,
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


async def create_acknowledged_takeover(
    authority: CockpitStateAuthority,
) -> str:
    takeover = await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )
    event_id = takeover.payload.risks[0].event_id
    await authority.apply_command(
        command(CommandName.ACKNOWLEDGE_RISK, {"eventId": event_id})
    )
    return event_id


async def test_control_cannot_leave_takeover_while_critical_risk_is_unresolved() -> None:
    authority = CockpitStateAuthority()
    await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )
    before = await authority.get_snapshot()

    with pytest.raises(CommandRejected) as captured:
        await authority.apply_command(
            command(CommandName.SET_SYSTEM_MODE, {"mode": "normal"})
        )

    after = await authority.get_snapshot()
    assert captured.value.code == "invalid_transition"
    assert captured.value.status_code == 409
    assert after == before
    assert after.system_mode is SystemMode.TAKEOVER
    assert after.active_flow is FlowId.RISK_TAKEOVER
    assert after.passenger.media_state == "suppressed"


async def test_media_controls_cannot_break_safety_suppression() -> None:
    authority = CockpitStateAuthority()
    await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )
    before = await authority.get_snapshot()

    with pytest.raises(CommandRejected) as captured:
        await authority.apply_command(
            command(
                CommandName.SET_MEDIA_STATE,
                {"state": "paused"},
                endpoint=EndpointId.CENTER,
            )
        )

    after = await authority.get_snapshot()
    assert captured.value.code == "safety_suppressed"
    assert after == before
    assert after.passenger.media_state == "suppressed"


async def test_resolving_last_critical_risk_restores_coherent_recovery_state() -> None:
    authority = CockpitStateAuthority()
    event_id = await create_acknowledged_takeover(authority)

    resolved = await authority.apply_command(
        command(CommandName.RESOLVE_RISK, {"eventId": event_id})
    )

    risk = resolved.payload.risks[0]
    assert risk.lifecycle is RiskLifecycle.RESOLVED
    assert resolved.payload.system_mode is SystemMode.RECOVERY
    assert resolved.payload.active_flow is FlowId.NAVIGATION_HANDOFF
    assert resolved.payload.passenger.media_state == "paused"
    assert resolved.payload.data_health["vision"].status is DataFreshness.OFFLINE


async def test_non_risk_commands_cannot_steal_active_flow_during_takeover() -> None:
    authority = CockpitStateAuthority()
    await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )

    navigation = await authority.apply_command(
        command(
            CommandName.SELECT_DESTINATION,
            {"destinationName": "城市艺术中心"},
            endpoint=EndpointId.CENTER,
        )
    )
    suggestion = await authority.apply_command(
        command(
            CommandName.SUBMIT_TRIP_SUGGESTION,
            {"suggestion": "建议短暂停留"},
            endpoint=EndpointId.PASSENGER,
        )
    )

    assert navigation.payload.active_flow is FlowId.RISK_TAKEOVER
    assert suggestion.payload.active_flow is FlowId.RISK_TAKEOVER
    assert suggestion.payload.system_mode is SystemMode.TAKEOVER
    assert suggestion.payload.passenger.media_state == "suppressed"


async def test_normal_mode_is_available_after_risk_resolution() -> None:
    authority = CockpitStateAuthority()
    event_id = await create_acknowledged_takeover(authority)
    await authority.apply_command(
        command(CommandName.RESOLVE_RISK, {"eventId": event_id})
    )

    normal = await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "normal"})
    )

    assert normal.payload.system_mode is SystemMode.NORMAL
    assert normal.payload.passenger.media_state == "paused"
    assert all(
        risk.lifecycle is RiskLifecycle.RESOLVED
        for risk in normal.payload.risks
    )

async def test_snapshot_contract_rejects_missing_required_runtime_maps() -> None:
    authority = CockpitStateAuthority()
    snapshot = await authority.get_snapshot()
    payload = snapshot.model_dump(by_alias=False)
    payload["data_health"].pop("vision")

    with pytest.raises(ValidationError, match="data_health is missing required domains"):
        CockpitSnapshotV1.model_validate(payload)

    payload = snapshot.model_dump(by_alias=False)
    payload["endpoint_connectivity"].pop(EndpointId.CONTROL)
    with pytest.raises(ValidationError, match="endpoint_connectivity is missing endpoints"):
        CockpitSnapshotV1.model_validate(payload)


def test_passenger_contract_rejects_overlong_suggestion() -> None:
    with pytest.raises(ValidationError):
        PassengerStateV1(trip_suggestions=["x" * 201])


async def test_resolving_one_critical_risk_keeps_takeover_while_another_is_active() -> None:
    authority = CockpitStateAuthority()
    first_event = await create_acknowledged_takeover(authority)
    # 直接注入第二个未解决的 critical 风险，验证同步函数在仍有未处置
    # critical 风险时不会退出 takeover（覆盖 cockpit_state.py 的
    # _synchronize_risk_dependent_state_locked 未处置分支）。
    authority._snapshot.risks.append(
        RiskEventV1(
            event_id="simulated-takeover-extra",
            session_id=authority._snapshot.session_id,
            risk_type=RiskType.DRIVER_DISTRACTION,
            lifecycle=RiskLifecycle.ACTIVE,
            severity=RiskSeverity.CRITICAL,
            source=RiskSource.SIMULATED_EVENT,
            confidence=1,
            occurred_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            message="演示场景：第二个未处置关键风险",
            evidence=["control_scenario:simulated_takeover"],
            metadata={"scenario": "simulated_takeover"},
        )
    )

    resolved = await authority.apply_command(
        command(CommandName.RESOLVE_RISK, {"eventId": first_event})
    )

    assert resolved.payload.system_mode is SystemMode.TAKEOVER
    assert resolved.payload.active_flow is FlowId.RISK_TAKEOVER
    assert resolved.payload.passenger.media_state == "suppressed"
    assert all(
        risk.lifecycle is not RiskLifecycle.ACTIVE or risk.event_id == "simulated-takeover-extra"
        for risk in resolved.payload.risks
    )


async def test_repeated_takeover_command_is_idempotent() -> None:
    authority = CockpitStateAuthority()
    await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )
    before = await authority.get_snapshot()

    # 已处于 takeover 时再次请求 takeover：命令级幂等短路（mode 相同直接
    # 返回），不得重复创建风险事件，也不得改变任何权威状态。
    second = await authority.apply_command(
        command(CommandName.SET_SYSTEM_MODE, {"mode": "takeover"})
    )
    after = await authority.get_snapshot()

    assert second.payload == before
    assert after == before
    assert len(after.risks) == 1
