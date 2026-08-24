from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.cockpit_router import create_cockpit_router, serve_platform_websocket
from app.cockpit.errors import CommandRejected
from app.cockpit.service import CockpitService
from app.config import RuntimeSettings
from app.contracts.v1 import (
    CommandEnvelopeV1,
    CommandName,
    CommandPayloadV1,
    EndpointId,
    MessageSource,
)
from app.platform.command_gateway import GatewayResult
from app.platform.errors import AuthenticationRequired, RoleForbidden
from app.platform.models import AuditDelivery, Principal, Role
from app.platform.persistence import DatabaseUnavailable
from app.platform.sessions import SessionIdentity
from app.platform.websocket_registry import WebSocketSessionRegistry

ORIGIN = "http://127.0.0.1:5173"
COOKIE_NAME = "supersonic_platform_session_dev"


def command(name: CommandName, *, endpoint: EndpointId, parameters: dict) -> CommandEnvelopeV1:
    return CommandEnvelopeV1(
        message_id=uuid4(),
        correlation_id=uuid4(),
        timestamp=datetime.now(UTC),
        source=MessageSource(kind="endpoint", id=endpoint.value),
        payload=CommandPayloadV1(name=name, endpoint=endpoint, parameters=parameters),
    )


class FakeWire:
    def __init__(
        self,
        *,
        identity: SessionIdentity | None = None,
        forbidden: bool = False,
        authority: CockpitService | None = None,
        resolve_error: Exception | None = None,
    ) -> None:
        self.identity = identity
        self.forbidden = forbidden
        self.authority = authority or CockpitService()
        self.resolve_error = resolve_error
        self.applied: list[tuple] = []
        self.resolved: list[str] = []

    def cookie_name(self) -> str:
        return COOKIE_NAME

    async def resolve(self, raw_secret: str) -> SessionIdentity:
        self.resolved.append(raw_secret)
        if self.resolve_error is not None:
            raise self.resolve_error
        if self.identity is None:
            raise AuthenticationRequired()
        return self.identity

    async def apply(self, identity, command, *, server_endpoint) -> GatewayResult:
        if self.forbidden:
            raise RoleForbidden()
        self.applied.append((identity, command, server_endpoint))
        envelope = await self.authority.apply_command(
            command,
            server_endpoint=server_endpoint,
        )
        return GatewayResult(envelope=envelope, audit_delivery=AuditDelivery.PRIMARY)


def identity(
    *,
    role: Role = Role.ADMIN,
    expires_at: datetime | None = None,
) -> SessionIdentity:
    return SessionIdentity(
        principal=Principal(
            user_id="11111111-1111-4111-8111-111111111111",
            role=role,
            session_id="22222222-2222-4222-8222-222222222222",
        ),
        display_name="Operator",
        expires_at=expires_at or datetime(2099, 1, 1, tzinfo=UTC),
    )


def make_client(wire: FakeWire) -> TestClient:
    settings = RuntimeSettings(
        control_enabled=True,
        platform_ui_origin=ORIGIN,
    )
    app = FastAPI()
    app.state.cockpit_authority = wire.authority
    app.state.settings = settings

    @app.exception_handler(CommandRejected)
    async def command_rejected(_: object, exc: CommandRejected) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(AuthenticationRequired)
    async def authentication_required(_: object, exc: AuthenticationRequired) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RoleForbidden)
    async def role_forbidden(_: object, exc: RoleForbidden) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(DatabaseUnavailable)
    async def database_unavailable(_: object, exc: DatabaseUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "database_unavailable", "message": str(exc)}},
        )

    app.include_router(
        create_cockpit_router(
            wire.authority,
            settings,
            platform=wire,
            ws_registry=WebSocketSessionRegistry(),
        )
    )
    return TestClient(app)


def test_platform_command_resolve_database_outage_is_503_not_401() -> None:
    client = make_client(FakeWire(identity=identity(), resolve_error=DatabaseUnavailable()))

    response = client.post(
        "/api/v1/commands/control",
        headers={"Origin": ORIGIN},
        cookies={COOKIE_NAME: "valid-secret"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


def test_platform_command_without_cookie_is_401() -> None:
    client = make_client(FakeWire(identity=identity()))

    response = client.post(
        "/api/v1/commands/control",
        headers={"Origin": ORIGIN},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_platform_command_with_invalid_session_is_401() -> None:
    client = make_client(FakeWire(identity=None))

    response = client.post(
        "/api/v1/commands/control",
        headers={"Origin": ORIGIN},
        cookies={COOKIE_NAME: "invalid"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 401


def test_platform_command_role_forbidden_is_403() -> None:
    client = make_client(FakeWire(identity=identity(), forbidden=True))

    response = client.post(
        "/api/v1/commands/control",
        headers={"Origin": ORIGIN},
        cookies={COOKIE_NAME: "valid-secret"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_forbidden"


def test_websocket_gate_rejects_platform_without_registry() -> None:
    settings = RuntimeSettings(control_enabled=True, platform_ui_origin=ORIGIN)
    with pytest.raises(RuntimeError, match="must be configured together"):
        create_cockpit_router(
            CockpitService(),
            settings,
            platform=FakeWire(identity=identity()),
            ws_registry=None,
        )


def test_platform_command_success_returns_envelope() -> None:
    wire = FakeWire(identity=identity())
    client = make_client(wire)

    response = client.post(
        "/api/v1/commands/control",
        headers={"Origin": ORIGIN},
        cookies={COOKIE_NAME: "valid-secret"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 200
    assert response.json()["protocolVersion"] == "gp05.v1"
    assert len(wire.applied) == 1


def test_platform_command_control_disabled_stays_403() -> None:
    settings = RuntimeSettings(control_enabled=False, platform_ui_origin=ORIGIN)
    wire = FakeWire(identity=identity())
    app = FastAPI()

    @app.exception_handler(CommandRejected)
    async def command_rejected(_: object, exc: CommandRejected) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    app.include_router(
        create_cockpit_router(
            wire.authority,
            settings,
            platform=wire,
            ws_registry=WebSocketSessionRegistry(),
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/commands/control",
        headers={"Origin": ORIGIN},
        cookies={COOKIE_NAME: "valid-secret"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "control_disabled"
    assert wire.applied == []


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "null",
        ORIGIN + ".evil",
        "http://evil.example/" + ORIGIN,
        ORIGIN + "/path",
        "https://untrusted.example.test",
    ],
)
def test_platform_command_requires_exact_origin_before_session_resolution(
    origin: str | None,
) -> None:
    wire = FakeWire(identity=identity())
    client = make_client(wire)
    headers = {} if origin is None else {"Origin": origin}

    response = client.post(
        "/api/v1/commands/control",
        headers=headers,
        cookies={COOKIE_NAME: "valid-secret"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "origin_forbidden",
            "message": "Request origin is not allowed.",
        }
    }
    assert wire.resolved == []
    assert wire.applied == []


class FakeEnvelope:
    def model_dump(self, *, mode: str, by_alias: bool) -> dict[str, str]:
        assert mode == "json"
        assert by_alias
        return {"protocolVersion": "gp05.v1"}


class FakeWebSocket:
    def __init__(self) -> None:
        self.headers = {"origin": ORIGIN}
        self.cookies = {COOKIE_NAME: "valid-secret"}
        self.accepted = False
        self.close_codes: list[int] = []
        self.sent: list[dict[str, str]] = []
        self._closed = asyncio.Event()
        self.receive_finished = asyncio.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def receive(self) -> dict[str, str]:
        try:
            await self._closed.wait()
            return {"type": "websocket.disconnect"}
        finally:
            self.receive_finished.set()

    async def send_json(self, payload: dict[str, str]) -> None:
        self.sent.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.close_codes.append(code)
        self._closed.set()


class FakeWebSocketAuthority:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[FakeEnvelope] = asyncio.Queue()
        self.disconnected = False

    async def connect_endpoint(self, endpoint: EndpointId) -> asyncio.Queue[FakeEnvelope]:
        assert endpoint is EndpointId.CLUSTER
        return self.queue

    async def disconnect_endpoint(
        self,
        endpoint: EndpointId,
        queue: asyncio.Queue[FakeEnvelope],
    ) -> None:
        assert endpoint is EndpointId.CLUSTER
        assert queue is self.queue
        self.disconnected = True


async def _wait_for_connection(
    registry: WebSocketSessionRegistry,
    session_id: str,
) -> None:
    for _ in range(100):
        if registry.connection_count(session_id) == 1:
            return
        await asyncio.sleep(0)
    raise AssertionError("WebSocket was not registered")


async def _wait_for_sent(websocket: FakeWebSocket, count: int) -> None:
    for _ in range(100):
        if len(websocket.sent) == count:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"Expected {count} sent snapshots, got {len(websocket.sent)}")


async def test_established_platform_websocket_stops_before_post_expiry_snapshot() -> None:
    expires_at = datetime.now(UTC) + timedelta(milliseconds=100)
    wire = FakeWire(identity=identity(expires_at=expires_at))
    websocket = FakeWebSocket()
    authority = FakeWebSocketAuthority()
    registry = WebSocketSessionRegistry()
    settings = RuntimeSettings(platform_ui_origin=ORIGIN)
    await authority.queue.put(FakeEnvelope())

    async def publish_after_expiry() -> None:
        await asyncio.sleep(0.15)
        await authority.queue.put(FakeEnvelope())

    publisher = asyncio.create_task(publish_after_expiry())
    await asyncio.wait_for(
        serve_platform_websocket(
            websocket,
            EndpointId.CLUSTER,
            authority,
            wire,
            registry,
            settings,
        ),
        timeout=0.5,
    )
    await publisher

    assert websocket.sent == [{"protocolVersion": "gp05.v1"}]
    assert websocket.close_codes == [1008]
    assert websocket.receive_finished.is_set()
    assert authority.disconnected
    assert registry.connection_count(identity().principal.session_id) == 0


async def test_two_established_connections_expire_and_unregister() -> None:
    session_identity = identity(expires_at=datetime.now(UTC) + timedelta(milliseconds=100))
    wire = FakeWire(identity=session_identity)
    first = FakeWebSocket()
    second = FakeWebSocket()
    authority = FakeWebSocketAuthority()
    registry = WebSocketSessionRegistry()
    settings = RuntimeSettings(platform_ui_origin=ORIGIN)

    await asyncio.wait_for(
        asyncio.gather(
            serve_platform_websocket(
                first,
                EndpointId.CLUSTER,
                authority,
                wire,
                registry,
                settings,
            ),
            serve_platform_websocket(
                second,
                EndpointId.CLUSTER,
                authority,
                wire,
                registry,
                settings,
            ),
        ),
        timeout=0.5,
    )

    assert first.close_codes == [1008]
    assert second.close_codes == [1008]
    assert registry.connection_count(session_identity.principal.session_id) == 0


async def test_platform_websocket_connect_failure_unregisters_session() -> None:
    class FailingAuthority(FakeWebSocketAuthority):
        async def connect_endpoint(
            self,
            endpoint: EndpointId,
        ) -> asyncio.Queue[FakeEnvelope]:
            raise RuntimeError("connect failed")

    session_identity = identity()
    wire = FakeWire(identity=session_identity)
    websocket = FakeWebSocket()
    authority = FailingAuthority()
    registry = WebSocketSessionRegistry()

    with pytest.raises(RuntimeError, match="connect failed"):
        await serve_platform_websocket(
            websocket,
            EndpointId.CLUSTER,
            authority,
            wire,
            registry,
            RuntimeSettings(platform_ui_origin=ORIGIN),
        )

    assert registry.connection_count(session_identity.principal.session_id) == 0


async def test_revoke_during_accept_rejects_resolved_websocket_before_registration() -> None:
    accept_started = asyncio.Event()
    release_accept = asyncio.Event()

    class BlockingAcceptWebSocket(FakeWebSocket):
        async def accept(self) -> None:
            accept_started.set()
            await release_accept.wait()
            await super().accept()

    session_identity = identity()
    websocket = BlockingAcceptWebSocket()
    authority = FakeWebSocketAuthority()
    registry = WebSocketSessionRegistry()
    task = asyncio.create_task(
        serve_platform_websocket(
            websocket,
            EndpointId.CLUSTER,
            authority,
            FakeWire(identity=session_identity),
            registry,
            RuntimeSettings(platform_ui_origin=ORIGIN),
        )
    )
    await asyncio.wait_for(accept_started.wait(), timeout=0.2)

    await registry.close_all(session_identity.principal.session_id)
    release_accept.set()
    await asyncio.wait_for(task, timeout=0.2)

    assert websocket.close_codes == [1008]
    assert registry.connection_count(session_identity.principal.session_id) == 0
    assert not authority.disconnected


async def test_platform_websocket_does_not_misreport_inner_timeout_as_session_expiry() -> None:
    class TimeoutAuthority(FakeWebSocketAuthority):
        async def connect_endpoint(
            self,
            endpoint: EndpointId,
        ) -> asyncio.Queue[FakeEnvelope]:
            raise TimeoutError("authority timed out")

    session_identity = identity()
    registry = WebSocketSessionRegistry()

    with pytest.raises(TimeoutError, match="authority timed out"):
        await serve_platform_websocket(
            FakeWebSocket(),
            EndpointId.CLUSTER,
            TimeoutAuthority(),
            FakeWire(identity=session_identity),
            registry,
            RuntimeSettings(platform_ui_origin=ORIGIN),
        )

    assert registry.connection_count(session_identity.principal.session_id) == 0


async def test_failed_revoke_close_blocks_later_snapshot_until_explicit_retry() -> None:
    async def failing_close(_: object) -> None:
        raise RuntimeError("close failed")

    session_identity = identity()
    wire = FakeWire(identity=session_identity)
    websocket = FakeWebSocket()
    authority = FakeWebSocketAuthority()
    registry = WebSocketSessionRegistry(close_connection=failing_close)
    settings = RuntimeSettings(platform_ui_origin=ORIGIN)
    task = asyncio.create_task(
        serve_platform_websocket(
            websocket,
            EndpointId.CLUSTER,
            authority,
            wire,
            registry,
            settings,
        )
    )
    try:
        await _wait_for_connection(registry, session_identity.principal.session_id)
        await authority.queue.put(FakeEnvelope())
        await _wait_for_sent(websocket, 1)

        with pytest.raises(RuntimeError, match="close failed"):
            await registry.close_all(session_identity.principal.session_id)

        assert not registry.may_send(session_identity.principal.session_id, websocket)
        await authority.queue.put(FakeEnvelope())
        await asyncio.sleep(0.02)
        assert websocket.sent == [{"protocolVersion": "gp05.v1"}]
        assert registry.connection_count(session_identity.principal.session_id) == 1

        async def successful_retry(candidate: object) -> None:
            await candidate.close(code=1008)

        registry._close = successful_retry
        await registry.close_all(session_identity.principal.session_id)
        await asyncio.wait_for(task, timeout=0.2)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert registry.connection_count(session_identity.principal.session_id) == 0


async def test_failed_revoke_close_cancels_snapshot_already_in_send() -> None:
    send_started = asyncio.Event()
    send_cancelled = asyncio.Event()

    class SlowSendWebSocket(FakeWebSocket):
        async def send_json(self, payload: dict[str, str]) -> None:
            send_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                send_cancelled.set()

    async def failing_close(_: object) -> None:
        raise RuntimeError("close failed")

    session_identity = identity()
    websocket = SlowSendWebSocket()
    authority = FakeWebSocketAuthority()
    registry = WebSocketSessionRegistry(close_connection=failing_close)
    task = asyncio.create_task(
        serve_platform_websocket(
            websocket,
            EndpointId.CLUSTER,
            authority,
            FakeWire(identity=session_identity),
            registry,
            RuntimeSettings(platform_ui_origin=ORIGIN),
        )
    )
    try:
        await _wait_for_connection(registry, session_identity.principal.session_id)
        await authority.queue.put(FakeEnvelope())
        await asyncio.wait_for(send_started.wait(), timeout=0.2)

        with pytest.raises(RuntimeError, match="close failed"):
            await registry.close_all(session_identity.principal.session_id)

        await asyncio.wait_for(send_cancelled.wait(), timeout=0.2)
        assert websocket.sent == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_session_expiry_cancels_snapshot_already_in_send() -> None:
    send_started = asyncio.Event()
    send_cancelled = asyncio.Event()

    class SlowSendWebSocket(FakeWebSocket):
        async def send_json(self, payload: dict[str, str]) -> None:
            send_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                send_cancelled.set()

    session_identity = identity(expires_at=datetime.now(UTC) + timedelta(milliseconds=100))
    websocket = SlowSendWebSocket()
    authority = FakeWebSocketAuthority()
    registry = WebSocketSessionRegistry()
    await authority.queue.put(FakeEnvelope())

    await asyncio.wait_for(
        serve_platform_websocket(
            websocket,
            EndpointId.CLUSTER,
            authority,
            FakeWire(identity=session_identity),
            registry,
            RuntimeSettings(platform_ui_origin=ORIGIN),
        ),
        timeout=0.5,
    )

    assert send_started.is_set()
    assert send_cancelled.is_set()
    assert websocket.sent == []
    assert websocket.close_codes == [1008]
    assert authority.disconnected
    assert registry.connection_count(session_identity.principal.session_id) == 0
