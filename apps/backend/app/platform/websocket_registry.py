from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Protocol


class CloseableConnection(Protocol):
    """The minimal WebSocket surface the registry needs to close a connection."""

    async def close(self, code: int = 1000) -> None: ...


CloseConnectionHook = Callable[[object], Awaitable[None]]


async def _default_close(connection: object) -> None:
    closeable = connection
    await closeable.close()


class WebSocketSessionRegistry:
    """Single-process registry of Platform Session WebSocket connections.

    Maps a platform session id to the set of live connections. `close_all`
    closes every connection of a session through the injected close hook so
    revoked sessions stop receiving snapshots immediately. The registry holds
    no durable state and is not distributed.
    """

    def __init__(
        self,
        *,
        close_connection: CloseConnectionHook | None = None,
    ) -> None:
        self._connections: dict[str, set[object]] = defaultdict(set)
        self._close = close_connection or _default_close

    def register(self, session_id: str, connection: object) -> None:
        self._connections[session_id].add(connection)

    async def close_all(self, session_id: str) -> None:
        connections = self._connections.pop(session_id, None)
        if connections is None:
            return
        for connection in connections:
            await self._close(connection)

    def disconnect(self, session_id: str, connection: object) -> None:
        connections = self._connections.get(session_id)
        if connections is None:
            return
        connections.discard(connection)
        if not connections:
            self._connections.pop(session_id, None)

    def active_sessions(self) -> set[str]:
        return set(self._connections)

    def connection_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, ()))
