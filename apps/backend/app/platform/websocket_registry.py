from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Protocol


class CloseableConnection(Protocol):
    """The minimal WebSocket surface the registry needs to close a connection."""

    async def close(self, code: int = 1000) -> None: ...


CloseConnectionHook = Callable[[object], Awaitable[None]]
SendConnectionHook = Callable[[], Awaitable[None]]


async def _default_close(connection: object) -> None:
    closeable = connection
    await closeable.close()


class WebSocketSessionRegistry:
    """Single-process registry of Platform Session WebSocket connections.

    Maps a platform session id to the set of live connections. `close_all`
    marks every connection non-sendable before invoking the injected close hook,
    so a failed close cannot resume snapshot delivery. Revoked session ids stay
    blocked for the process lifetime to reject handshakes that resolved before
    the durable revoke committed. The registry holds no durable state and is not
    distributed.
    """

    def __init__(
        self,
        *,
        close_connection: CloseConnectionHook | None = None,
    ) -> None:
        self._connections: dict[str, set[object]] = defaultdict(set)
        self._blocked_sessions: set[str] = set()
        self._close_locks: dict[str, asyncio.Lock] = {}
        self._send_tasks: dict[str, set[asyncio.Task[None]]] = defaultdict(set)
        self._close = close_connection or _default_close

    def register(self, session_id: str, connection: object) -> bool:
        if session_id in self._blocked_sessions:
            return False
        self._connections[session_id].add(connection)
        return True

    async def close_all(self, session_id: str) -> None:
        self._blocked_sessions.add(session_id)
        lock = self._close_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            await self._cancel_sends(session_id)
            connections = self._connections.get(session_id)
            if connections is None:
                return
            for connection in tuple(connections):
                current = self._connections.get(session_id)
                if current is None or connection not in current:
                    continue
                await self._close(connection)
                self.disconnect(session_id, connection)

    async def send_if_allowed(
        self,
        session_id: str,
        connection: object,
        send: SendConnectionHook,
    ) -> bool:
        if not self.may_send(session_id, connection):
            return False
        task = asyncio.create_task(send())
        self._send_tasks[session_id].add(task)
        try:
            await task
        except asyncio.CancelledError:
            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling():
                raise
            if session_id not in self._blocked_sessions:
                raise
            return False
        finally:
            tasks = self._send_tasks.get(session_id)
            if tasks is not None:
                tasks.discard(task)
                if not tasks:
                    self._send_tasks.pop(session_id, None)
        return True

    def disconnect(self, session_id: str, connection: object) -> None:
        connections = self._connections.get(session_id)
        if connections is None:
            return
        connections.discard(connection)
        if not connections:
            self._connections.pop(session_id, None)

    def may_send(self, session_id: str, connection: object) -> bool:
        connections = self._connections.get(session_id)
        return (
            connections is not None
            and connection in connections
            and session_id not in self._blocked_sessions
        )

    def active_sessions(self) -> set[str]:
        return set(self._connections)

    def connection_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, ()))

    async def _cancel_sends(self, session_id: str) -> None:
        tasks = tuple(self._send_tasks.get(session_id, ()))
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
