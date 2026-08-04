from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..cockpit.errors import CommandRejected
from ..cockpit.service import CockpitService
from ..config import RuntimeSettings
from ..contracts.v1 import (
    CockpitSnapshotV1,
    CommandEnvelopeV1,
    EndpointId,
    SnapshotEnvelopeV1,
)


def create_cockpit_router(
    authority: CockpitService,
    settings: RuntimeSettings,
) -> APIRouter:
    router = APIRouter()

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
    ) -> SnapshotEnvelopeV1:
        if endpoint is EndpointId.CONTROL and not settings.control_enabled:
            raise CommandRejected(
                "control_disabled",
                "Control endpoint commands are disabled by default.",
                status_code=403,
            )
        return await authority.apply_command(
            command,
            server_endpoint=endpoint,
        )

    @router.websocket("/ws/v1/cockpit")
    async def cockpit_websocket(websocket: WebSocket, endpoint: EndpointId) -> None:
        await serve_cockpit_websocket(websocket, endpoint, authority)

    return router


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
                await websocket.send_json(
                    envelope.model_dump(mode="json", by_alias=True)
                )
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await authority.disconnect_endpoint(endpoint, queue)
