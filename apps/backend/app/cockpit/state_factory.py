from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from ..contracts.v1 import (
    CockpitSnapshotV1,
    CommandName,
    DataFreshness,
    DataHealth,
    EndpointConnection,
    EndpointId,
    FlowId,
    MapServiceStatus,
    NavigationStateV1,
    PassengerStateV1,
    RouteProvider,
    RouteStatus,
    SystemMode,
    ThemeMode,
    VehicleStateV1,
)

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


def navigation_data_freshness(navigation: NavigationStateV1) -> DataFreshness:
    """Map route/provider state to one authoritative navigation-health value."""
    if (
        navigation.provider is RouteProvider.NONE
        or navigation.service_status is MapServiceStatus.UNAVAILABLE
        or navigation.status in {RouteStatus.IDLE, RouteStatus.UNAVAILABLE}
    ):
        return DataFreshness.OFFLINE
    if (
        navigation.provider is RouteProvider.AMAP
        and navigation.service_status is MapServiceStatus.LIVE
    ):
        return DataFreshness.FRESH
    return DataFreshness.STALE


class CockpitStateFactory:
    """Create valid aggregate roots without depending on transport or persistence."""

    def __init__(self, *, clock: Clock, id_factory: IdFactory) -> None:
        self._clock = clock
        self._id_factory = id_factory

    def create_default(self, *, revision: int) -> CockpitSnapshotV1:
        now = self._clock()
        navigation = NavigationStateV1(
            provider=RouteProvider.NONE,
            service_status=MapServiceStatus.UNAVAILABLE,
            status=RouteStatus.IDLE,
            updated_at=now,
        )
        return CockpitSnapshotV1(
            session_id=str(self._id_factory()),
            revision=revision,
            timestamp=now,
            theme=ThemeMode.NIGHT,
            system_mode=SystemMode.NORMAL,
            active_flow=FlowId.NAVIGATION_HANDOFF,
            data_health={
                "vehicle": DataHealth(status=DataFreshness.FRESH, updated_at=now),
                "navigation": DataHealth(
                    status=navigation_data_freshness(navigation),
                    updated_at=navigation.updated_at,
                ),
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
            navigation=navigation,
            passenger=PassengerStateV1(),
            endpoint_connectivity={
                endpoint: EndpointConnection(
                    status=DataFreshness.OFFLINE,
                    last_seen_at=now,
                )
                for endpoint in EndpointId
            },
            capabilities=[
                CommandName.SET_THEME.value,
                CommandName.SET_SYSTEM_MODE.value,
                CommandName.RESET_SESSION.value,
            ],
        )
