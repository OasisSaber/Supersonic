from __future__ import annotations

import pytest

from app.platform.websocket_registry import WebSocketSessionRegistry


class RecordingCloseHook:
    def __init__(self) -> None:
        self.closed: list[object] = []

    async def __call__(self, connection: object) -> None:
        self.closed.append(connection)


def connection(name: str) -> object:
    return object.__new__(
        type("FakeConnection", (), {}),
    )


def test_register_tracks_connections_per_session() -> None:
    hook = RecordingCloseHook()
    registry = WebSocketSessionRegistry(close_connection=hook)
    first = connection("first")
    second = connection("second")

    registry.register("session-a", first)
    registry.register("session-a", second)
    registry.register("session-b", first)

    assert registry.connection_count("session-a") == 2
    assert registry.connection_count("session-b") == 1
    assert registry.active_sessions() == {"session-a", "session-b"}


async def test_close_all_closes_and_removes_every_connection_of_one_session() -> None:
    hook = RecordingCloseHook()
    registry = WebSocketSessionRegistry(close_connection=hook)
    first = connection("first")
    second = connection("second")
    registry.register("session-a", first)
    registry.register("session-a", second)

    await registry.close_all("session-a")

    assert set(hook.closed) == {first, second}
    assert registry.connection_count("session-a") == 0
    assert registry.active_sessions() == set()


async def test_close_all_preserves_other_sessions() -> None:
    hook = RecordingCloseHook()
    registry = WebSocketSessionRegistry(close_connection=hook)
    kept = connection("kept")
    dropped = connection("dropped")
    registry.register("session-a", dropped)
    registry.register("session-b", kept)

    await registry.close_all("session-a")

    assert hook.closed == [dropped]
    assert registry.connection_count("session-b") == 1
    assert registry.active_sessions() == {"session-b"}


async def test_close_all_is_idempotent_for_unknown_session() -> None:
    hook = RecordingCloseHook()
    registry = WebSocketSessionRegistry(close_connection=hook)

    await registry.close_all("missing-session")

    assert hook.closed == []


async def test_close_all_keeps_failed_and_unattempted_connections_for_retry() -> None:
    first = connection("first")
    failing = connection("failing")
    last = connection("last")
    attempts: list[object] = []

    async def hook(candidate: object) -> None:
        attempts.append(candidate)
        if candidate is failing:
            raise RuntimeError("close failed")

    registry = WebSocketSessionRegistry(close_connection=hook)
    registry.register("session-a", first)
    registry.register("session-a", failing)
    registry.register("session-a", last)

    with pytest.raises(RuntimeError, match="close failed"):
        await registry.close_all("session-a")

    successful_attempts = set(attempts) - {failing}
    assert registry.connection_count("session-a") == 3 - len(successful_attempts)

    retry_attempts: list[object] = []

    async def retry_hook(candidate: object) -> None:
        retry_attempts.append(candidate)

    registry._close = retry_hook
    await registry.close_all("session-a")

    assert set(retry_attempts) == {first, failing, last} - successful_attempts
    assert registry.connection_count("session-a") == 0
    assert registry.active_sessions() == set()


def test_disconnect_removes_only_the_given_connection() -> None:
    hook = RecordingCloseHook()
    registry = WebSocketSessionRegistry(close_connection=hook)
    first = connection("first")
    second = connection("second")
    registry.register("session-a", first)
    registry.register("session-a", second)

    registry.disconnect("session-a", first)

    assert registry.connection_count("session-a") == 1
    assert hook.closed == []


def test_disconnect_removes_session_when_last_connection_leaves() -> None:
    hook = RecordingCloseHook()
    registry = WebSocketSessionRegistry(close_connection=hook)
    only = connection("only")
    registry.register("session-a", only)

    registry.disconnect("session-a", only)

    assert registry.connection_count("session-a") == 0
    assert registry.active_sessions() == set()


def test_disconnect_is_noop_for_unknown_session() -> None:
    hook = RecordingCloseHook()
    registry = WebSocketSessionRegistry(close_connection=hook)

    registry.disconnect("missing-session", connection("phantom"))

    assert registry.active_sessions() == set()
