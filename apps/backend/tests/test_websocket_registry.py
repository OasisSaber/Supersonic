from __future__ import annotations

from app.platform.websocket_registry import WebSocketSessionRegistry


class RecordingCloseHook:
    def __init__(self) -> None:
        self.closed: list[object] = []

    async def __call__(self, connection: object) -> None:
        self.closed.append(connection)


def connection(name: str) -> object:
    return object.__new__(type("FakeConnection", (), {}), )


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
