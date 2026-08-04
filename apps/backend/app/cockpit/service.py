from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ..contracts.v1 import (
    CONTRACT_VERSION,
    CockpitSnapshotV1,
    CommandEnvelopeV1,
    DataFreshness,
    EndpointConnection,
    EndpointId,
    MessageSource,
    SnapshotEnvelopeV1,
)
from .broker import SnapshotBroker
from .policies import CommandPolicy
from .state_factory import CockpitStateFactory
from .transitions import CockpitTransitions


class CockpitService:
    """Application service for one authoritative in-memory cockpit aggregate."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
        command_policy: CommandPolicy | None = None,
        broker: SnapshotBroker | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4
        self._policy = command_policy or CommandPolicy()
        self._broker = broker or SnapshotBroker()
        self._state_factory = CockpitStateFactory(
            clock=self._clock,
            id_factory=self._id_factory,
        )
        self._transitions = CockpitTransitions(
            clock=self._clock,
            id_factory=self._id_factory,
            state_factory=self._state_factory,
        )
        self._lock = asyncio.Lock()
        self._snapshot = self._state_factory.create_default(revision=0)

        # Compatibility aliases for existing white-box tests during migration.
        self._subscribers = self._broker.subscribers
        self._connection_counts = self._broker.connection_counts

    async def get_snapshot(self) -> CockpitSnapshotV1:
        async with self._lock:
            return self._snapshot.model_copy(deep=True)

    async def apply_command(
        self,
        command: CommandEnvelopeV1,
        *,
        server_endpoint: EndpointId | None = None,
    ) -> SnapshotEnvelopeV1:
        async with self._lock:
            self._policy.validate(command, server_endpoint=server_endpoint)
            result = self._transitions.apply(self._snapshot, command)
            if result.changed:
                self._snapshot = result.snapshot
                if result.reset:
                    self._rebuild_connectivity_locked()
                self._touch_locked()
                self._publish_locked(command.correlation_id)
            return self._make_envelope_locked(command.correlation_id)

    async def connect_endpoint(
        self,
        endpoint: EndpointId,
    ) -> asyncio.Queue[SnapshotEnvelopeV1]:
        async with self._lock:
            queue, first_connection = self._broker.subscribe(endpoint)
            if first_connection:
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
            last_connection = self._broker.unsubscribe(endpoint, queue)
            if last_connection:
                self._set_connection_locked(endpoint, DataFreshness.OFFLINE)
                self._touch_locked()
                self._publish_locked(self._id_factory())

    def _make_default_snapshot(self, *, revision: int) -> CockpitSnapshotV1:
        """Compatibility seam for existing tests; prefer CockpitStateFactory."""
        return self._state_factory.create_default(revision=revision)

    def _rebuild_connectivity_locked(self) -> None:
        for endpoint in EndpointId:
            status = (
                DataFreshness.FRESH
                if self._broker.count(endpoint) > 0
                else DataFreshness.OFFLINE
            )
            self._set_connection_locked(endpoint, status)

    def _set_connection_locked(
        self,
        endpoint: EndpointId,
        status: DataFreshness,
    ) -> None:
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
        self._broker.publish(self._make_envelope_locked(correlation_id))
