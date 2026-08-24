from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from ..cockpit.errors import CommandRejected
from ..cockpit.service import CockpitService
from ..config import RuntimeSettings
from ..contracts.v1 import (
    CockpitSnapshotV1,
    CommandEnvelopeV1,
    EndpointId,
    SnapshotEnvelopeV1,
)
from ..platform.command_gateway import GatewayResult
from ..platform.errors import AuthenticationRequired, RoleForbidden
from ..platform.persistence import DatabaseUnavailable, MigrationRequired
from ..platform.security import ExactOriginPolicy
from ..platform.sessions import SessionIdentity
from ..platform.websocket_registry import WebSocketSessionRegistry


class PlatformCommandWire(Protocol):
    """Optional platform command path: resolve identity, then apply via gateway."""

    def cookie_name(self) -> str: ...

    async def resolve(self, raw_secret: str) -> SessionIdentity: ...

    async def apply(
        self,
        identity: SessionIdentity,
        command: CommandEnvelopeV1,
        *,
        server_endpoint: EndpointId,
    ) -> GatewayResult: ...


def create_cockpit_router(
    authority: CockpitService,
    settings: RuntimeSettings,
    *,
    platform: PlatformCommandWire | None = None,
    ws_registry: WebSocketSessionRegistry | None = None,
) -> APIRouter:
    if (platform is None) != (ws_registry is None):
        raise RuntimeError("platform wire and WebSocket registry must be configured together")
    router = APIRouter()
    origin_policy = ExactOriginPolicy(settings.platform_ui_origin)

    @router.get("/api/v1/snapshot", response_model=CockpitSnapshotV1)
    async def cockpit_snapshot() -> CockpitSnapshotV1:
        return await authority.get_snapshot()

    @router.get("/api/v1/control/status")
    async def control_status() -> dict[str, bool]:
        return {"controlEnabled": settings.control_enabled}

    @router.post(
        "/api/v1/commands/{endpoint}",
        response_model=SnapshotEnvelopeV1,
    )
    async def cockpit_command(
        endpoint: EndpointId,
        command: CommandEnvelopeV1,
        request: Request,
    ) -> SnapshotEnvelopeV1:
        if platform is not None and not origin_policy.allows(request.headers.get("origin")):
            raise CommandRejected(
                "origin_forbidden",
                "Request origin is not allowed.",
                status_code=403,
            )
        if endpoint is EndpointId.CONTROL and not settings.control_enabled:
            raise CommandRejected(
                "control_disabled",
                "Control endpoint commands are disabled by default.",
                status_code=403,
            )
        if platform is not None:
            return await _platform_command(request, platform, command, endpoint)
        return await authority.apply_command(
            command,
            server_endpoint=endpoint,
        )

    @router.websocket("/ws/v1/cockpit")
    async def cockpit_websocket(websocket: WebSocket, endpoint: EndpointId) -> None:
        if platform is not None and ws_registry is not None:
            await serve_platform_websocket(
                websocket,
                endpoint,
                authority,
                platform,
                ws_registry,
                settings,
            )
            return
        await serve_cockpit_websocket(websocket, endpoint, authority)

    return router


async def _platform_command(
    request: Request,
    platform: PlatformCommandWire,
    command: CommandEnvelopeV1,
    endpoint: EndpointId,
) -> SnapshotEnvelopeV1:
    raw_secret = request.cookies.get(platform.cookie_name())
    if raw_secret is None:
        raise AuthenticationRequired()
    try:
        identity = await platform.resolve(raw_secret)
    except AuthenticationRequired:
        raise
    except (DatabaseUnavailable, MigrationRequired):
        raise
    except Exception as exc:
        raise AuthenticationRequired() from exc
    try:
        result = await platform.apply(
            identity,
            command,
            server_endpoint=endpoint,
        )
    except RoleForbidden:
        raise
    return result.envelope


async def serve_cockpit_websocket(
    websocket: WebSocket,
    endpoint: EndpointId,
    authority: CockpitService,
) -> None:
    await websocket.accept()
    queue = await authority.connect_endpoint(endpoint)
    try:
        while True:
            send_task = asyncio.create_task(queue.get())
            receive_task = asyncio.create_task(websocket.receive())
            done, pending = await asyncio.wait(
                {send_task, receive_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            if receive_task in done:
                message = receive_task.result()
                if message["type"] == "websocket.disconnect":
                    break
            if send_task in done:
                envelope = send_task.result()
                await websocket.send_json(envelope.model_dump(mode="json", by_alias=True))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await authority.disconnect_endpoint(endpoint, queue)


async def serve_platform_websocket(
    websocket: WebSocket,
    endpoint: EndpointId,
    authority: CockpitService,
    platform: PlatformCommandWire,
    registry: WebSocketSessionRegistry,
    settings: RuntimeSettings,
) -> None:
    if not ExactOriginPolicy(settings.platform_ui_origin).allows(websocket.headers.get("origin")):
        await websocket.close(code=1008)
        return
    raw_secret = websocket.cookies.get(platform.cookie_name())
    if raw_secret is None:
        await websocket.close(code=1008)
        return
    try:
        identity = await platform.resolve(raw_secret)
    except Exception:
        await websocket.close(code=1008)
        return
    session_id = identity.principal.session_id
    remaining_seconds = max(
        0.0,
        (identity.expires_at.astimezone(UTC) - datetime.now(UTC)).total_seconds(),
    )
    expiry_deadline = asyncio.get_running_loop().time() + remaining_seconds
    expiry_timeout = asyncio.timeout_at(expiry_deadline)
    queue = None
    registered = False
    try:
        async with expiry_timeout:
            await websocket.accept()
            if not registry.register(session_id, websocket):
                await websocket.close(code=1008)
                return
            registered = True
            queue = await authority.connect_endpoint(endpoint)
            while True:
                snapshot_task = asyncio.create_task(queue.get())
                receive_task = asyncio.create_task(websocket.receive())
                try:
                    done, _ = await asyncio.wait(
                        {snapshot_task, receive_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    iteration_tasks = (snapshot_task, receive_task)
                    for task in iteration_tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*iteration_tasks, return_exceptions=True)

                if receive_task in done:
                    message = receive_task.result()
                    if message["type"] == "websocket.disconnect":
                        break
                if snapshot_task in done:
                    envelope = snapshot_task.result()
                    payload = envelope.model_dump(mode="json", by_alias=True)
                    await registry.send_if_allowed(
                        session_id,
                        websocket,
                        lambda payload=payload: websocket.send_json(payload),
                    )
    except TimeoutError:
        if not expiry_timeout.expired():
            raise
        try:
            await websocket.close(code=1008)
        except Exception:
            pass
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        try:
            if queue is not None:
                await authority.disconnect_endpoint(endpoint, queue)
        finally:
            if registered:
                registry.disconnect(session_id, websocket)
