from __future__ import annotations

import asyncio

from ..contracts.v1 import EndpointId, SnapshotEnvelopeV1


class SnapshotBroker:
    """Manage bounded snapshot subscribers and endpoint connection counts."""

    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[SnapshotEnvelopeV1]] = set()
        self.connection_counts = dict.fromkeys(EndpointId, 0)

    def subscribe(
        self,
        endpoint: EndpointId,
    ) -> tuple[asyncio.Queue[SnapshotEnvelopeV1], bool]:
        queue: asyncio.Queue[SnapshotEnvelopeV1] = asyncio.Queue(maxsize=1)
        self.subscribers.add(queue)
        self.connection_counts[endpoint] += 1
        return queue, self.connection_counts[endpoint] == 1

    def unsubscribe(
        self,
        endpoint: EndpointId,
        queue: asyncio.Queue[SnapshotEnvelopeV1],
    ) -> bool:
        self.subscribers.discard(queue)
        if self.connection_counts[endpoint] == 0:
            return False
        self.connection_counts[endpoint] -= 1
        return self.connection_counts[endpoint] == 0

    def count(self, endpoint: EndpointId) -> int:
        return self.connection_counts[endpoint]

    def publish(self, envelope: SnapshotEnvelopeV1) -> None:
        for queue in self.subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(envelope.model_copy(deep=True))
