"""Runtime smoke test for the Mock Demo HTTP and WebSocket chain."""

from __future__ import annotations

import asyncio
import json

import httpx
import websockets


BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/simulation"


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        health = (await client.get("/api/health")).raise_for_status().json()
        assert health == {"status": "ok", "mode": "mock"}

        frames = (await client.get("/api/events")).raise_for_status().json()
        assert len(frames) >= 4
        assert any(
            frame["road"]["pedestrian_detected"] and frame["driver"]["distracted"]
            for frame in frames
        )

        trip = (await client.get("/api/trips/demo")).raise_for_status().json()
        assert trip["highest_risk"] == "high"
        assert any(event["event"] == "pedestrian_and_distraction" for event in trip["events"])

        report = (
            await client.post("/api/report/generate", json={"trip": trip})
        ).raise_for_status().json()
        assert report["provider"] == "mock"
        assert "高风险" in report["trip_report"]

    async with websockets.connect(WS_URL, open_timeout=10) as websocket:
        payloads = [json.loads(await asyncio.wait_for(websocket.recv(), timeout=5)) for _ in range(2)]
        assert [item["sequence"] for item in payloads] == [0, 1]
        assert all("vehicle" in item and "risk" in item for item in payloads)

    print(
        json.dumps(
            {
                "health": health,
                "mock_frames": len(frames),
                "trip_highest_risk": trip["highest_risk"],
                "report_provider": report["provider"],
                "websocket_sequences": [item["sequence"] for item in payloads],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
