from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic.alias_generators import to_camel

CONTRACT_VERSION = "gp05.v1"


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class EndpointId(StrEnum):
    CLUSTER = "cluster"
    HUD = "hud"
    CENTER = "center"
    PASSENGER = "passenger"
    OVERVIEW = "overview"
    CONTROL = "control"


class ThemeMode(StrEnum):
    DAY = "day"
    NIGHT = "night"


class ComponentState(StrEnum):
    NORMAL = "normal"
    ACTIVE = "active"
    DISABLED = "disabled"
    WARNING = "warning"
    CRITICAL = "critical"
    LOADING = "loading"
    EMPTY = "empty"
    STALE = "stale"
    OFFLINE = "offline"


class SystemMode(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    TAKEOVER = "takeover"
    STALE = "stale"
    OFFLINE = "offline"
    RECOVERY = "recovery"


class FlowId(StrEnum):
    NAVIGATION_HANDOFF = "navigation_handoff"
    RISK_TAKEOVER = "risk_takeover"
    PASSENGER_COLLABORATION = "passenger_collaboration"


class DataFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    OFFLINE = "offline"


class RiskLifecycle(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class RiskSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RiskSource(StrEnum):
    LIVE_CAMERA = "live_camera"
    VIDEO_INFERENCE = "video_inference"
    SIMULATED_EVENT = "simulated_event"


class RiskType(StrEnum):
    DRIVER_FATIGUE = "driver_fatigue"
    DRIVER_DISTRACTION = "driver_distraction"
    PARKING_GUARD_MOTION = "parking_guard_motion"
    OCCUPANT_PHONE_USE = "occupant_phone_use"
    OCCUPANT_OUT_OF_ZONE = "occupant_out_of_zone"


class RouteProvider(StrEnum):
    AMAP = "amap"
    LOCAL_FALLBACK = "local_fallback"
    NONE = "none"


class MapServiceStatus(StrEnum):
    LIVE = "live"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class RouteStatus(StrEnum):
    IDLE = "idle"
    PLANNING = "planning"
    PREVIEW = "preview"
    ACTIVE = "active"
    ARRIVED = "arrived"
    UNAVAILABLE = "unavailable"


class CommandName(StrEnum):
    SET_THEME = "set_theme"
    SET_SYSTEM_MODE = "set_system_mode"
    SELECT_DESTINATION = "select_destination"
    CONFIRM_ROUTE = "confirm_route"
    ACKNOWLEDGE_RISK = "acknowledge_risk"
    RESOLVE_RISK = "resolve_risk"
    SET_MEDIA_STATE = "set_media_state"
    SUBMIT_TRIP_SUGGESTION = "submit_trip_suggestion"
    SET_CABIN_CONTROL = "set_cabin_control"
    RESET_SESSION = "reset_session"


class EventDomain(StrEnum):
    SYSTEM = "system"
    NAVIGATION = "navigation"
    RISK = "risk"
    PASSENGER = "passenger"
    VISION = "vision"
    PERSISTENCE = "persistence"
    MAP = "map"


ENDPOINT_COMMAND_PERMISSIONS: dict[EndpointId, frozenset[CommandName]] = {
    EndpointId.CLUSTER: frozenset({CommandName.ACKNOWLEDGE_RISK}),
    EndpointId.HUD: frozenset(),
    EndpointId.CENTER: frozenset(
        {
            CommandName.SELECT_DESTINATION,
            CommandName.CONFIRM_ROUTE,
            CommandName.ACKNOWLEDGE_RISK,
            CommandName.RESOLVE_RISK,
            CommandName.SET_MEDIA_STATE,
            CommandName.SET_CABIN_CONTROL,
        }
    ),
    EndpointId.PASSENGER: frozenset(
        {
            CommandName.SET_MEDIA_STATE,
            CommandName.SUBMIT_TRIP_SUGGESTION,
            CommandName.SET_CABIN_CONTROL,
        }
    ),
    EndpointId.OVERVIEW: frozenset(),
    EndpointId.CONTROL: frozenset(CommandName),
}


class DataHealth(ContractModel):
    status: DataFreshness
    updated_at: datetime


class VehicleStateV1(ContractModel):
    speed_kph: float = Field(ge=0, le=320)
    gear: str = Field(min_length=1, max_length=8)
    battery_percent: float = Field(ge=0, le=100)
    range_km: float = Field(ge=0)
    drive_mode: str = Field(min_length=1, max_length=40)
    seatbelt_fastened: bool


class Coordinate(ContractModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class NavigationStep(ContractModel):
    index: int = Field(ge=0)
    instruction: str = Field(min_length=1, max_length=200)
    road_name: str = Field(max_length=120)
    distance_meters: float = Field(ge=0)
    maneuver: str = Field(min_length=1, max_length=60)


class NavigationStateV1(ContractModel):
    provider: RouteProvider = RouteProvider.NONE
    service_status: MapServiceStatus = MapServiceStatus.UNAVAILABLE
    status: RouteStatus = RouteStatus.IDLE
    destination_name: str | None = Field(default=None, max_length=160)
    remaining_distance_meters: float = Field(default=0, ge=0)
    eta_seconds: int = Field(default=0, ge=0)
    current_step: NavigationStep | None = None
    steps: list[NavigationStep] = Field(default_factory=list)
    polyline: list[Coordinate] = Field(default_factory=list)
    updated_at: datetime


class RiskEventV1(ContractModel):
    event_id: str = Field(min_length=1, max_length=80)
    session_id: str = Field(min_length=1, max_length=80)
    risk_type: RiskType
    lifecycle: RiskLifecycle
    severity: RiskSeverity
    source: RiskSource
    confidence: float = Field(ge=0, le=1)
    occurred_at: datetime
    updated_at: datetime
    message: str = Field(min_length=1, max_length=240)
    evidence: list[str] = Field(default_factory=list, max_length=32)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class EndpointConnection(ContractModel):
    status: DataFreshness
    last_seen_at: datetime


class PassengerStateV1(ContractModel):
    media_state: Literal["playing", "paused", "suppressed"] = "paused"
    privacy_enabled: bool = True
    trip_suggestions: list[str] = Field(default_factory=list, max_length=8)


class CockpitSnapshotV1(ContractModel):
    session_id: str = Field(min_length=1, max_length=80)
    revision: int = Field(ge=0)
    timestamp: datetime
    theme: ThemeMode
    system_mode: SystemMode
    active_flow: FlowId
    data_health: dict[str, DataHealth]
    vehicle: VehicleStateV1
    navigation: NavigationStateV1
    risks: list[RiskEventV1] = Field(default_factory=list)
    passenger: PassengerStateV1 = Field(default_factory=PassengerStateV1)
    endpoint_connectivity: dict[EndpointId, EndpointConnection]
    capabilities: list[str] = Field(default_factory=list)


class MessageSource(ContractModel):
    kind: Literal["endpoint", "service"]
    id: str = Field(min_length=1, max_length=80)


class CommandPayloadV1(ContractModel):
    name: CommandName
    endpoint: EndpointId
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class EventPayloadV1(ContractModel):
    domain: EventDomain
    name: str = Field(min_length=1, max_length=100)
    data: dict[str, JsonValue] = Field(default_factory=dict)


class EnvelopeBase(ContractModel):
    protocol_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    message_id: UUID
    correlation_id: UUID
    timestamp: datetime
    source: MessageSource
    target: EndpointId | None = None


class CommandEnvelopeV1(EnvelopeBase):
    kind: Literal["command"] = "command"
    payload: CommandPayloadV1


class EventEnvelopeV1(EnvelopeBase):
    kind: Literal["event"] = "event"
    payload: EventPayloadV1


class SnapshotEnvelopeV1(EnvelopeBase):
    kind: Literal["snapshot"] = "snapshot"
    payload: CockpitSnapshotV1


MessageEnvelopeV1 = Annotated[
    CommandEnvelopeV1 | EventEnvelopeV1 | SnapshotEnvelopeV1,
    Field(discriminator="kind"),
]
