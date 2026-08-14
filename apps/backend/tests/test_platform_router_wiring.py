from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.cockpit_router import create_cockpit_router
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
from app.platform.sessions import SessionIdentity
from app.platform.websocket_registry import WebSocketSessionRegistry


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
    ) -> None:
        self.identity = identity
        self.forbidden = forbidden
        self.authority = authority or CockpitService()
        self.applied: list[tuple] = []

    def cookie_name(self) -> str:
        return "supersonic_platform_session_dev"

    async def resolve(self, raw_secret: str) -> SessionIdentity:
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


def identity(*, role: Role = Role.ADMIN) -> SessionIdentity:
    return SessionIdentity(
        principal=Principal(
            user_id="11111111-1111-4111-8111-111111111111",
            role=role,
            session_id="22222222-2222-4222-8222-222222222222",
        ),
        display_name="Operator",
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )


def make_client(wire: FakeWire) -> TestClient:
    settings = RuntimeSettings(
        control_enabled=True,
        platform_ui_origin="http://127.0.0.1:5173",
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

    app.include_router(
        create_cockpit_router(
            wire.authority,
            settings,
            platform=wire,
            ws_registry=WebSocketSessionRegistry(),
        )
    )
    return TestClient(app)


def test_platform_command_without_cookie_is_401() -> None:
    client = make_client(FakeWire(identity=identity()))

    response = client.post(
        "/api/v1/commands/control",
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
        cookies={"supersonic_platform_session_dev": "invalid"},
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
        cookies={"supersonic_platform_session_dev": "valid-secret"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_forbidden"


def test_platform_command_success_returns_envelope() -> None:
    wire = FakeWire(identity=identity())
    client = make_client(wire)

    response = client.post(
        "/api/v1/commands/control",
        cookies={"supersonic_platform_session_dev": "valid-secret"},
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
    settings = RuntimeSettings(control_enabled=False, platform_ui_origin="http://127.0.0.1:5173")
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
        cookies={"supersonic_platform_session_dev": "valid-secret"},
        json=command(
            CommandName.SET_THEME,
            endpoint=EndpointId.CONTROL,
            parameters={"theme": "day"},
        ).model_dump(mode="json", by_alias=True),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "control_disabled"
    assert wire.applied == []
