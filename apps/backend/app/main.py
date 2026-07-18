from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .cockpit_state import CockpitStateAuthority, CommandRejected
from .contracts.v1 import (
    CockpitSnapshotV1,
    CommandEnvelopeV1,
    EndpointId,
    SnapshotEnvelopeV1,
)
from .data import load_mock_frames, vehicle_for_sequence
from .mock_llm import generate_mock_report
from .models import (
    ReportRequest,
    ReportResponse,
    RiskLevel,
    SimulationFrame,
    TripRecord,
)
from .risk_engine import evaluate_risk


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_mock_frames()
    yield


def health() -> dict[str, str]:
    return {"status": "ok", "mode": os.getenv("APP_MODE", "mock")}


def events() -> list[dict]:
    return [frame.model_dump(mode="json") for frame in load_mock_frames()]


def build_demo_trip() -> TripRecord:
    frames = load_mock_frames()
    risk_events = []
    for sequence, frame in enumerate(frames):
        frame.vehicle = vehicle_for_sequence(sequence)
        risk_events.append(evaluate_risk(frame))
    order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
    highest = max((event.level for event in risk_events), key=order.get)
    return TripRecord(
        trip_id="demo-commute-001",
        duration_seconds=max(frame.timestamp for frame in frames),
        frames_processed=len(frames),
        highest_risk=highest,
        events=risk_events,
        summary="城市通勤Mock行程，用于验证HMI风险联动链路。",
    )


def demo_trip() -> TripRecord:
    return build_demo_trip()


def report(request: ReportRequest) -> ReportResponse:
    return generate_mock_report(request.trip)


async def simulation(websocket: WebSocket) -> None:
    await websocket.accept()
    frames = load_mock_frames()
    sequence = 0
    try:
        while True:
            source = frames[sequence % len(frames)].model_copy(deep=True)
            vehicle = vehicle_for_sequence(sequence)
            source.vehicle = vehicle
            payload = SimulationFrame(
                sequence=sequence,
                vehicle=vehicle,
                sensor=source,
                risk=evaluate_risk(source),
            )
            await websocket.send_json(payload.model_dump(mode="json"))
            sequence += 1
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        return


def create_app(authority: CockpitStateAuthority | None = None) -> FastAPI:
    api = FastAPI(
        title="城市通勤风险感知智能座舱 HMI Demo API",
        version="0.2.0",
        lifespan=lifespan,
    )
    api.state.cockpit_authority = authority or CockpitStateAuthority()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.exception_handler(CommandRejected)
    async def command_rejected(_: Request, exc: CommandRejected) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    api.add_api_route("/api/health", health, methods=["GET"])
    api.add_api_route("/api/events", events, methods=["GET"])
    api.add_api_route("/api/trips/demo", demo_trip, methods=["GET"], response_model=TripRecord)
    api.add_api_route(
        "/api/report/generate",
        report,
        methods=["POST"],
        response_model=ReportResponse,
    )

    @api.get("/api/v1/snapshot", response_model=CockpitSnapshotV1)
    async def cockpit_snapshot() -> CockpitSnapshotV1:
        return await api.state.cockpit_authority.get_snapshot()

    @api.post("/api/v1/commands", response_model=SnapshotEnvelopeV1)
    async def cockpit_command(command: CommandEnvelopeV1) -> SnapshotEnvelopeV1:
        return await api.state.cockpit_authority.apply_command(command)

    @api.websocket("/ws/simulation")
    async def legacy_simulation(websocket: WebSocket) -> None:
        await simulation(websocket)

    @api.websocket("/ws/v1/cockpit")
    async def cockpit_websocket(websocket: WebSocket, endpoint: EndpointId) -> None:
        await websocket.accept()
        queue = await api.state.cockpit_authority.connect_endpoint(endpoint)
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
        except WebSocketDisconnect:
            pass
        finally:
            await api.state.cockpit_authority.disconnect_endpoint(endpoint, queue)

    return api


app = create_app()
