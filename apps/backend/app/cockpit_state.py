from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .contracts.v1 import (
    CONTRACT_VERSION,
    ENDPOINT_COMMAND_PERMISSIONS,
    CockpitSnapshotV1,
    CommandEnvelopeV1,
    CommandName,
    DataFreshness,
    DataHealth,
    EndpointConnection,
    EndpointId,
    FlowId,
    MapServiceStatus,
    MessageSource,
    NavigationStateV1,
    NavigationStep,
    PassengerStateV1,
    RiskEventV1,
    RiskLifecycle,
    RiskSeverity,
    RiskSource,
    RiskType,
    RouteProvider,
    RouteStatus,
    SnapshotEnvelopeV1,
    SystemMode,
    ThemeMode,
    VehicleStateV1,
)


class CommandRejected(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CockpitStateAuthority:
    """Owns the single in-memory cockpit state and broadcasts full snapshots."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue[SnapshotEnvelopeV1]] = set()
        self._connection_counts = dict.fromkeys(EndpointId, 0)
        self._snapshot = self._make_default_snapshot(revision=0)

    def _make_default_snapshot(self, *, revision: int) -> CockpitSnapshotV1:
        now = self._clock()
        return CockpitSnapshotV1(
            session_id=str(self._id_factory()),
            revision=revision,
            timestamp=now,
            theme=ThemeMode.NIGHT,
            system_mode=SystemMode.NORMAL,
            active_flow=FlowId.NAVIGATION_HANDOFF,
            data_health={
                "vehicle": DataHealth(status=DataFreshness.FRESH, updated_at=now),
                "navigation": DataHealth(status=DataFreshness.OFFLINE, updated_at=now),
                "vision": DataHealth(status=DataFreshness.OFFLINE, updated_at=now),
            },
            vehicle=VehicleStateV1(
                speed_kph=0,
                gear="P",
                battery_percent=82,
                range_km=436,
                drive_mode="comfort",
                seatbelt_fastened=True,
            ),
            navigation=NavigationStateV1(
                provider=RouteProvider.NONE,
                service_status=MapServiceStatus.UNAVAILABLE,
                status=RouteStatus.IDLE,
                updated_at=now,
            ),
            passenger=PassengerStateV1(),
            endpoint_connectivity={
                endpoint: EndpointConnection(status=DataFreshness.OFFLINE, last_seen_at=now)
                for endpoint in EndpointId
            },
            capabilities=[
                CommandName.SET_THEME.value,
                CommandName.SET_SYSTEM_MODE.value,
                CommandName.RESET_SESSION.value,
            ],
        )

    async def get_snapshot(self) -> CockpitSnapshotV1:
        async with self._lock:
            return self._snapshot.model_copy(deep=True)

    async def apply_command(self, command: CommandEnvelopeV1) -> SnapshotEnvelopeV1:
        async with self._lock:
            self._validate_command(command)
            changed = self._apply_supported_command(command)
            if changed:
                self._touch_locked()
                self._publish_locked(command.correlation_id)
            return self._make_envelope_locked(command.correlation_id)

    async def connect_endpoint(
        self, endpoint: EndpointId
    ) -> asyncio.Queue[SnapshotEnvelopeV1]:
        queue: asyncio.Queue[SnapshotEnvelopeV1] = asyncio.Queue(maxsize=1)
        async with self._lock:
            self._subscribers.add(queue)
            self._connection_counts[endpoint] += 1
            if self._connection_counts[endpoint] == 1:
                self._set_connection_locked(endpoint, DataFreshness.FRESH)
                self._touch_locked()
            self._publish_locked(self._id_factory())
        return queue

    async def disconnect_endpoint(
        self,
        endpoint: EndpointId,
        queue: asyncio.Queue[SnapshotEnvelopeV1],
    ) -> None:
        async with self._lock:
            self._subscribers.discard(queue)
            if self._connection_counts[endpoint] == 0:
                return
            self._connection_counts[endpoint] -= 1
            if self._connection_counts[endpoint] == 0:
                self._set_connection_locked(endpoint, DataFreshness.OFFLINE)
                self._touch_locked()
                self._publish_locked(self._id_factory())

    def _validate_command(self, command: CommandEnvelopeV1) -> None:
        endpoint = command.payload.endpoint
        if command.source.kind != "endpoint" or command.source.id != endpoint.value:
            raise CommandRejected(
                "source_mismatch",
                "Command source must match the declared endpoint.",
                status_code=403,
            )
        if command.payload.name not in ENDPOINT_COMMAND_PERMISSIONS[endpoint]:
            raise CommandRejected(
                "command_forbidden",
                f"Endpoint {endpoint.value} cannot issue {command.payload.name.value}.",
                status_code=403,
            )
        if command.payload.name not in {
            CommandName.SET_THEME,
            CommandName.SET_SYSTEM_MODE,
            CommandName.SELECT_DESTINATION,
            CommandName.CONFIRM_ROUTE,
            CommandName.ACKNOWLEDGE_RISK,
            CommandName.RESOLVE_RISK,
            CommandName.SET_MEDIA_STATE,
            CommandName.SUBMIT_TRIP_SUGGESTION,
            CommandName.SET_CABIN_CONTROL,
            CommandName.RESET_SESSION,
        }:
            raise CommandRejected(
                "command_not_implemented",
                f"Command {command.payload.name.value} is reserved but not implemented.",
                status_code=501,
            )

    def _apply_supported_command(self, command: CommandEnvelopeV1) -> bool:
        name = command.payload.name
        parameters = command.payload.parameters
        if name is CommandName.SET_THEME:
            self._require_keys(parameters, {"theme"})
            try:
                value = ThemeMode(parameters["theme"])
            except (TypeError, ValueError) as exc:
                raise CommandRejected("invalid_parameters", "theme must be day or night.") from exc
            if value == self._snapshot.theme:
                return False
            self._snapshot.theme = value
            return True
        if name is CommandName.SET_SYSTEM_MODE:
            self._require_keys(parameters, {"mode"})
            try:
                value = SystemMode(parameters["mode"])
            except (TypeError, ValueError) as exc:
                raise CommandRejected(
                    "invalid_parameters",
                    "mode is not a valid system mode.",
                ) from exc
            if value == self._snapshot.system_mode:
                return False
            self._snapshot.system_mode = value
            if value is SystemMode.TAKEOVER:
                self._activate_simulated_takeover_locked()
            return True

        if name is CommandName.SELECT_DESTINATION:
            self._require_keys(parameters, {"destinationName"})
            destination = parameters["destinationName"]
            if not isinstance(destination, str) or not destination.strip():
                raise CommandRejected(
                    "invalid_parameters", "destinationName must be a non-empty string."
                )
            self._snapshot.active_flow = FlowId.NAVIGATION_HANDOFF
            self._snapshot.navigation = NavigationStateV1(
                provider=RouteProvider.LOCAL_FALLBACK,
                service_status=MapServiceStatus.DEGRADED,
                status=RouteStatus.PREVIEW,
                destination_name=destination.strip(),
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
            return True

        if name is CommandName.CONFIRM_ROUTE:
            self._require_keys(parameters, set())
            if self._snapshot.navigation.status is not RouteStatus.PREVIEW:
                raise CommandRejected(
                    "invalid_transition", "A route preview is required before confirmation."
                )
            self._snapshot.navigation.status = RouteStatus.ACTIVE
            self._snapshot.navigation.updated_at = self._clock()
            return True

        if name in {CommandName.ACKNOWLEDGE_RISK, CommandName.RESOLVE_RISK}:
            self._require_keys(parameters, {"eventId"})
            event_id = parameters["eventId"]
            if not isinstance(event_id, str):
                raise CommandRejected("invalid_parameters", "eventId must be a string.")
            risk = next((item for item in self._snapshot.risks if item.event_id == event_id), None)
            if risk is None:
                raise CommandRejected(
                    "risk_not_found", "The risk event is not active in this snapshot.", 404
                )
            if name is CommandName.ACKNOWLEDGE_RISK:
                if risk.lifecycle.value != "active":
                    raise CommandRejected(
                        "invalid_transition", "Only active risks can be acknowledged."
                    )
                risk.lifecycle = RiskLifecycle.ACKNOWLEDGED
            else:
                if risk.lifecycle.value != "acknowledged":
                    raise CommandRejected(
                        "invalid_transition", "Only acknowledged risks can be resolved."
                    )
                risk.lifecycle = RiskLifecycle.RESOLVED
                self._snapshot.system_mode = SystemMode.RECOVERY
            risk.updated_at = self._clock()
            return True

        if name is CommandName.SET_MEDIA_STATE:
            self._require_keys(parameters, {"state"})
            value = parameters["state"]
            if value not in {"playing", "paused"}:
                raise CommandRejected("invalid_parameters", "state must be playing or paused.")
            if self._media_is_safety_suppressed_locked() and value == "playing":
                raise CommandRejected(
                    "safety_suppressed", "Media cannot play during driver takeover.", 409
                )
            self._snapshot.passenger.media_state = value
            return True

        if name is CommandName.SUBMIT_TRIP_SUGGESTION:
            self._require_keys(parameters, {"suggestion"})
            value = parameters["suggestion"]
            if not isinstance(value, str) or not value.strip():
                raise CommandRejected(
                    "invalid_parameters", "suggestion must be a non-empty string."
                )
            self._snapshot.active_flow = FlowId.PASSENGER_COLLABORATION
            suggestions = [value.strip(), *self._snapshot.passenger.trip_suggestions]
            self._snapshot.passenger.trip_suggestions = suggestions[:8]
            return True

        if name is CommandName.SET_CABIN_CONTROL:
            self._require_keys(parameters, {"privacyEnabled"})
            value = parameters["privacyEnabled"]
            if not isinstance(value, bool):
                raise CommandRejected("invalid_parameters", "privacyEnabled must be boolean.")
            self._snapshot.passenger.privacy_enabled = value
            return True

        self._require_keys(parameters, set())
        previous_revision = self._snapshot.revision
        self._snapshot = self._make_default_snapshot(revision=previous_revision)
        return True

    def _activate_simulated_takeover_locked(self) -> None:
        has_active_risk = any(
            risk.lifecycle in {RiskLifecycle.ACTIVE, RiskLifecycle.ACKNOWLEDGED}
            for risk in self._snapshot.risks
        )
        if has_active_risk:
            return
        now = self._clock()
        self._snapshot.active_flow = FlowId.RISK_TAKEOVER
        self._snapshot.data_health["vision"] = DataHealth(
            status=DataFreshness.FRESH,
            updated_at=now,
        )
        self._snapshot.passenger.media_state = "suppressed"
        self._snapshot.risks.append(
            RiskEventV1(
                event_id=f"simulated-takeover-{self._id_factory()}",
                session_id=self._snapshot.session_id,
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

    def _media_is_safety_suppressed_locked(self) -> bool:
        return any(
            risk.severity is RiskSeverity.CRITICAL
            and risk.lifecycle in {RiskLifecycle.ACTIVE, RiskLifecycle.ACKNOWLEDGED}
            for risk in self._snapshot.risks
        )

    @staticmethod
    def _require_keys(parameters: dict, expected: set[str]) -> None:
        if set(parameters) != expected:
            expected_text = ", ".join(sorted(expected)) or "no parameters"
            raise CommandRejected(
                "invalid_parameters",
                f"Command requires exactly: {expected_text}.",
            )

    def _set_connection_locked(self, endpoint: EndpointId, status: DataFreshness) -> None:
        self._snapshot.endpoint_connectivity[endpoint] = EndpointConnection(
            status=status,
            last_seen_at=self._clock(),
        )

    def _touch_locked(self) -> None:
        self._snapshot.revision += 1
        self._snapshot.timestamp = self._clock()

    def _make_envelope_locked(self, correlation_id: UUID) -> SnapshotEnvelopeV1:
        return SnapshotEnvelopeV1(
            protocol_version=CONTRACT_VERSION,
            message_id=self._id_factory(),
            correlation_id=correlation_id,
            timestamp=self._clock(),
            source=MessageSource(kind="service", id="cockpit-state-authority"),
            payload=self._snapshot.model_copy(deep=True),
        )

    def _publish_locked(self, correlation_id: UUID) -> None:
        envelope = self._make_envelope_locked(correlation_id)
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(envelope.model_copy(deep=True))
