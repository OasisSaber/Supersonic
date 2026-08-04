from __future__ import annotations

from dataclasses import dataclass

from ..contracts.v1 import (
    CockpitSnapshotV1,
    CommandEnvelopeV1,
    CommandName,
    DataFreshness,
    DataHealth,
    FlowId,
    MapServiceStatus,
    NavigationStateV1,
    NavigationStep,
    RiskEventV1,
    RiskLifecycle,
    RiskSeverity,
    RiskSource,
    RiskType,
    RouteProvider,
    RouteStatus,
    SystemMode,
    ThemeMode,
)
from .errors import CommandRejected
from .policies import Parameters
from .state_factory import Clock, CockpitStateFactory, IdFactory, navigation_data_freshness

DESTINATION_NAME_MAX_LENGTH = 160
SUGGESTION_MAX_LENGTH = 200


@dataclass(frozen=True, slots=True)
class TransitionResult:
    snapshot: CockpitSnapshotV1
    changed: bool
    reset: bool = False
    resolved_risk: RiskEventV1 | None = None


class CockpitTransitions:
    """Apply domain transitions to a defensive copy of the aggregate."""

    def __init__(
        self,
        *,
        clock: Clock,
        id_factory: IdFactory,
        state_factory: CockpitStateFactory,
    ) -> None:
        self._clock = clock
        self._id_factory = id_factory
        self._state_factory = state_factory

    def apply(
        self,
        current: CockpitSnapshotV1,
        command: CommandEnvelopeV1,
    ) -> TransitionResult:
        candidate = current.model_copy(deep=True)
        name = command.payload.name
        params = Parameters(command.payload.parameters)
        resolved_risk: RiskEventV1 | None = None

        if name is CommandName.SET_THEME:
            params.require_exact("theme")
            value = params.enum(
                "theme",
                ThemeMode,
                message="theme must be day or night.",
            )
            if value == candidate.theme:
                return TransitionResult(candidate, changed=False)
            candidate.theme = value

        elif name is CommandName.SET_SYSTEM_MODE:
            params.require_exact("mode")
            value = params.enum(
                "mode",
                SystemMode,
                message="mode is not a valid system mode.",
            )
            if value is not SystemMode.TAKEOVER and has_unresolved_critical_risk(candidate):
                raise CommandRejected(
                    "invalid_transition",
                    "Resolve all critical risks before leaving takeover mode.",
                    status_code=409,
                )
            if value == candidate.system_mode:
                return TransitionResult(candidate, changed=False)
            candidate.system_mode = value
            if value is SystemMode.TAKEOVER:
                self._activate_simulated_takeover(candidate)

        elif name is CommandName.SELECT_DESTINATION:
            params.require_exact("destinationName")
            destination = params.text(
                "destinationName",
                max_length=DESTINATION_NAME_MAX_LENGTH,
            )
            navigation = NavigationStateV1(
                provider=RouteProvider.LOCAL_FALLBACK,
                service_status=MapServiceStatus.DEGRADED,
                status=RouteStatus.PREVIEW,
                destination_name=destination,
                remaining_distance_meters=8400,
                eta_seconds=960,
                current_step=NavigationStep(
                    index=0,
                    instruction="前方 300 米右转",
                    road_name="滨河大道",
                    distance_meters=300,
                    maneuver="turn_right",
                ),
                steps=[],
                polyline=[],
                updated_at=self._clock(),
            )
            candidate.active_flow = FlowId.NAVIGATION_HANDOFF
            candidate.navigation = navigation
            synchronize_navigation_health(candidate)

        elif name is CommandName.CONFIRM_ROUTE:
            params.require_exact()
            if candidate.navigation.status is not RouteStatus.PREVIEW:
                raise CommandRejected(
                    "invalid_transition",
                    "A route preview is required before confirmation.",
                )
            candidate.navigation.status = RouteStatus.ACTIVE
            candidate.navigation.updated_at = self._clock()
            synchronize_navigation_health(candidate)

        elif name in {CommandName.ACKNOWLEDGE_RISK, CommandName.RESOLVE_RISK}:
            params.require_exact("eventId")
            event_id = params.text("eventId", max_length=256)
            risk = next(
                (item for item in candidate.risks if item.event_id == event_id),
                None,
            )
            if risk is None:
                raise CommandRejected(
                    "risk_not_found",
                    "The risk event is not active in this snapshot.",
                    status_code=404,
                )
            if name is CommandName.ACKNOWLEDGE_RISK:
                if risk.lifecycle is not RiskLifecycle.ACTIVE:
                    raise CommandRejected(
                        "invalid_transition",
                        "Only active risks can be acknowledged.",
                    )
                risk.lifecycle = RiskLifecycle.ACKNOWLEDGED
            else:
                if risk.lifecycle is not RiskLifecycle.ACKNOWLEDGED:
                    raise CommandRejected(
                        "invalid_transition",
                        "Only acknowledged risks can be resolved.",
                    )
                risk.lifecycle = RiskLifecycle.RESOLVED
                candidate.system_mode = SystemMode.RECOVERY
                resolved_risk = risk
            risk.updated_at = self._clock()

        elif name is CommandName.SET_MEDIA_STATE:
            params.require_exact("state")
            value = params.text("state", max_length=16)
            if value not in {"playing", "paused"}:
                raise CommandRejected(
                    "invalid_parameters",
                    "state must be playing or paused.",
                )
            if has_unresolved_critical_risk(candidate):
                raise CommandRejected(
                    "safety_suppressed",
                    "Media controls are disabled during driver takeover.",
                    status_code=409,
                )
            if candidate.passenger.media_state == value:
                return TransitionResult(candidate, changed=False)
            candidate.passenger.media_state = value

        elif name is CommandName.SUBMIT_TRIP_SUGGESTION:
            params.require_exact("suggestion")
            suggestion = params.text(
                "suggestion",
                max_length=SUGGESTION_MAX_LENGTH,
            )
            candidate.active_flow = FlowId.PASSENGER_COLLABORATION
            candidate.passenger.trip_suggestions = [
                suggestion,
                *candidate.passenger.trip_suggestions,
            ][:8]

        elif name is CommandName.SET_CABIN_CONTROL:
            params.require_exact("privacyEnabled")
            value = params.boolean("privacyEnabled")
            if candidate.passenger.privacy_enabled is value:
                return TransitionResult(candidate, changed=False)
            candidate.passenger.privacy_enabled = value

        elif name is CommandName.RESET_SESSION:
            params.require_exact()
            reset_snapshot = self._state_factory.create_default(
                revision=current.revision,
            )
            return TransitionResult(reset_snapshot, changed=True, reset=True)

        else:
            raise CommandRejected(
                "command_not_implemented",
                f"Command {name.value} is reserved but not implemented.",
                status_code=501,
            )

        synchronize_risk_dependent_state(
            candidate,
            clock=self._clock,
            resolved_risk=resolved_risk,
        )
        return TransitionResult(
            candidate,
            changed=True,
            resolved_risk=resolved_risk,
        )

    def _activate_simulated_takeover(self, snapshot: CockpitSnapshotV1) -> None:
        if has_unresolved_critical_risk(snapshot):
            return
        now = self._clock()
        snapshot.risks.append(
            RiskEventV1(
                event_id=f"simulated-takeover-{self._id_factory()}",
                session_id=snapshot.session_id,
                risk_type=RiskType.DRIVER_DISTRACTION,
                lifecycle=RiskLifecycle.ACTIVE,
                severity=RiskSeverity.CRITICAL,
                source=RiskSource.SIMULATED_EVENT,
                confidence=1,
                occurred_at=now,
                updated_at=now,
                message="演示场景：驾驶员注意力风险，立即接管",
                evidence=["control_scenario:simulated_takeover"],
                metadata={"scenario": "simulated_takeover"},
            )
        )
        snapshot.data_health["vision"] = DataHealth(
            status=DataFreshness.FRESH,
            updated_at=now,
        )


def has_unresolved_critical_risk(snapshot: CockpitSnapshotV1) -> bool:
    return any(
        risk.severity is RiskSeverity.CRITICAL
        and risk.lifecycle in {RiskLifecycle.ACTIVE, RiskLifecycle.ACKNOWLEDGED}
        for risk in snapshot.risks
    )


def synchronize_navigation_health(snapshot: CockpitSnapshotV1) -> None:
    navigation = snapshot.navigation
    snapshot.data_health["navigation"] = DataHealth(
        status=navigation_data_freshness(navigation),
        updated_at=navigation.updated_at,
    )


def synchronize_risk_dependent_state(
    snapshot: CockpitSnapshotV1,
    *,
    clock: Clock,
    resolved_risk: RiskEventV1 | None = None,
) -> None:
    if has_unresolved_critical_risk(snapshot):
        snapshot.system_mode = SystemMode.TAKEOVER
        snapshot.active_flow = FlowId.RISK_TAKEOVER
        snapshot.passenger.media_state = "suppressed"
        return

    if snapshot.passenger.media_state == "suppressed":
        snapshot.passenger.media_state = "paused"
    if snapshot.active_flow is FlowId.RISK_TAKEOVER:
        snapshot.active_flow = FlowId.NAVIGATION_HANDOFF
    if resolved_risk is not None and resolved_risk.source is RiskSource.SIMULATED_EVENT:
        snapshot.data_health["vision"] = DataHealth(
            status=DataFreshness.OFFLINE,
            updated_at=clock(),
        )
