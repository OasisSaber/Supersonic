from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..data import load_mock_frames, vehicle_for_sequence
from ..mock_llm import generate_mock_report
from ..models import ReportRequest, ReportResponse, RiskLevel, SimulationFrame, TripRecord
from ..risk_engine import evaluate_risk


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
        summary="城市通勤 Mock 行程，用于验证 HMI 风险联动链路。",
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


async def legacy_simulation(websocket: WebSocket) -> None:
    await simulation(websocket)


def create_legacy_router() -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/events", events, methods=["GET"])
    router.add_api_route(
        "/api/trips/demo",
        demo_trip,
        methods=["GET"],
        response_model=TripRecord,
    )
    router.add_api_route(
        "/api/report/generate",
        report,
        methods=["POST"],
        response_model=ReportResponse,
    )
    router.add_api_websocket_route("/ws/simulation", legacy_simulation)
    return router
